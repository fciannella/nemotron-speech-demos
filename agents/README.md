# LangGraph Agents

This directory contains LangGraph agents built using the [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api).

## Agents

### simple_agent

A straightforward conversational agent that:
- Maintains conversation history using LangGraph's built-in memory
- Responds using OpenAI's GPT-4o-mini
- Uses the Functional API with `@entrypoint` decorator
- No complex tasks - just simple chat with context

## Setup

### Local Development

1. **Install dependencies:**
```bash
cd agents
pip install -r requirements.txt
```

2. **Set up environment:**
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. **Run the development server:**
```bash
langgraph dev --host 0.0.0.0 --port 2024
```

The server will start at http://localhost:2024

### Docker

The agent is automatically started with Docker Compose:

```bash
# From project root
docker compose up langgraph
```

## Using the Agent

### Via LangGraph Studio

Access the LangGraph Studio UI at http://localhost:2024

### Via API

```python
from langgraph_sdk import get_client

# Connect to the server
client = get_client(url="http://localhost:2024")

# Create a thread (conversation)
thread = client.threads.create()

# Send a message
response = client.runs.create(
    thread_id=thread["thread_id"],
    assistant_id="simple_agent",
    input={
        "messages": [
            {"role": "user", "content": "Hello! How are you?"}
        ]
    }
)

# Get the response
for chunk in client.runs.stream(
    thread_id=thread["thread_id"],
    run_id=response["run_id"]
):
    print(chunk)
```

## Agent Structure

The agent uses LangGraph's Functional API:

```python
@entrypoint(checkpointer=checkpointer)
def simple_agent(input_data: dict) -> dict:
    # Extract messages
    messages = input_data.get("messages", [])
    
    # Call LLM
    response = llm.invoke(messages)
    
    # Return response
    return {"messages": [{"role": "assistant", "content": response.content}]}
```

Key features:
- **`@entrypoint`**: Marks the function as a workflow entry point
- **`checkpointer`**: Enables persistence and memory
- **Simple flow**: No explicit state management needed
- **Automatic checkpointing**: Conversation history is automatically saved

## Configuration

Edit `langgraph.json` to configure agents:

```json
{
  "dependencies": ["."],
  "graphs": {
    "simple_agent": "./simple_agent.py:simple_agent"
  },
  "env": ".env"
}
```

## Testing the Agent

### Interactive Testing

Use the provided test script to chat with the agent:

```bash
cd agents

# Install test dependencies
pip install -r test_requirements.txt

# Run the interactive test
python test_agent.py
```

The script will:
- Connect to the LangGraph service at http://localhost:2024
- Create a conversation thread
- Allow you to chat interactively with the agent
- Maintain conversation history automatically

**Commands:**
- Type your message and press Enter to chat
- Type `new` to start a new conversation thread
- Type `quit`, `exit`, or press Ctrl+C to exit

**Example:**
```
👤 You: Hello! How are you?
🤖 Assistant: Hello! I'm doing well, thank you for asking...

👤 You: What's the weather like?
🤖 Assistant: I don't have access to real-time weather data...

👤 You: new
🔄 Started new conversation

👤 You: quit
👋 Goodbye!
```

### Programmatic Testing

```python
from langgraph_sdk import get_client

# Connect to the service
client = get_client(url="http://localhost:2024")

# Create a thread
thread = client.threads.create()

# Send a message
response = client.runs.create(
    thread_id=thread["thread_id"],
    assistant_id="simple_agent",
    input={
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
)

# Stream the response
for chunk in client.runs.stream(
    thread_id=thread["thread_id"],
    run_id=response["run_id"]
):
    print(chunk)
```

## Next Steps

- Add more sophisticated agents with tasks
- Implement tool calling
- Add human-in-the-loop interactions
- Connect to the Pipecat pipeline

