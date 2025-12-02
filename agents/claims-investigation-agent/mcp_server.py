#!/usr/bin/env python3
"""
MCP Server for Twilio Voice Agent

Exposes tools for AI agents to:
- Initiate customer calls
- Retrieve call summaries
- List all calls
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from twilio.rest import Client as TwilioClient

from call_storage import get_storage

load_dotenv(override=True)

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

# Initialize storage
storage = get_storage()


class VoiceAgentMCPServer:
    """MCP Server for voice agent tools."""

    def __init__(self):
        self.server = Server("twilio-voice-agent")
        self.twilio_client = None
        self._init_twilio()
        self._register_handlers()

    def _init_twilio(self):
        """Initialize Twilio client."""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")

        if account_sid and auth_token:
            self.twilio_client = TwilioClient(account_sid, auth_token)
            logger.info("Twilio client initialized")
        else:
            logger.warning("Twilio credentials not found - calls will fail")

    def _register_handlers(self):
        """Register tool handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="call_customer",
                    description="Initiate an outbound voice call to a customer using a LangGraph agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "phone_number": {
                                "type": "string",
                                "description": "Customer phone number in E.164 format (e.g., +15551234567)",
                            },
                            "langgraph_url": {
                                "type": "string",
                                "description": "LangGraph API endpoint URL (e.g., http://localhost:2024)",
                            },
                            "assistant_name": {
                                "type": "string",
                                "description": "Name of the LangGraph assistant to use (e.g., fraud-notification-agent)",
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Optional metadata to pass to the call (e.g., customer info, case details)",
                            },
                        },
                        "required": ["phone_number", "langgraph_url", "assistant_name"],
                    },
                ),
                Tool(
                    name="get_call_summary",
                    description="Get the summary, transcript, and results of a call",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "call_sid": {
                                "type": "string",
                                "description": "Twilio Call SID from call_customer response",
                            }
                        },
                        "required": ["call_sid"],
                    },
                ),
                Tool(
                    name="list_calls",
                    description="List recent calls with optional status filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of calls to return (default: 20)",
                                "default": 20,
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by call status (initiated, in-progress, completed, failed, no-answer)",
                                "enum": ["initiated", "in-progress", "completed", "failed", "no-answer", "busy"],
                            },
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "call_customer":
                    result = await self._call_customer(arguments)
                elif name == "get_call_summary":
                    result = await self._get_call_summary(arguments)
                elif name == "list_calls":
                    result = await self._list_calls(arguments)
                else:
                    return [
                        TextContent(
                            type="text",
                            text=f"Error: Unknown tool '{name}'",
                        )
                    ]

                return [
                    TextContent(
                        type="text",
                        text=self._format_result(result),
                    )
                ]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [
                    TextContent(
                        type="text",
                        text=f"Error executing {name}: {str(e)}",
                    )
                ]

    async def _call_customer(self, args: Dict) -> Dict:
        """Initiate a customer call."""
        phone_number = args["phone_number"]
        langgraph_url = args["langgraph_url"]
        assistant_name = args["assistant_name"]
        metadata = args.get("metadata", {})

        logger.info(f"Initiating call to {phone_number}")
        logger.info(f"  • Assistant: {assistant_name}")
        logger.info(f"  • LangGraph URL: {langgraph_url}")
        logger.info(f"  • Metadata: {metadata}")

        if not self.twilio_client:
            return {
                "success": False,
                "error": "Twilio client not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN",
            }

        try:
            # Get server URL for TwiML webhook
            server_url = os.getenv("SERVER_URL", "localhost:7861")
            
            # Remove protocol if already present
            server_url = server_url.replace("https://", "").replace("http://", "")
            
            # Determine protocol
            protocol = "https" if not server_url.startswith("localhost") else "http"

            # Prepare call configuration to pass via body data
            call_config = {
                "langgraph_url": langgraph_url,
                "assistant_name": assistant_name,
                **metadata,
            }

            # Construct TwiML URL that will pass config to the bot
            twiml_url = f"{protocol}://{server_url}/twiml"

            # Make the call
            call = self.twilio_client.calls.create(
                to=phone_number,
                from_=os.getenv("TWILIO_PHONE_NUMBER"),
                url=twiml_url,
                method="POST",
            )

            call_sid = call.sid

            # Store in database
            storage.create_call(
                call_sid=call_sid,
                phone_number=phone_number,
                langgraph_url=langgraph_url,
                assistant_name=assistant_name,
                metadata=metadata,
            )

            # Store body data for server.py to retrieve
            # We'll need to pass this via the TwiML somehow
            # For now, let's use an in-memory store in server.py
            # Actually, we need to update server.py to read from storage!

            logger.info(f"Call initiated successfully: {call_sid}")
            logger.info(f"  • LangGraph URL: {langgraph_url}")
            logger.info(f"  • Assistant: {assistant_name}")

            return {
                "success": True,
                "call_sid": call_sid,
                "phone_number": phone_number,
                "status": call.status,
                "langgraph_url": langgraph_url,  # Include for verification
                "assistant_name": assistant_name,
                "message": "Call initiated. Use get_call_summary(call_sid) to retrieve results after 2-3 minutes.",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to initiate call: {e}")
            return {
                "success": False,
                "error": str(e),
                "phone_number": phone_number,
            }

    async def _get_call_summary(self, args: Dict) -> Dict:
        """Get call summary and transcript."""
        call_sid = args["call_sid"]

        logger.info(f"Retrieving call summary for {call_sid}")

        # Get from storage
        summary = storage.get_call_summary(call_sid)

        if not summary:
            # Try to get from Twilio API
            if self.twilio_client:
                try:
                    call = self.twilio_client.calls(call_sid).fetch()
                    return {
                        "call_sid": call_sid,
                        "status": call.status,
                        "duration_seconds": call.duration,
                        "note": "Call found in Twilio but no local summary available. Call may still be in progress.",
                    }
                except Exception as e:
                    logger.error(f"Error fetching from Twilio: {e}")

            return {
                "error": f"Call {call_sid} not found",
                "call_sid": call_sid,
            }

        return summary

    async def _list_calls(self, args: Dict) -> Dict:
        """List recent calls."""
        limit = args.get("limit", 20)
        status = args.get("status")

        logger.info(f"Listing calls (limit={limit}, status={status})")

        calls = storage.list_calls(limit=limit, status=status)

        # Convert datetime objects to ISO strings for JSON serialization
        serializable_calls = []
        for call in calls:
            start_time = call.get("start_time")
            if hasattr(start_time, 'isoformat'):
                start_time = start_time.isoformat()
            
            serializable_calls.append({
                "call_sid": call["call_sid"],
                "phone_number": call["phone_number"],
                "assistant_name": call.get("assistant_name"),
                "status": call["status"],
                "start_time": start_time,
                "duration_seconds": call.get("duration_seconds"),
            })

        return {
            "total": len(serializable_calls),
            "calls": serializable_calls,
        }

    def _format_result(self, result: Dict) -> str:
        """Format result as JSON string."""
        import json

        return json.dumps(result, indent=2)

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Voice Agent MCP Server starting...")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main():
    """Main entry point."""
    server = VoiceAgentMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

