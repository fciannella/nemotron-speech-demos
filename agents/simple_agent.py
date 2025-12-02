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
import logging

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
    # Add system instruction to match user's language
    SYSTEM_PROMPT = """You are a helpful and friendly AI voice assistant.

IMPORTANT LANGUAGE RULE: Always respond in the SAME LANGUAGE that the user is speaking.

Supported languages:
- English - respond in English
- Spanish (Español) - respond in Spanish
- French (Français) - respond in French
- German (Deutsch) - respond in German
- Mandarin Chinese (中文) - respond in Mandarin

If the user speaks ANY other language that is NOT in the supported list above, respond in English.

Match the user's language automatically in every response. Be conversational, helpful, and natural."""

    # Log incoming messages for debugging
    logger.info("=" * 80)
    logger.info(f"[SimpleAgent] Received {len(messages)} messages")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        if isinstance(msg, dict):
            logger.info(f"  [{i}] Dict: role={msg.get('role')}, content={msg.get('content', '')[:100]}...")
        elif hasattr(msg, 'content'):
            logger.info(f"  [{i}] {msg_type}: content={getattr(msg, 'content', '')[:100]}...")
        else:
            logger.info(f"  [{i}] {msg_type}: {str(msg)[:100]}...")
    
    # Messages can be LangChain objects or dicts - convert to LangChain messages
    langchain_messages = []
    
    # Add system message at the start if this is a new conversation
    has_system_message = False
    
    for msg in messages:
        # Check if it's already a LangChain message object
        if isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
            if isinstance(msg, SystemMessage):
                has_system_message = True
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
                has_system_message = True
                langchain_messages.append(SystemMessage(content=content))
        else:
            # Try to extract content from unknown object types
            content = getattr(msg, "content", str(msg))
            if content:
                langchain_messages.append(HumanMessage(content=str(content)))
    
    # Prepend system message if not already present
    if not has_system_message:
        langchain_messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))
        logger.info("[SimpleAgent] Added system message with language rules")
    else:
        logger.info("[SimpleAgent] System message already present in conversation")
    
    # Log what we're sending to LLM
    logger.info(f"[SimpleAgent] Sending {len(langchain_messages)} messages to LLM:")
    for i, msg in enumerate(langchain_messages):
        msg_type = type(msg).__name__
        content_preview = msg.content[:100] if hasattr(msg, 'content') else str(msg)[:100]
        logger.info(f"  [{i}] {msg_type}: {content_preview}...")
    
    # Call the LLM with the full message history
    logger.info("[SimpleAgent] Invoking LLM...")
    response = llm.invoke(langchain_messages)
    logger.info(f"[SimpleAgent] LLM response: {response.content[:200]}...")
    logger.info("=" * 80)
    
    # Convert all messages to dict format for consistent storage (including system message)
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

