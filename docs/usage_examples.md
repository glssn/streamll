# streamll Usage Examples

## One-Line Adoption

```python
@streamll.instrument  # This is ALL you need!
class RAGModule(dspy.Module):
    def forward(self, question):
        # Automatically gets DSPy events

        # Can also use manual tracing
        with streamll.trace("custom_operation"):
            result = custom_work()

        return self.chain_of_thought(question=question)
```

## Mixed Usage - DSPy + Manual Tracing

```python
@streamll.instrument  # One line!
class RAGModule(dspy.Module):
    def forward(self, question):
        # This gets DSPy's call_id automatically

        # Manual trace inherits DSPy's execution_id!
        with streamll.trace("preprocessing"):
            # These events share the same execution_id
            processed = clean_text(question)

        # DSPy call - tracked automatically
        context = self.retrieve(processed)

        # Another manual operation
        with streamll.trace("reranking"):
            streamll.emit("operation", operation="custom_rerank")
            reranked = custom_rerank(context)

        # All events share the same execution_id from DSPy!
        return self.generate(context=reranked, question=question)
```

## Event Flow Example

```
DSPy Module.forward() called
├── DSPy generates call_id: "abc123"
├── StreamllDSPyCallback.on_module_start()
│   └── Emits: {execution_id: "abc123", event_type: "start", operation: "module_forward"}
│
├── with streamll.trace("preprocessing"):
│   ├── Gets execution_id from DSPy context: "abc123" 
│   └── Emits: {execution_id: "abc123", event_type: "start", operation: "preprocessing"}
│
├── self.retrieve() called
│   └── StreamllDSPyCallback.on_lm_start()
│       └── Emits: {execution_id: "abc123", event_type: "start", operation: "retrieval"}
│
└── StreamllDSPyCallback.on_module_end()
    └── Emits: {execution_id: "abc123", event_type: "end", operation: "module_forward"}
```

## Three Integration Methods

```python
# Method 1: Decorator (automatic)
@streamll.instrument
class RAGModule(dspy.Module):
    def forward(self, question):
        return self.chain_of_thought(question=question)

# Method 2: Global callbacks (zero code change)
streamll.configure(sinks=[TerminalSink()])
dspy.settings.configure(callbacks=[StreamllDSPyCallback()])

# Method 3: Manual context (fine control)
with streamll.trace("document_processing"):
    streamll.emit("operation_start", operation="ocr")
    result = ocr(document)
    streamll.emit("operation_end", operation="ocr", data={"pages": 5})
```

## Execution ID Resolution

```python
def get_execution_id() -> str:
    """Smart ID resolution."""
    
    # 1. Check if we're in a DSPy callback context
    from dspy.utils.callback import ACTIVE_CALL_ID
    dspy_id = ACTIVE_CALL_ID.get()
    if dspy_id:
        return dspy_id  # Use DSPy's ID
    
    # 2. Check if we're in a streamll.trace() context
    ctx = _execution_context.get()
    if ctx and ctx.get("execution_id"):
        return ctx["execution_id"]
    
    # 3. Generate new ID for standalone calls
    return generate(size=12)
```

## Decorator Auto-Configuration

```python
def instrument(cls):
    """One-line adoption - handles everything!"""
    
    def wrapped_init(self, *args, **kwargs):
        # Call original __init__
        original_init(self, *args, **kwargs)
        
        # Add StreamllDSPyCallback to THIS instance
        if not hasattr(self, "callbacks"):
            self.callbacks = []
        self.callbacks.append(StreamllDSPyCallback())
        
        # Auto-configure streamll if not already done
        if not _global_sinks:
            # Set up default sink (Terminal for dev)
            configure(sinks=[TerminalSink()])
    
    cls.__init__ = wrapped_init
    return cls
```
