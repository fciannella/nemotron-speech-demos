# Dockerfile for Pipecat Backend

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
# WebRTC (aiortc) requires FFmpeg and related libraries
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    unzip \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Note: The pipecat package is installed from local directory with extras
COPY pipecat/ ./pipecat/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY pipeline_modern.py .
COPY langgraph_llm_service.py .
COPY audio_contexts/ ./audio_contexts/

# Copy env.example as reference (actual .env should be mounted or passed as env vars)
COPY env.example .

# Expose the FastAPI port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run the application directly
CMD ["python", "pipeline_modern.py"]

