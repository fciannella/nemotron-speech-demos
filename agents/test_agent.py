#!/usr/bin/env python3
"""Interactive test script for the simple_agent using LangGraph SDK.

This script connects to the running LangGraph service and allows you to
chat with the agent interactively.

Usage:
    python test_agent.py [--url http://localhost:2024]
"""

import argparse
import asyncio
import sys
from langgraph_sdk import get_client


def print_separator():
    """Print a visual separator."""
    print("-" * 60)


async def chat_with_agent(base_url: str = "http://localhost:2024"):
    """Start an interactive chat session with the agent.
    
    Args:
        base_url: The base URL of the LangGraph service
    """
    print("\n" + "=" * 60)
    print("🤖 LangGraph Simple Agent - Interactive Test")
    print("=" * 60)
    print(f"📡 Connecting to: {base_url}")
    
    try:
        # Create client
        client = get_client(url=base_url)
        
        # Create a new thread (conversation)
        thread = await client.threads.create()
        thread_id = thread["thread_id"]
        print(f"🆔 Thread ID: {thread_id}")
        print("\n💡 Type 'quit', 'exit', or press Ctrl+C to end the conversation")
        print("💡 Type 'new' to start a new conversation thread")
        print_separator()
        
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.lower() == 'new':
                    thread = await client.threads.create()
                    thread_id = thread["thread_id"]
                    print(f"\n🔄 Started new conversation (Thread ID: {thread_id})")
                    continue
                
                # Get the current thread state (conversation history)
                try:
                    state = await client.threads.get_state(thread_id=thread_id)
                    # Extract existing messages from the state
                    # The state values contain "messages" which is the list directly
                    existing_messages = state["values"].get("messages", []) if state.get("values") else []
                except Exception as e:
                    # If no previous state, start fresh
                    existing_messages = []
                
                # Append the new user message to the conversation history
                # The agent expects messages as a list directly (not wrapped in a dict)
                agent_input = existing_messages + [
                    {"role": "user", "content": user_input}
                ]
                
                # Run the agent
                print("\n🤖 Assistant: ", end="", flush=True)
                
                # Stream the response
                response_text = ""
                async for chunk in client.runs.stream(
                    thread_id=thread_id,
                    assistant_id="simple_agent",
                    input=agent_input,
                    stream_mode="values"
                ):
                    # Extract the message content from the chunk
                    if isinstance(chunk.data, dict):
                        messages = chunk.data.get("messages", [])
                        if messages:
                            # Get the last message (which should be the assistant's response)
                            last_message = messages[-1]
                            if isinstance(last_message, dict):
                                role = last_message.get("role")
                                content = last_message.get("content", "")
                                
                                # Only print assistant messages
                                if role == "assistant" and content != response_text:
                                    # Print only the new part
                                    new_text = content[len(response_text):]
                                    print(new_text, end="", flush=True)
                                    response_text = content
                
                print()  # New line after response
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error during conversation: {e}")
                print("💡 Try starting a new conversation with 'new' or restart the script")
    
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error connecting to LangGraph service: {e}")
        print(f"💡 Make sure the service is running at {base_url}")
        print("   Run: docker compose up langgraph")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive test for LangGraph simple_agent"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8124",
        help="Base URL of the LangGraph service (default: http://localhost:8124)"
    )
    
    args = parser.parse_args()
    
    # Run the async function
    asyncio.run(chat_with_agent(base_url=args.url))


if __name__ == "__main__":
    main()

