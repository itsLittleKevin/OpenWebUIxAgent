#!/bin/bash
# =============================================================================
# Ollama Entrypoint Script for ClusterX AI
# Starts Ollama server and pre-pulls configured models
# =============================================================================

set -e

echo "=== ClusterX AI Ollama Instance ==="
echo "Starting Ollama server..."

# Start Ollama server in background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
MAX_RETRIES=30
RETRY_COUNT=0
while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Ollama failed to start within timeout"
        exit 1
    fi
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES..."
done
echo "Ollama server is ready!"

# Pre-pull models if specified
if [ -n "$OLLAMA_PRELOAD_MODELS" ]; then
    echo ""
    echo "=== Pre-loading Models ==="
    for model in $OLLAMA_PRELOAD_MODELS; do
        echo "Checking model: $model"
        # Check if model already exists
        if ollama list | grep -q "$model"; then
            echo "  Model $model already exists, skipping..."
        else
            echo "  Pulling model $model (this may take a while)..."
            ollama pull "$model"
            echo "  Model $model pulled successfully!"
        fi
    done
    echo "=== All models ready ==="
fi

echo ""
echo "Ollama is now serving at http://0.0.0.0:11434"
echo "Press Ctrl+C to stop"

# Keep the container running by waiting on Ollama
wait $OLLAMA_PID
