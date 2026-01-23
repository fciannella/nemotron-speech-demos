#!/bin/bash

# Sync Pipecat Nemotron Demo to Remote Server
# This script syncs your local project to the remote server

set -e

# Configuration
REMOTE_SERVER="nvidia@10.110.96.94"
REMOTE_DIR="/home/nvidia/nemotron-speech-demos"
LOCAL_DIR="/home/fciannella/PycharmProjects/pipecat-nemotron-demos"

echo "=========================================="
echo "Syncing to Remote Server"
echo "=========================================="
echo "Local:  $LOCAL_DIR"
echo "Remote: $REMOTE_SERVER:$REMOTE_DIR"
echo ""

# Test SSH connection first
echo "Testing SSH connection..."
if ! ssh -q "$REMOTE_SERVER" exit; then
    echo "❌ Error: Cannot connect to $REMOTE_SERVER"
    echo "Please check:"
    echo "  1. SSH is configured correctly"
    echo "  2. You have access to the remote server"
    echo "  3. Your SSH key is added (ssh-add)"
    exit 1
fi
echo "✅ SSH connection successful"
echo ""

# Ask for confirmation
read -p "Do you want to proceed with the sync? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Sync cancelled."
    exit 0
fi

echo ""
echo "Starting sync..."
echo ""

# Perform rsync
rsync -avz --progress \
  --exclude='.git/' \
  --exclude='.gitignore' \
  --exclude='__pycache__/' \
  --exclude='*.py[cod]' \
  --exclude='*.so' \
  --exclude='.Python' \
  --exclude='*.egg-info/' \
  --exclude='venv/' \
  --exclude='env/' \
  --exclude='ENV/' \
  --exclude='.venv/' \
  --exclude='node_modules/' \
  --exclude='dist/' \
  --exclude='build/' \
  --exclude='.idea/' \
  --exclude='.vscode/' \
  --exclude='*.iml' \
  --exclude='*.iws' \
  --exclude='.env.local' \
  --exclude='.env.*.local' \
  --exclude='*.log' \
  --exclude='logs/' \
  --exclude='.DS_Store' \
  --exclude='Thumbs.db' \
  --exclude='.coverage' \
  --exclude='.pytest_cache/' \
  --exclude='.hypothesis/' \
  --exclude='htmlcov/' \
  --exclude='.tox/' \
  --exclude='.nox/' \
  --exclude='tests/' \
  --exclude='archived/' \
  --exclude='audio_contexts/' \
  --exclude='docs/' \
  --exclude='*.egg' \
  --exclude='.ipynb_checkpoints/' \
  --exclude='.mypy_cache/' \
  --exclude='ui/dist/' \
  --exclude='pipecat/.git/' \
  --exclude='agents/.langgraph_api/' \
  --exclude='test-ui/' \
  "$LOCAL_DIR/" \
  "$REMOTE_SERVER:$REMOTE_DIR/"

echo ""
echo "✅ Sync completed successfully!"
echo ""
echo "Next steps on the remote server:"
echo "  1. SSH to the server: ssh $REMOTE_SERVER"
echo "  2. Navigate to the directory: cd $REMOTE_DIR"
echo "  3. Set up your .env file with VITE_API_BASE_URL"
echo "  4. Build and start: docker compose up --build -d"
echo ""

