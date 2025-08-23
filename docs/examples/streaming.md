# Token Streaming Guide

Monitor LLM responses token-by-token as they're generated for real-time user interfaces and analytics.

## Overview

StreamLL's token streaming shows you individual tokens as they arrive from the LLM, perfect for:
- **Chat interfaces** - Show responses building up word-by-word
- **Performance monitoring** - Track token generation speed
- **Real-time analytics** - Analyze response patterns as they happen
- **User experience** - Provide immediate feedback during generation

## Basic Token Streaming

### 1. Wrap Any DSPy Module

```python
import streamll
import dspy

# Create your DSPy module
class ChatBot(dspy.Module):
    def __init__(self):
        super().__init__()
        self.chat = dspy.ChainOfThought("question -> answer")
    
    def forward(self, question):
        return self.chat(question=question)

# Configure DSPy
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash"))

# Create streaming wrapper
bot = ChatBot()
streaming_bot = streamll.create_streaming_wrapper(
    bot,
    signature_field_name="answer"  # Stream the "answer" field
)

# Use it - see tokens stream in real-time!
result = streaming_bot("Explain machine learning in simple terms")
```

### 2. See Token Stream

**Terminal Output:**
```bash
[16:31:42.156] ▶ answer_generation (a1b2c3d4)
[16:31:43.156] • answer_generation (a1b2c3d4) 'Machine'
[16:31:43.198] • answer_generation (a1b2c3d4) ' learning'
[16:31:43.234] • answer_generation (a1b2c3d4) ' is'
[16:31:43.267] • answer_generation (a1b2c3d4) ' a'
[16:31:43.301] • answer_generation (a1b2c3d4) ' type'
[16:31:43.334] • answer_generation (a1b2c3d4) ' of'
[16:31:43.367] • answer_generation (a1b2c3d4) ' artificial'
[16:31:43.401] • answer_generation (a1b2c3d4) ' intelligence...'
[16:31:46.782] ■ answer_generation (a1b2c3d4)
```

## Streaming with Different Modules

### Chain of Thought

```python
@streamll.instrument
class ReasoningBot(dspy.Module):
    def __init__(self):
        super().__init__()
        self.reason = dspy.ChainOfThought("question -> reasoning, answer")

# Stream both reasoning and answer
reasoning_bot = ReasoningBot()

# Stream the reasoning
streaming_reasoning = streamll.create_streaming_wrapper(
    reasoning_bot,
    signature_field_name="reasoning"
)

# Stream the answer  
streaming_answer = streamll.create_streaming_wrapper(
    reasoning_bot,
    signature_field_name="answer"
)
```

### RAG Pipeline

```python
@streamll.instrument  
class RAGPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        docs = self.retrieve(question)
        context = "\n".join([doc.text for doc in docs])
        return self.generate(context=context, question=question)

# Stream RAG answers
rag = RAGPipeline()
streaming_rag = streamll.create_streaming_wrapper(
    rag,
    signature_field_name="answer",
    operation="rag_streaming"  # Custom operation name
)

result = streaming_rag("What are the benefits of renewable energy?")
```

## Advanced Streaming Configuration

### Custom Operation Names

```python
streaming_module = streamll.create_streaming_wrapper(
    module,
    signature_field_name="answer",
    operation="custom_chat",  # Shows as "custom_chat" in events
    event_type="token"        # Event type (default: "token")
)
```

### Async Streaming

```python
# Enable async streaming for high-throughput scenarios
streaming_module = streamll.create_streaming_wrapper(
    module,
    signature_field_name="answer",
    async_streaming=True  # Use async streaming mode
)
```

## Capturing Streaming Events

### Terminal Monitoring

StreamLL automatically shows streaming tokens in the terminal with the `•` symbol.

### Redis Streaming

Store streaming tokens in Redis for analytics:

```python
from streamll.sinks import RedisSink

# Configure Redis sink to capture tokens
@streamll.instrument(sinks=[
    RedisSink("redis://localhost:6379", stream_key="chat_tokens")
])
class StreamingChat(dspy.Module):
    pass

# Create streaming wrapper
streaming_chat = streamll.create_streaming_wrapper(
    StreamingChat(),
    signature_field_name="response"
)

# Tokens are stored in Redis stream "chat_tokens"
result = streaming_chat("Tell me a story")
```

