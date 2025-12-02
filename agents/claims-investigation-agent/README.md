# Claims Investigation Agent

AI agent that makes outbound phone calls to investigate insurance claims using Twilio and MCP (Model Context Protocol).

## 🎯 What It Does

This agent can:
- **Initiate outbound calls** to customers for claim verification
- **Retrieve call summaries** and transcripts after calls complete
- **List recent calls** with status filtering
- **Make investigation decisions** based on call outcomes

## 🏗️ Architecture

```
User/System Request
    ↓
Claims Investigation Agent (LangGraph)
    ↓
MCP Client Adapter
    ↓
MCP Server (mcp_server.py)
    ↓
Twilio API → Makes real phone call
    ↓
Customer answers
    ↓
Voice Agent (e.g., fraud-notification-agent) conducts conversation
    ↓
Call results stored in SQLite (calls.db)
    ↓
Agent retrieves summary and analyzes
```

## 📁 Files

- **`claims_agent.py`** - Main agent with MCP integration
- **`mcp_server.py`** - MCP server exposing Twilio tools
- **`call_storage.py`** - SQLite storage for call records
- **`README.md`** - This file

## 🛠️ Available Tools

### 1. `call_customer`
Initiate an outbound call to a customer.

**Parameters:**
- `phone_number` (required) - Customer phone in E.164 format (e.g., `+15551234567`)
- `langgraph_url` (required) - LangGraph API endpoint (e.g., `http://langgraph:2024`)
- `assistant_name` (required) - Which voice agent to use (e.g., `fraud-notification-agent`)
- `metadata` (optional) - Additional data (claim ID, customer info, etc.)

**Returns:**
```json
{
  "success": true,
  "call_sid": "CA1234567890abcdef",
  "phone_number": "+15551234567",
  "status": "queued",
  "message": "Call initiated. Use get_call_summary(call_sid) after 2-3 minutes."
}
```

### 2. `get_call_summary`
Retrieve transcript and results from a completed call.

**Parameters:**
- `call_sid` (required) - Call SID from `call_customer` response

**Returns:**
```json
{
  "call_sid": "CA1234567890abcdef",
  "phone_number": "+15551234567",
  "status": "completed",
  "duration_seconds": 180,
  "transcript": "Full conversation transcript...",
  "outcome": {
    "verified": true,
    "fraud_confirmed": false,
    "notes": "Customer confirmed transaction was legitimate"
  },
  "assistant_name": "fraud-notification-agent"
}
```

### 3. `list_calls`
List recent investigation calls.

**Parameters:**
- `limit` (optional) - Max calls to return (default: 20)
- `status` (optional) - Filter by status (`initiated`, `in-progress`, `completed`, `failed`, `no-answer`)

**Returns:**
```json
{
  "total": 5,
  "calls": [
    {
      "call_sid": "CA123...",
      "phone_number": "+15551234567",
      "status": "completed",
      "start_time": "2025-11-24T18:30:00",
      "duration_seconds": 180
    }
  ]
}
```

## 🚀 How to Use

### Example Conversation:

**User:** "Investigate claim CLM-12345 for John Doe at +15551234567"

**Agent:**
1. Uses `call_customer` tool to initiate call
2. Returns: "Call initiated with ID CA123..."
3. Waits for user to ask for results (or automatically checks)
4. Uses `get_call_summary` to retrieve outcome
5. Analyzes results
6. Provides assessment: "Customer verified claim as legitimate. No fraud detected."

## 📋 Requirements

### Twilio Account
- Account SID
- Auth Token
- Twilio phone number

### Voice Agent Server
- Must be publicly accessible (for Twilio webhooks)
- Use ngrok for local development
- Must have TwiML endpoint at `/twiml`

### Environment Variables
```bash
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+15551234567
SERVER_URL=https://your-ngrok-url.ngrok.io
OPENAI_API_KEY=sk-xxxxx
```

## 🧪 Testing

### Test Locally (without real calls):

The MCP server will fail gracefully if Twilio credentials aren't set, allowing you to test the agent logic:

```
User: "List recent calls"
Agent: Uses list_calls tool → Returns empty list or mock data
```

### Test with Real Calls:

1. Set up Twilio credentials
2. Start ngrok: `ngrok http 7861`
3. Set SERVER_URL in .env
4. Restart: `docker-compose up -d`
5. Use agent: "Call +15551234567 for claim verification"

## 📊 Call Storage

### Database Location:
- **Docker**: `/app/data/calls.db` (persisted volume)
- **Local**: `./calls.db`

### View Call Records:
```bash
# In Docker
docker-compose exec langgraph sqlite3 /app/data/calls.db "SELECT * FROM calls;"

# Locally
sqlite3 calls.db "SELECT * FROM calls;"
```

## 🔒 Security Notes

- ✅ Call database persisted in Docker volume
- ✅ Twilio credentials via environment variables (not hardcoded)
- ⚠️ SERVER_URL must use HTTPS in production
- ⚠️ Implement authentication for webhook endpoint
- ⚠️ Add rate limiting for call initiation
- ⚠️ Monitor for abuse (e.g., spamming calls)

## 🎭 Use Cases

1. **Fraud Investigation**
   - Call customer to verify suspicious transaction
   - Get verbal confirmation
   - Record outcome for case file

2. **Claim Verification**
   - Call policyholder about claim
   - Verify details and circumstances
   - Document conversation

3. **Follow-up Calls**
   - Reach out for missing information
   - Confirm claim resolution
   - Customer satisfaction check

4. **Automated Outreach**
   - Batch call multiple customers
   - Consistent investigation process
   - Automated result collection

## 🔧 Customization

### Change LLM Model:
```bash
# In .env or docker-compose.yml
CLAIMS_MODEL=gpt-4o
# Or use default OPENAI_MODEL
```

### Adjust System Prompt:
Edit `SYSTEM_PROMPT` in `claims_agent.py`

### Add Custom Tools:
Add more tools to `mcp_server.py`

## 🐛 Troubleshooting

### Issue: MCP server won't start
**Check**: Python path in container
**Solution**: Verify mcp_server.py is executable

### Issue: Twilio calls fail
**Check**: Credentials and phone number
**Solution**: Verify in Twilio console

### Issue: Calls initiated but no summary
**Check**: SERVER_URL is publicly accessible
**Solution**: Use ngrok or proper domain

### Issue: Database not persisted
**Check**: Volume mount
**Solution**: Verify `/app/data` exists in container

## 📚 Documentation

- **DOCKER_VOLUME_AND_ENV_SETUP.md** - Docker configuration guide
- **MCP_INTEGRATION.md** - MCP architecture details (to be created)

---

**Status**: ✅ Ready to deploy and test!

