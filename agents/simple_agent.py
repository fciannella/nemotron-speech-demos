"""Simple conversational agent using LangGraph Functional API.

This agent maintains conversation history and responds using an LLM.
No complex tasks - just a straightforward chat agent with memory.

Note: When running with LangGraph API/CLI, persistence is handled automatically
by the platform, so we don't need to provide a custom checkpointer.
"""

from langgraph.func import entrypoint
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Union


# Initialize the LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


@entrypoint()
def simple_agent(messages: list) -> dict:
    """Simple conversational agent that maintains message history.
    
    Args:
        messages: List of messages - can be LangChain message objects or dicts
                  (includes full conversation history from the thread)
            
    Returns:
        Dictionary containing ALL messages (history + new response)
    """
    # Messages can be LangChain objects or dicts - convert to LangChain messages
    langchain_messages = []
    
    for msg in messages:
        # Check if it's already a LangChain message object
        if isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            langchain_messages.append(msg)
        elif isinstance(msg, dict):
            # Convert dict to LangChain message
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif role == "system":
                langchain_messages.append(SystemMessage(content=content))
        else:
            # Try to extract content from unknown object types
            content = getattr(msg, "content", str(msg))
            if content:
                langchain_messages.append(HumanMessage(content=str(content)))
    
    # Call the LLM with the full message history
    response = llm.invoke(langchain_messages)
    
    # Convert all messages to dict format for consistent storage
    all_messages = []
    for msg in langchain_messages:
        if isinstance(msg, HumanMessage):
            all_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            all_messages.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, SystemMessage):
            all_messages.append({"role": "system", "content": msg.content})
    
    # Add the new response
    all_messages.append({
        "role": "assistant",
        "content": response.content
    })
    
    # Return ALL messages including the new response
    # The platform will persist this full conversation history
    return {
        "messages": all_messages
    }

