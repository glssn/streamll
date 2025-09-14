import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _process_stream_chunk(
    chunk: Any,
    signature_field_name: str,
    token_index: int,
    event_type: str,
    operation: str | None,
    streaming_mode: str,
) -> tuple[str | None, Any | None, int]:
    from streamll.context import emit

    if hasattr(chunk, "choices") and chunk.choices:
        delta = chunk.choices[0].delta
        if delta and hasattr(delta, "content") and delta.content:
            emit(
                event_type,
                operation=operation,
                data={
                    "token": delta.content,
                    "token_index": token_index,
                    "signature_field": signature_field_name,
                    "streaming_mode": streaming_mode,
                    "provider": _extract_provider_from_chunk(chunk),
                    "chunk_size": len(delta.content),
                },
            )
            return delta.content, None, token_index + 1

    if hasattr(chunk, signature_field_name):
        return None, chunk, token_index

    if hasattr(chunk, "chunk") and chunk.chunk:
        emit(
            event_type,
            operation=operation,
            data={
                "token": chunk.chunk,
                "token_index": token_index,
                "signature_field": signature_field_name,
                "streaming_mode": f"{streaming_mode}_chunk",
                "provider": "dspy_chunk",
            },
        )
        return chunk.chunk, None, token_index + 1

    return None, None, token_index


def create_streaming_wrapper(  # noqa: C901
    module: Any,
    signature_field_name: str,
    event_type: str = "token",
    async_streaming: bool = False,
    operation: str | None = None,
) -> Callable:
    from streamll.context import emit

    try:
        from dspy.streaming import streamify
    except ImportError as e:
        logger.error("DSPy streaming not available: %s", e)
        return module

    if operation is None:
        operation = f"{module.__class__.__name__.lower()}_streaming"

    try:
        streaming_module = streamify(module, async_streaming=async_streaming)
    except Exception as e:
        logger.warning("Failed to create streaming module: %s", e)
        return module

    def streaming_wrapper(*args, **kwargs):  # noqa: C901
        token_index = 0
        final_result = None
        streaming_mode = "real_dspy"

        try:
            stream_iterator = streaming_module(*args, **kwargs)

            if async_streaming:
                try:
                    import inspect

                    from dspy.streaming import apply_sync_streaming

                    if inspect.isasyncgen(stream_iterator) or hasattr(stream_iterator, "__aiter__"):
                        stream_iterator = apply_sync_streaming(stream_iterator)  # type: ignore[arg-type]
                        streaming_mode = "real_dspy_async"
                except ImportError:
                    logger.warning("DSPy async streaming conversion not available")

            for chunk in stream_iterator:  # type: ignore[union-attr]
                _, final_result, token_index = _process_stream_chunk(
                    chunk,
                    signature_field_name,
                    token_index,
                    event_type,
                    operation,
                    streaming_mode,
                )
                if final_result:
                    break

            if token_index > 0 and final_result is None:
                logger.info(
                    f"Got {token_index} streaming chunks, no final result. Attempting normal execution."
                )
                try:
                    final_result = module(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Failed to get final result after streaming: {e}")

            return final_result

        except Exception as e:
            logger.warning("Streaming failed: %s", e)
            logger.info("Falling back to non-streaming execution")

            result = module(*args, **kwargs)
            if hasattr(result, signature_field_name):
                field_content = getattr(result, signature_field_name)
                if field_content:
                    emit(
                        event_type,
                        operation=operation,
                        data={
                            "token": field_content,
                            "token_index": 0,
                            "signature_field": signature_field_name,
                            "streaming_mode": "fallback_complete",
                            "provider": "fallback",
                        },
                    )

            return result

    return streaming_wrapper


def _extract_provider_from_chunk(chunk: Any) -> str:
    if hasattr(chunk, "model") and chunk.model:
        model = chunk.model.lower()
        if "gpt" in model or "openai" in model:
            return "openai"
        elif "gemini" in model or "google" in model:
            return "gemini"
        elif "claude" in model or "anthropic" in model:
            return "anthropic"
        elif "llama" in model:
            return "meta"
        else:
            return model
    return "unknown"


def _find_predictors_in_module(
    module_instance: Any, stream_fields: list[str]
) -> list[tuple[str, Any, Any]]:
    import dspy

    predictors = []
    for name, attr in module_instance.__dict__.items():
        if isinstance(attr, dspy.Predict):
            predictors.append((name, attr, None))
        elif (
            isinstance(attr, dspy.ChainOfThought)
            and hasattr(attr, "predict")
            and isinstance(attr.predict, dspy.Predict)
        ):
            predictors.append(("predict", attr.predict, attr))

    result = []
    for predictor_name, predictor, parent in predictors:
        try:
            output_fields = predictor.signature.output_fields
            if any(f in output_fields for f in stream_fields):
                result.append((predictor_name, predictor, parent))
        except (AttributeError, Exception) as e:
            logger.warning(f"Could not check predictor {predictor_name}: {e}")

    return result


def wrap_with_streaming(forward_method, module_instance, stream_fields: list[str]) -> Callable:  # noqa: C901
    from streamll.context import emit_event, get_execution_id
    from streamll.models import StreamllEvent, generate_event_id

    try:
        import dspy
        from dspy.streaming import StreamListener, streamify
        from dspy.streaming.messages import StreamResponse
    except ImportError as e:
        logger.warning(f"DSPy streaming not available: {e}")
        return forward_method

    def streaming_forward(*args, **kwargs):  # noqa: C901
        predictors = _find_predictors_in_module(module_instance, stream_fields)
        if not predictors:
            return forward_method(*args, **kwargs)

        original_predictors = []
        for predictor_name, predictor, parent in predictors:
            original_predictors.append((predictor_name, predictor, parent))

            token_indices = {
                field: 0 for field in stream_fields if field in predictor.signature.output_fields
            }

            listeners = [StreamListener(signature_field_name=field) for field in token_indices]

            stream_predictor = streamify(
                predictor,
                stream_listeners=listeners,
                async_streaming=False,
                include_final_prediction_in_output_stream=True,
            )

            def make_streaming_wrapper(pred_name, indices, predictor):
                def streaming_predict(*pred_args, **pred_kwargs):
                    result = None
                    stream_output = predictor(*pred_args, **pred_kwargs)

                    for chunk in stream_output:
                        if isinstance(chunk, StreamResponse):
                            field_name = chunk.signature_field_name
                            if field_name in indices:
                                event = StreamllEvent(
                                    event_id=generate_event_id(),
                                    execution_id=get_execution_id(),
                                    timestamp=datetime.now(UTC),
                                    module_name=module_instance.__class__.__name__,
                                    method_name=pred_name,
                                    event_type="token",
                                    data={
                                        "field": field_name,
                                        "token": chunk.chunk,
                                        "token_index": indices[field_name],
                                    },
                                )
                                emit_event(event, module_instance)
                                indices[field_name] += 1
                        elif isinstance(chunk, dspy.Prediction):
                            result = chunk

                    return result

                return streaming_predict

            wrapper = make_streaming_wrapper(predictor_name, token_indices, stream_predictor)
            if parent is not None:
                setattr(parent, predictor_name, wrapper)
            else:
                setattr(module_instance, predictor_name, wrapper)

        try:
            result = forward_method(*args, **kwargs)
        finally:
            for name, original, parent in original_predictors:
                if parent is not None:
                    setattr(parent, name, original)
                else:
                    setattr(module_instance, name, original)

        return result

    return streaming_forward


__all__ = [
    "create_streaming_wrapper",
    "wrap_with_streaming",
]
