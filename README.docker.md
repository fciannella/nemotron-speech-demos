# Docker Compose Setup

This document describes how to run the Pipecat Nemotron Demo using Docker Compose.

## Architecture

The application consists of three containers:

1. **pipecat** - Python FastAPI backend running the voice agent pipeline
2. **ui** - React + Vite frontend served by nginx
3. **langgraph** - LangGraph agents service for conversational AI

## Prerequisites

- Docker Engine 20.10 or later
- Docker Compose v2.0 or later
- NVIDIA API keys for Riva services

## Quick Start

### 1. Set Up Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.docker .env
```

Edit `.env` and add your NVIDIA API keys and other configuration values.

### 2. Build and Run

Build and start both containers:

```bash
docker compose up --build
```

Or run in detached mode:

```bash
docker compose up -d --build
```

### 3. Access the Application

#### Local Development

- **UI**: http://localhost
- **Backend API**: http://localhost:7860
- **WebSocket**: ws://localhost/ws
- **LangGraph Studio**: http://localhost:2024

#### Remote Server Deployment

If you're deploying on a remote server and accessing from your local machine:

1. Set the `VITE_API_BASE_URL` environment variable to your remote server's address:

```bash
# In your .env file on the remote server
VITE_API_BASE_URL=http://YOUR_SERVER_IP:7860
# or if using a domain name
VITE_API_BASE_URL=http://your-domain.com:7860
```

2. Rebuild the UI container to apply the changes:

```bash
docker compose build ui
docker compose up -d ui
```

3. Access the UI from your local machine:
   - **UI**: http://YOUR_SERVER_IP or http://your-domain.com
   - **Backend API**: http://YOUR_SERVER_IP:7860

**Important**: The `VITE_API_BASE_URL` must be set **before** building the UI container, as it's baked into the compiled JavaScript during the build process.

## Configuration

### Environment Variables

All configuration is done through environment variables in the `.env` file:

- **NVIDIA_API_KEY**: Your NVIDIA NGC API key (required for Riva STT/TTS)
- **OPENAI_API_KEY**: Your OpenAI API key (required for LangGraph agents)
- **NVIDIA_ASR_FUNCTION_ID**: Function ID for Speech-to-Text service
- **NVIDIA_TTS_FUNCTION_ID**: Function ID for Text-to-Speech service
- **LANGGRAPH_BASE_URL**: URL for LangGraph service (defaults to `http://langgraph:2024` in Docker)
- See `.env.docker` for all available options

### Networking

The containers communicate via a Docker bridge network (`app-network`). The UI container proxies API and WebSocket requests to the pipecat backend.

If you're running LangGraph on your host machine, the pipecat container can access it via `host.docker.internal:2024` (already configured in the default `.env.docker`).

## Docker Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f pipecat
docker compose logs -f ui
```

### Stop Services

```bash
docker compose down
```

### Rebuild After Code Changes

```bash
docker compose up --build
```

### Remove All Containers and Volumes

```bash
docker compose down -v
```

## Development

### Hot Reload (Development Mode)

For development with hot reload, you can mount your source code as volumes. Add to `docker-compose.yml`:

```yaml
services:
  pipecat:
    volumes:
      - ./pipeline_modern.py:/app/pipeline_modern.py
      - ./langgraph_llm_service.py:/app/langgraph_llm_service.py
```

Then restart:

```bash
docker compose restart pipecat
```

### Building Individual Services

```bash
# Build only the backend
docker compose build pipecat

# Build only the UI
docker compose build ui
```

## Troubleshooting

### Remote Server Connection Issues

**Symptoms:**
- Browser console shows: `Failed to load resource: net::ERR_CONNECTION_REFUSED` for `localhost:7860/rtc-config`
- "Could not fetch ICE servers, using defaults"
- "Cannot read properties of undefined (reading 'enumerateDevices')"

**Solution:**
The UI is trying to connect to `localhost:7860` instead of your remote server. You need to configure the `VITE_API_BASE_URL` environment variable:

1. Add to your `.env` file on the remote server:
   ```bash
   VITE_API_BASE_URL=http://YOUR_SERVER_IP:7860
   ```

2. Rebuild and restart the UI container:
   ```bash
   docker compose build ui
   docker compose up -d ui
   ```

3. Clear your browser cache and refresh the page.

### Container Won't Start

1. Check logs: `docker compose logs pipecat`
2. Verify environment variables in `.env`
3. Ensure NVIDIA API keys are valid

### Can't Connect to LangGraph

If LangGraph is running on your host machine:
- Use `LANGGRAPH_BASE_URL=http://host.docker.internal:2024` in `.env`
- Ensure LangGraph is listening on `0.0.0.0:2024`, not just `127.0.0.1:2024`

### WebSocket Connection Issues

1. Check that the pipecat backend is healthy: `docker compose ps`
2. Check nginx logs: `docker compose logs ui`
3. Verify WebSocket endpoint is accessible: `curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost/ws`

### Port Conflicts

If port 80 or 7860 is already in use, modify the port mappings in `docker-compose.yml`:

```yaml
services:
  ui:
    ports:
      - "8080:80"  # Changed from 80:80
  pipecat:
    ports:
      - "7861:7860"  # Changed from 7860:7860
```

## Health Checks

Both containers have health checks configured:

- **pipecat**: Checks `/health` endpoint every 30s
- **ui**: Checks nginx is serving content every 30s

View health status:

```bash
docker compose ps
```

## Production Considerations

1. **HTTPS**: Use a reverse proxy (e.g., Traefik, Caddy) or configure nginx with SSL certificates
2. **Secrets Management**: Use Docker secrets or external secret management instead of `.env` files
3. **Logging**: Configure proper log aggregation (e.g., ELK stack, CloudWatch)
4. **Scaling**: Consider using Docker Swarm or Kubernetes for multi-instance deployments
5. **TURN Servers**: Configure Twilio TURN servers for production WebRTC connections

## Services Overview

### LangGraph Service

The LangGraph container runs agents built with the [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api):

- **simple_agent**: A conversational agent with memory
- Access LangGraph Studio at http://localhost:2024
- Agents automatically maintain conversation history
- See `agents/README.md` for more details

### Starting Individual Services

```bash
# Start only LangGraph
docker compose up langgraph

# Start only backend
docker compose up pipecat

# Start only UI
docker compose up ui
```

## File Structure

```
.
├── Dockerfile              # Pipecat backend Dockerfile
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore           # Backend build exclusions
├── .env.docker             # Example environment variables
├── agents/
│   ├── Dockerfile          # LangGraph agents Dockerfile
│   ├── .dockerignore       # Agents build exclusions
│   ├── simple_agent.py     # Simple conversational agent
│   ├── langgraph.json      # LangGraph configuration
│   ├── requirements.txt    # Python dependencies
│   └── README.md           # Agents documentation
├── ui/
│   ├── Dockerfile          # UI frontend Dockerfile
│   ├── .dockerignore       # UI build exclusions
│   └── nginx.conf          # Nginx configuration
└── README.docker.md        # This file
```

