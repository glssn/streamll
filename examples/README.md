# streamll examples

These examples use [uv's inline script dependencies](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies) for automatic dependency management.

## Running examples

Make sure you have [uv installed](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
# Set your API key
export OPENROUTER_API_KEY="your-key"
# or
export GEMINI_API_KEY="your-key"

# Run examples directly
uv run examples/quickstart.py
uv run examples/production_redis.py
uv run examples/consumer_demo.py
```

`uv` will automatically:
- Install Python 3.11+ if needed
- Create a virtual environment
- Install dependencies (streamll, dspy, etc.)
- Run the script

## Examples

### `quickstart.py`

Basic streamll usage showing:
- `@streamll.instrument` decorator
- Token streaming with `stream_fields=["answer"]`
- Terminal output (default)

### `production_redis.py`

Production Redis integration:
- Stream events to Redis
- Configure Redis connection
- Multiple event processing

### `consumer_demo.py`

Event consumption:
- Listen for streamll events from Redis
- Handle different event types (start, token, end, error)
- Real-time event processing
