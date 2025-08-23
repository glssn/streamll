# DSPy Integration with StreamLL

StreamLL provides deep integration with DSPy through callback mechanisms that capture every aspect of your LLM application workflow.

## Callback Architecture

### LM Callbacks
StreamLL's `StreamllDSPyCallback` automatically captures:
- **Model Information**: Provider, model name, API endpoint
- **Prompts**: Complete prompt templates with variable substitutions
- **Completions**: Full LLM responses including reasoning steps
- **Token Usage**: Input tokens, output tokens, total cost tracking
- **Streaming**: Real-time token streaming for chat applications
- **Errors**: LLM API failures, rate limiting, timeout handling

### Tool Callbacks  
For DSPy tools (retrievers, custom tools, API integrations):
- **Tool Identification**: Tool name, description, class information
- **Arguments**: Input parameters passed to tools
- **Results**: Tool outputs, search results, API responses
- **Performance**: Execution time, success/failure rates
- **Error Handling**: Tool failures, API timeouts, data parsing errors

## Configuration Options

### Privacy Controls
- `include_inputs=False`: Exclude sensitive prompt data
- `include_outputs=False`: Exclude LLM response content
- Custom data filtering for compliance requirements

### Sink Routing
- **Shared Sinks**: TerminalSink for all modules
- **Module-Specific Sinks**: RedisSink per module instance  
- **Event Filtering**: Include only specific event types

## Example Usage

```python
import streamll
from streamll.sinks import TerminalSink, RedisSink
import dspy

# Configure streamll
streamll.configure([
    TerminalSink(),
    RedisSink(url="redis://localhost:6379", stream_key="ml_events")
])

# Set up DSPy with streamll callback
dspy.configure(
    lm=dspy.LM('gemini/gemini-2.5-flash'),
    callback=streamll.dspy_callback()
)

# Your DSPy modules automatically get full observability
class RAGPipeline(dspy.Module):
    def forward(self, query):
        # All LM calls and tool usage tracked automatically
        return self.generate(query=query)
```