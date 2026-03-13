#!/bin/sh

echo "=== Railway Startup Script ==="
echo "Checking ChromaDB directory..."

# Check if chroma_db exists and has content
if [ -d "/app/data/chroma_db" ]; then
    CHROMA_FILES=$(find /app/data/chroma_db -type f 2>/dev/null | wc -l)
    echo "ChromaDB directory exists with $CHROMA_FILES files"
else
    echo "ChromaDB directory does not exist"
    CHROMA_FILES=0
fi

# Always build index if no files found
if [ "$CHROMA_FILES" -eq 0 ]; then
    echo "Building knowledge index..."
    python scripts/build_knowledge_index.py
    if [ $? -eq 0 ]; then
        echo "Knowledge index built successfully"
    else
        echo "ERROR: Failed to build knowledge index"
    fi
else
    echo "Knowledge index already exists, skipping build"
fi

echo "Starting application..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}"
