# Testing the LangGraph Agent

## Quick Start

### 1. Make sure the LangGraph service is running

```bash
# From project root
docker compose up langgraph -d

# Check it's running
docker compose logs langgraph --tail 20
```

You should see:
```
🚀 API: http://0.0.0.0:2024
✅ Graph registered: simple_agent
```

### 2. Install test dependencies

```bash
cd agents
pip install -r test_requirements.txt
```

### 3. Run the interactive test

```bash
python test_agent.py
```

## Usage Examples

### Basic Conversation

```
🤖 LangGraph Simple Agent - Interactive Test
============================================================
📡 Connecting to: http://localhost:2024
🆔 Thread ID: 550e8400-e29b-41d4-a716-446655440000

💡 Type 'quit', 'exit', or press Ctrl+C to end the conversation
💡 Type 'new' to start a new conversation thread
------------------------------------------------------------

👤 You: Hello! My name is Alice.
🤖 Assistant: Hello Alice! It's nice to meet you. How can I help you today?

👤 You: What's my name?
🤖 Assistant: Your name is Alice! You just told me that. How can I assist you?

👤 You: Tell me a joke
🤖 Assistant: Sure! Why don't scientists trust atoms? Because they make up everything!

👤 You: quit
👋 Goodbye!
```

### Starting a New Conversation

The agent maintains conversation history within a thread. To start fresh:

```
👤 You: Remember this number: 42
🤖 Assistant: Got it! I'll remember that the number is 42.

👤 You: new
🔄 Started new conversation (Thread ID: 660e8400-e29b-41d4-a716-446655440001)

👤 You: What number did I tell you?
🤖 Assistant: I don't have any record of you telling me a number. Could you share it again?
```

### Testing from a Different Machine

If the LangGraph service is running on a server:

```bash
python test_agent.py --url http://your-server:2024
```

## Troubleshooting

### Connection Refused

```
❌ Error connecting to LangGraph service: Connection refused
💡 Make sure the service is running at http://localhost:2024
   Run: docker compose up langgraph
```

**Solution:** Start the LangGraph service:
```bash
docker compose up langgraph -d
```

### Module Not Found

```
ModuleNotFoundError: No module named 'langgraph_sdk'
```

**Solution:** Install test dependencies:
```bash
pip install -r test_requirements.txt
```

### Agent Not Responding

If the agent seems stuck, check the logs:

```bash
docker compose logs langgraph --tail 50
```

Look for errors like:
- Missing OpenAI API key
- Model unavailable
- Rate limiting

**Solution:** Make sure your `.env` file has a valid `OPENAI_API_KEY`:

```bash
# In project root
echo "OPENAI_API_KEY=sk-your-key-here" >> .env
docker compose restart langgraph
```

## Programmatic Testing

For more advanced testing or automation, use the SDK directly:

```python
from langgraph_sdk import get_client
import json

# Connect
client = get_client(url="http://localhost:2024")

# Create thread
thread = client.threads.create()
print(f"Thread ID: {thread['thread_id']}")

# Send multiple messages
messages = [
    "Hello!",
    "What's the capital of France?",
    "Tell me more about it"
]

for msg in messages:
    print(f"\n👤 User: {msg}")
    
    # Send message
    response_text = ""
    for chunk in client.runs.stream(
        thread_id=thread["thread_id"],
        assistant_id="simple_agent",
        input={"messages": [{"role": "user", "content": msg}]},
        stream_mode="values"
    ):
        if isinstance(chunk.data, dict):
            messages_list = chunk.data.get("messages", [])
            if messages_list:
                last_msg = messages_list[-1]
                if isinstance(last_msg, dict) and last_msg.get("role") == "assistant":
                    content = last_msg.get("content", "")
                    if content != response_text:
                        print(f"🤖 Assistant: {content}")
                        response_text = content
```

## Testing Different Scenarios

### Test Memory/Context Retention

```python
# First conversation
"My favorite color is blue"
"What's my favorite color?"  # Should respond: blue

# New thread
"What's my favorite color?"  # Should NOT know
```

### Test Multi-turn Reasoning

```python
"Let's count to 5 together. I'll start: 1"
"What comes next?"  # Should say: 2
"And next?"  # Should say: 3
```

### Test Error Handling

```python
# Very long message
"a" * 10000

# Empty message
""

# Special characters
"Hello! @#$%^&*()_+ こんにちは 你好"
```

## Performance Testing

To test response times:

```bash
time python -c "
from langgraph_sdk import get_client
client = get_client(url='http://localhost:2024')
thread = client.threads.create()
list(client.runs.stream(
    thread_id=thread['thread_id'],
    assistant_id='simple_agent',
    input={'messages': [{'role': 'user', 'content': 'Hello!'}]},
    stream_mode='values'
))
"
```

## Next Steps

Once you've verified the agent works:

1. **Connect to Pipecat**: Update the pipecat service to use this agent
2. **Add Tools**: Extend the agent with function calling
3. **Add Tasks**: Use `@task` decorator for complex operations
4. **Deploy**: Use LangSmith for production deployment

See the [main README](README.md) for more information.