### Read Tokens from Redis

```python
import redis
import json

def read_streaming_tokens():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Read all token events
    entries = r.xread({"chat_tokens": "0"})
    
    tokens = []
    for stream_name, stream_entries in entries:
        for entry_id, fields in stream_entries:
            event = json.loads(fields["event"])
            
            if event["event_type"] == "token":
                tokens.append({
                    "token": event["data"]["token"],
                    "timestamp": event["timestamp"],
                    "token_index": event["data"].get("token_index", 0)
                })
    
    # Sort by token index
    tokens.sort(key=lambda x: x["token_index"])
    
    # Reconstruct full response
    full_response = "".join([t["token"] for t in tokens])
    
    return tokens, full_response

tokens, response = read_streaming_tokens()
print(f"Response: {response}")
print(f"Tokens: {len(tokens)}")
```

## Real-Time Web Interface

Build a chat interface that streams tokens in real-time:

### Backend (FastAPI)

```python
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import streamll
import dspy
import json
import asyncio

app = FastAPI()

# Configure streaming chat
@streamll.instrument
class WebChat(dspy.Module):
    def __init__(self):
        super().__init__()
        self.chat = dspy.ChainOfThought("question -> answer")
    
    def forward(self, question):
        return self.chat(question=question)

dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash"))
chat_bot = WebChat()

# WebSocket for streaming
@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Custom event capture for WebSocket
    captured_tokens = []
    
    def capture_token(event_type, operation=None, data=None):
        if event_type == "token" and data:
            captured_tokens.append(data["token"])
            # Send token to WebSocket immediately
            asyncio.create_task(
                websocket.send_text(json.dumps({
                    "type": "token",
                    "content": data["token"]
                }))
            )
    
    # Monkey-patch emit for this connection
    original_emit = streamll.emit
    streamll.emit = capture_token
    
    try:
        while True:
            # Receive question from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "question":
                captured_tokens.clear()
                
                # Create streaming wrapper  
                streaming_chat = streamll.create_streaming_wrapper(
                    chat_bot,
                    signature_field_name="answer"
                )
                
                # Generate response (tokens stream via WebSocket)
                result = streaming_chat(message["content"])
                
                # Send completion signal
                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "full_response": result.answer
                }))
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Restore original emit
        streamll.emit = original_emit

# Simple HTML client
@app.get("/")
async def get():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Streaming Chat</title>
</head>
<body>
    <div id="chat"></div>
    <input type="text" id="input" placeholder="Ask a question...">
    <button onclick="sendMessage()">Send</button>
    
    <script>
        const ws = new WebSocket("ws://localhost:8000/chat");
        const chat = document.getElementById("chat");
        let currentResponse = "";
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.type === "token") {
                currentResponse += data.content;
                updateChat();
            } else if (data.type === "complete") {
                currentResponse = "";
            }
        };
        
        function updateChat() {
            chat.innerHTML = currentResponse;
        }
        
        function sendMessage() {
            const input = document.getElementById("input");
            const message = input.value;
            input.value = "";
            
            // Add question to chat
            chat.innerHTML += "<div><strong>You:</strong> " + message + "</div>";
            chat.innerHTML += "<div><strong>Bot:</strong> <span id='response'></span></div>";
            
            // Send to WebSocket
            ws.send(JSON.stringify({
                type: "question",
                content: message
            }));
        }
        
        // Send on Enter
        document.getElementById("input").addEventListener("keypress", function(e) {
            if (e.key === "Enter") {
                sendMessage();
            }
        });
    </script>
</body>
</html>
    """)

# Run with: uvicorn main:app --reload
```

### Frontend (React)

