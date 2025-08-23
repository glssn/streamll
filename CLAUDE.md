# StreamLL Development Guide

## Project Overview
StreamLL is a production observability tool for DSPy applications, providing streaming infrastructure for real-time event monitoring with Redis, RabbitMQ, and Terminal sinks.

## Development Philosophy: The Diamond Approach

### Priority Hierarchy (ALWAYS follow this order)
1. **Data integrity bugs first** - Event loss, corruption, inconsistent state
2. **Reliability issues** - Stack overflows, connection failures, resource leaks  
3. **Architecture consistency** - Sync vs async patterns, time sources, error handling
4. **Test infrastructure** - Fixtures, URLs, CI improvements

**Rule**: If you find yourself fixing test infrastructure instead of actual bugs, that's a red flag. Step back and ask: "What's the core problem here?"

### Test-Driven Bug Fixing Protocol

For every bug fix:
1. **Reproduce First**: Write a failing test that demonstrates the exact problem
2. **Identify Root Cause**: Don't treat symptoms - find the actual source
3. **Fix Precisely**: Change only what's necessary to fix the root cause
4. **Verify Completely**: Ensure the test passes and patterns are consistent
5. **Document Impact**: Explain what this fix prevents in production

**Example Structure**:
```python
def test_redis_data_loss_bug(self):
    """Test that reproduces the data loss bug when Redis fails mid-flush.
    
    Bug location: src/streamll/sinks/redis.py:256-267
    Bug: Events were removed from buffer before ensuring Redis write success
    Expected behavior: Events should only be removed AFTER successful write
    """
    # Setup that reproduces the exact scenario
    # Assertions that fail due to the bug
    # Comments explaining why this matters in production
```

### Red Flags (Stop and reconsider when you catch yourself doing these)

❌ **The Patch Cycle**:
- "Let me just quickly fix this URL..."
- Making sync things async (or vice versa) to make tests pass
- Adding sleeps or timeouts to handle race conditions  
- Swallowing exceptions "just to make it work"
- Modifying test fixtures instead of fixing the actual code

❌ **Symptom Treatment**:
- Changing error messages instead of fixing errors
- Adding retries without understanding why things fail
- "This works in my environment" without checking why it fails elsewhere

✅ **Diamond Standard**:
- Write the failing test first
- Understand the failure completely before fixing
- Fix affects the minimum necessary code
- Resulting code is more reliable than before
- Patterns are consistent across the codebase

### StreamLL-Specific Patterns

#### Error Handling
- **Circuit Breaker Pattern**: Use consistent time sources (`time.time()` throughout)
- **Connection Resilience**: Always have fallback mechanisms
- **Event Buffering**: Never lose events - buffer locally when sinks are unavailable

#### Performance
- **Redis**: Use pipelines for batch operations (82x speedup achieved)
- **RabbitMQ**: See `docs/rabbitmq-performance-guide.md` for batching, publisher confirms, and streams
- **Buffering**: Configurable buffer sizes with overflow strategies

#### Testing
- **Integration Tests**: Require actual infrastructure (Redis, RabbitMQ)  
- **Unit Tests**: Mock only external dependencies, not internal logic
- **Bug Tests**: Every bug gets a regression test that reproduces the exact scenario

### Architecture Decisions

#### Sink Pattern
All sinks follow `BaseSink` interface:
- `start()` - Initialize connections/threads
- `stop()` - Graceful shutdown with event flushing
- `handle_event()` - Fast, non-blocking event processing
- `flush()` - Synchronous guarantee that events are processed

#### Event Flow
```
DSPy Application → StreamllEvent → Sink.handle_event() → Buffer → Background Processing → External System
```

#### Dependencies
- **DSPy**: `>=2.6.24,<4.0.0` (minimum for streaming features)
- **Redis**: `>=4.5.4,<7.0.0` (security fixes + compatibility)  
- **RabbitMQ**: `aio-pika>=5.0.0,<10.0.0` (async support)

### Task Management
Use TodoWrite tool to maintain discipline:
- Break complex tasks into specific, testable steps
- Mark tasks in_progress before starting work
- Complete tasks immediately when finished
- Focus on one task at a time

### Code Quality Standards

#### Comments
- No implementation comments unless documenting complex algorithms
- TODO/BUG comments must include specific next actions
- Docstrings for all public methods with examples

#### Logging  
- `logger.debug()` - Development/troubleshooting info
- `logger.info()` - Important operational events  
- `logger.warning()` - Recoverable issues (circuit breaker, retries)
- `logger.error()` - Serious problems that need investigation

#### Testing Commands
```bash
# Run all tests
uv run pytest

# Run specific sink tests
uv run pytest tests/sinks/test_redis_sink.py -m redis

# Run integration tests (requires infrastructure)
uv run pytest -m integration

# Run without coverage for speed during development
uv run pytest --no-cov
```

## Remember: Good Architecture ≠ Perfect Code From Day 1

Good architecture is about **maintaining discipline when things get messy**. The codebase started with good patterns - stick to them even when it's harder.

**Focus priority**: Reliable first, then consistent, then fast.