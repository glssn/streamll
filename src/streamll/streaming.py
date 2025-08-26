"""
StreamLL Core Streaming Module

Provides real-time streaming capabilities for DSPy modules with StreamLL observability.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def create_streaming_wrapper(
    module: Any,
    signature_field_name: str,
    event_type: str = "token",
    async_streaming: bool = False,
    operation: str | None = None,
) -> Callable:
    """
    Create a streaming wrapper for any DSPy module.

    This function wraps a DSPy module to emit StreamLL events for each token/chunk
    as it's generated during streaming, providing real-time observability into
    LLM response generation.

    Args:
        module: DSPy module to wrap with streaming (e.g., dspy.ChainOfThought)
        signature_field_name: Output field to capture streaming from (e.g., "answer")
        event_type: StreamLL event type to emit (default: "token")
        async_streaming: Whether to use async or sync streaming (default: False)
        operation: Optional operation name for StreamLL events (default: auto-detect)

    Returns:
        Wrapped module function that emits StreamLL events for each token

    Example:
        >>> import streamll
        >>> import dspy
        >>>
        >>> generate = dspy.ChainOfThought("question -> answer")
        >>> streaming_generate = streamll.create_streaming_wrapper(
        ...     generate,
        ...     signature_field_name="answer"
        ... )
        >>>
        >>> # Now streaming_generate emits token events to StreamLL
        >>> result = streaming_generate(question="What is 2+2?")
    """

    # Import here to avoid circular dependencies
    from streamll.context import emit

    try:
        from dspy.streaming import StreamListener, streamify  # noqa: F401
    except ImportError as e:
        logger.error("DSPy streaming not available: %s", e)
        logger.info("Falling back to non-streaming mode")
        return module

    # Determine operation name
    if operation is None:
        operation = f"{module.__class__.__name__.lower()}_streaming"

    # Create streaming version using DSPy's streamify
    # Use raw streamify (no StreamListener) - this is the approach that actually worked
    try:
        streaming_module = streamify(module, async_streaming=async_streaming)
    except Exception as e:
        logger.warning("Failed to create streaming module: %s", e)
        logger.info("Falling back to non-streaming mode")
        return module

    def streaming_wrapper(*args, **kwargs):
        """Execute the module with streaming and emit StreamLL events."""

        token_index = 0
        final_result = None
        streaming_mode = "real_dspy"

        try:
            # Get the streaming iterator
            stream_iterator = streaming_module(*args, **kwargs)

            # Handle async vs sync streaming
            if async_streaming:
                # Convert async generator to sync using DSPy's utility
                try:
                    from dspy.streaming import apply_sync_streaming

                    stream_iterator = apply_sync_streaming(stream_iterator)
                    streaming_mode = "real_dspy_async"
                except ImportError:
                    logger.warning("DSPy async streaming conversion not available")
                    streaming_mode = "real_dspy_async_fallback"

            # Process the stream using the EXACT approach from the working demo
            for value in stream_iterator:
                # Pattern 1: Raw ModelResponseStream chunks - this is what worked!
                if hasattr(value, "choices") and value.choices:
                    delta = value.choices[0].delta
                    if delta and hasattr(delta, "content") and delta.content:
                        chunk_content = delta.content

                        # Emit token event immediately - exactly like working demo
                        emit(
                            event_type,
                            operation=operation,
                            data={
                                "token": chunk_content,
                                "token_index": token_index,
                                "signature_field": signature_field_name,
                                "streaming_mode": streaming_mode,
                                "provider": _extract_provider_from_chunk(value),
                                "chunk_size": len(chunk_content),
                            },
                        )
                        token_index += 1

                # Pattern 2: Final prediction result
                elif hasattr(value, signature_field_name):
                    final_result = value
                    break

                # Pattern 3: Other chunk formats (future compatibility)
                elif hasattr(value, "chunk") and value.chunk:
                    # Handle StreamResponse objects if they exist
                    emit(
                        event_type,
                        operation=operation,
                        data={
                            "token": value.chunk,
                            "token_index": token_index,
                            "signature_field": signature_field_name,
                            "streaming_mode": f"{streaming_mode}_chunk",
                            "provider": "dspy_chunk",
                        },
                    )
                    token_index += 1

            # If we got streaming chunks, but no final result, try to get it normally
            if token_index > 0 and final_result is None:
                logger.info(
                    f"Got {token_index} streaming chunks, but no final result. Attempting normal execution."
                )
                try:
                    final_result = module(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Failed to get final result after streaming: {e}")
                    final_result = None

            # Return the final result
            return final_result

        except Exception as e:
            logger.warning("Streaming failed: %s", e)
            logger.info("Falling back to non-streaming execution")

            # Fallback: execute normally without streaming
            result = module(*args, **kwargs)

            # Emit the complete response as a single token for consistency
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
    """Extract LLM provider name from streaming chunk."""

    # Try to get model info from the chunk
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

    # Fallback to unknown
    return "unknown"


# Utility function for list of streaming fields (future enhancement)
def create_multi_field_streaming_wrapper(
    module: Any,
    signature_field_names: list[str],
    event_type: str = "token",
    async_streaming: bool = False,
) -> Callable:
    """
    Create streaming wrapper for multiple signature fields.

    This is a future enhancement that allows streaming multiple output fields
    from a single DSPy module.

    Note: Currently not implemented - DSPy streaming limitations.
    """
    raise NotImplementedError(
        "Multi-field streaming not yet implemented. "
        "See BACKLOG-001 for auto-detection of streaming fields."
    )


def wrap_with_streaming(forward_method, module_instance, stream_fields: list[str]) -> Callable:
    """Wrap a forward method to enable token streaming.

    This function is used by the @instrument decorator to wrap forward methods
    for token streaming when stream_fields are specified.

    Since DSPy's streamify expects Module objects (not lambdas), we intercept
    and wrap the Predict modules within the forward method.

    Args:
        forward_method: The original forward method
        module_instance: The module instance being wrapped
        stream_fields: List of field names to stream

    Returns:
        Wrapped forward method that emits TokenEvents
    """
    from streamll.context import emit_event, get_execution_id
    from streamll.models import StreamllEvent, generate_event_id

    try:
        import dspy
        from dspy.streaming import StreamListener, streamify
        from dspy.streaming.messages import StreamResponse
    except ImportError as e:
        logger.warning(f"DSPy streaming not available: {e}")
        # Return unwrapped method if streaming not available
        return forward_method

    def streaming_forward(*args, **kwargs):
        """Execute forward with streaming and emit TokenEvents."""

        # Find all Predict modules in the instance
        predictors = []
        for name, attr in module_instance.__dict__.items():
            if isinstance(attr, dspy.Predict):
                predictors.append((name, attr, None))  # (name, predictor, parent)
            elif isinstance(attr, dspy.ChainOfThought):
                # ChainOfThought has an internal 'predict' attribute
                if hasattr(attr, "predict") and isinstance(attr.predict, dspy.Predict):
                    # Add the internal predict with parent reference
                    predictors.append(
                        ("predict", attr.predict, attr)
                    )  # (attr_name, predictor, parent)

        if not predictors:
            # No predictors to stream, just call normally
            return forward_method(*args, **kwargs)

        # Store original predictors and wrap them
        original_predictors = []
        for predictor_name, predictor, parent in predictors:
            # Check if this predictor has fields we want to stream
            try:
                output_fields = predictor.signature.output_fields
                fields_to_stream = [f for f in stream_fields if f in output_fields]

                if not fields_to_stream:
                    continue

                # Store original with parent info
                original_predictors.append((predictor_name, predictor, parent))

                # Track token indices per field
                token_indices = {field: 0 for field in fields_to_stream}

                # Create listeners
                listeners = [
                    StreamListener(signature_field_name=field) for field in fields_to_stream
                ]

                # Wrap with streamify
                stream_predictor = streamify(
                    predictor,
                    stream_listeners=listeners,
                    async_streaming=False,
                    include_final_prediction_in_output_stream=True,
                )

                # Create wrapper that processes stream
                def make_streaming_wrapper(pred_name, indices):
                    def streaming_predict(*pred_args, **pred_kwargs):
                        result = None
                        stream_output = stream_predictor(*pred_args, **pred_kwargs)
                        
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

                # Replace predictor with streaming version
                wrapper = make_streaming_wrapper(predictor_name, token_indices)
                if parent is not None:
                    # This is from ChainOfThought, set on parent
                    setattr(parent, predictor_name, wrapper)
                else:
                    # This is a direct Predict on module
                    setattr(module_instance, predictor_name, wrapper)

            except (AttributeError, Exception) as e:
                logger.warning(f"Could not wrap predictor {predictor_name}: {e}")
                continue

        try:
            # Call forward with wrapped predictors
            result = forward_method(*args, **kwargs)
        finally:
            # Restore original predictors
            for name, original, parent in original_predictors:
                if parent is not None:
                    # Restore on parent (ChainOfThought)
                    setattr(parent, name, original)
                else:
                    # Restore on module
                    setattr(module_instance, name, original)

        return result

    return streaming_forward


__all__ = [
    "create_streaming_wrapper",
    "create_multi_field_streaming_wrapper",
    "wrap_with_streaming",
]