```jsx
import React, { useState, useEffect } from 'react';

function StreamingChat() {
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [input, setInput] = useState('');
  const [ws, setWs] = useState(null);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8000/chat');
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'token') {
        setCurrentMessage(prev => prev + data.content);
      } else if (data.type === 'complete') {
        setMessages(prev => [...prev, 
          { type: 'bot', content: data.full_response }
        ]);
        setCurrentMessage('');
      }
    };
    
    setWs(websocket);
    
    return () => websocket.close();
  }, []);

  const sendMessage = () => {
    if (!input.trim()) return;
    
    // Add user message
    setMessages(prev => [...prev, 
      { type: 'user', content: input }
    ]);
    
    // Send to backend
    ws.send(JSON.stringify({
      type: 'question',
      content: input
    }));
    
    setInput('');
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.type}`}>
            <strong>{msg.type === 'user' ? 'You' : 'Bot'}:</strong>
            {msg.content}
          </div>
        ))}
        
        {currentMessage && (
          <div className="message bot streaming">
            <strong>Bot:</strong>
            {currentMessage}
            <span className="cursor">|</span>
          </div>
        )}
      </div>
      
      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask a question..."
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

export default StreamingChat;
```

## Performance Analysis

Analyze streaming performance from captured events:

```python
import redis
import json
from datetime import datetime

def analyze_streaming_performance():
    """Analyze token streaming speed and patterns."""
    
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    entries = r.xread({"chat_tokens": "0"})
    
    token_events = []
    
    for stream_name, stream_entries in entries:
        for entry_id, fields in stream_entries:
            event = json.loads(fields["event"])
            
            if event["event_type"] == "token":
                token_events.append({
                    "timestamp": datetime.fromisoformat(event["timestamp"]),
                    "token": event["data"]["token"],
                    "token_index": event["data"].get("token_index", 0),
                    "operation": event.get("operation", "unknown")
                })
    
    # Group by operation
    operations = {}
    for event in token_events:
        op = event["operation"]
        if op not in operations:
            operations[op] = []
        operations[op].append(event)
    
    # Analyze each operation
    for op_name, events in operations.items():
        events.sort(key=lambda x: x["token_index"])
        
        if len(events) < 2:
            continue
            
        # Calculate streaming speed
        start_time = events[0]["timestamp"]
        end_time = events[-1]["timestamp"]
        duration = (end_time - start_time).total_seconds()
        
        tokens_per_second = len(events) / duration if duration > 0 else 0
        
        # Calculate inter-token delays
        delays = []
        for i in range(1, len(events)):
            delay = (events[i]["timestamp"] - events[i-1]["timestamp"]).total_seconds() * 1000
            delays.append(delay)
        
        avg_delay = sum(delays) / len(delays) if delays else 0
        
        print(f"Operation: {op_name}")
        print(f"  Total tokens: {len(events)}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Speed: {tokens_per_second:.1f} tokens/sec")
        print(f"  Average delay: {avg_delay:.1f}ms between tokens")
        print()

analyze_streaming_performance()
```

## Best Practices

### 1. Choose the Right Field
Stream the most important output field (usually "answer" or "response").

### 2. Handle Connection Issues
Implement reconnection logic for WebSocket clients.

### 3. Buffer Management
Use appropriate buffer sizes for high-frequency streaming.

### 4. Error Handling
Gracefully handle streaming interruptions and LLM errors.

### 5. Performance Monitoring
Track tokens-per-second and latency for optimization.

### 6. User Experience
Show typing indicators and handle long pauses in token generation.

## Troubleshooting

### No Tokens Appearing

```python
# Check if streaming is working
streaming_module = streamll.create_streaming_wrapper(
    module,
    signature_field_name="answer"  # Verify this field exists
)

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Slow Token Generation

```python
# Check LLM model performance
# Some models are faster than others for streaming

# Monitor actual delays
def time_streaming():
    import time
    start = time.time()
    result = streaming_module("test question")
    duration = time.time() - start
    print(f"Total time: {duration:.2f}s")
```

### Missing Tokens

```python
# Ensure proper field name
print(result.keys())  # Check available fields
# Use the correct field name in signature_field_name
```

## Next Steps

- **[Real-time Analytics](../production/monitoring.md)** - Monitor streaming in production
- **[WebSocket Integration](../examples/websockets.md)** - Build live chat interfaces
- **[Performance Optimization](../production/performance.md)** - Optimize streaming speed