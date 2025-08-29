# StreamLL Development Guide

## Project Overview
StreamLL provides real-time observability for DSPy applications through the `@streamll.instrument` decorator and `streamll.trace()` context manager, with production sinks for Redis, RabbitMQ, and Terminal output.

## Core Philosophy: Less is More

### The Simplification Rule
Core functionality is ~2100 lines (src/). Tests add another ~1900 lines. Always ask:
- "Do we really need this?"
- "Can we achieve the same with less?"
- "Is this solving a real problem or a hypothetical one?"

### Priority Hierarchy (NEVER compromise on these)
1. **Core features must work** - `@streamll.instrument` decorator is THE core feature
2. **Clear naming** - No apologetic names (not "SimpleTerminalSink", just "TerminalSink")
3. **Essential complexity only** - If it takes 400 lines, try 40
4. **Real tests over infrastructure** - 26 working tests > 100 broken fixtures

## Critical Features (These MUST Always Work)

### 1. The Decorator
```python
@streamll.instrument
class MyModule(dspy.Module):
    def forward(self, x):
        return self.predict(x)
```
This is why users choose StreamLL. If this breaks, nothing else matters.

### 2. The Trace Context
```python
with streamll.trace("operation") as ctx:
    # Automatic start/end/error events
    ctx.emit("custom", data={"key": "value"})
```

### 3. Production Sinks
- **TerminalSink**: For development (not "SimpleTerm..." or "BasicTerm...")
- **RedisSink**: For production with buffering
- **RabbitMQSink**: For message queue integration

## Red Flags (Stop immediately if you catch yourself)

❌ **Over-Engineering**:
- Writing 400+ line files for simple features
- Adding "version tracking" or "AST hashing" to a 0.1 project
- Creating abstractions for single use cases
- Parameterizing everything (Redis sink needs 3 params, not 16)

❌ **Naming Crimes**:
- Apologetic names ("Simple", "Basic", "Minimal")
- Redundant suffixes ("StreamllEvent" in streamll package)
- Inconsistent patterns (some async, some sync without reason)

❌ **Documentation Bloat**:
- Keep docs proportional to code
- Examples that don't run
- Planning documents in the repo (JIRA.md, ROADMAP.md)

## The Right Way

### When Adding Features
1. **Start with "No"** - Default to not adding it
2. **Prove the need** - Real user request or actual bug
3. **Implement minimally** - Shortest path to working
4. **Test simply** - One clear test that shows it works
5. **Document briefly** - One example in README

### When Fixing Bugs
1. **Reproduce first** - Failing test before any fix
2. **Fix root cause** - Not symptoms
3. **Keep fix minimal** - Don't refactor the world
4. **Verify completely** - Test passes, examples work

### When Refactoring
**DON'T** - Unless you can delete 50%+ of the code

## Code Standards

### Structure
```
src/streamll/
  __init__.py       # Public API (minimal exports)
  decorator.py      # @instrument (< 150 lines)
  context.py        # trace() context (< 200 lines)
  streaming.py      # Token streaming logic
  models.py         # Single event model (< 50 lines)
  sinks/
    base.py         # BaseSink with buffering/circuit breaker
    terminal.py     # TerminalSink (< 100 lines)
    redis.py        # RedisSink (< 150 lines)
    rabbitmq.py     # RabbitMQSink (< 200 lines)
```

### Testing
```bash
# Run all tests - they should ALL pass
uv run pytest

# With environment variables for integration tests
uv run --env-file /path/to/.env pytest

# Quick check without coverage
uv run pytest --no-cov
```

### Examples Must Work
Every example in `examples/` must:
- Run without errors
- Use OpenRouter or Gemini (not OpenAI with quotas)
- Show a real use case
- Be under 150 lines

## Task Management
When working on multiple items, use TodoWrite to track:
- One task in_progress at a time
- Mark complete immediately when done
- Delete tasks that become irrelevant

## Final Rule: Protect the Core

The decorator and trace context are why StreamLL exists. Everything else is secondary. If a change might break these, it's not worth it.

Remember: Simpler code is better code. When in doubt, delete.

**Focus**: Working code > Perfect architecture > Comprehensive docs