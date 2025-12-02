# Dockerfile for LangGraph Agents

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code and configuration
COPY simple_agent.py .
COPY wire-transfer-agent/ ./wire-transfer-agent/
COPY claims-investigation-agent/ ./claims-investigation-agent/
COPY telco-agent/ ./telco-agent/
COPY rbc-fees-agent/ ./rbc-fees-agent/
COPY healthcare-agent/ ./healthcare-agent/
COPY langgraph.json .

# Create data directory for persistent storage
RUN mkdir -p /app/data

# Expose LangGraph dev server port (default: 2024)
EXPOSE 2024

# Health check (use /docs endpoint instead of / which doesn't exist)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:2024/docs || exit 1

# Run LangGraph development server
CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "2024"]

