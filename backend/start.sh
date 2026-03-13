#!/bin/sh

# Build knowledge index if not exists
if [ ! -d "/app/data/chroma_db" ] || [ -z "$(ls -A /app/data/chroma_db 2>/dev/null)" ]; then
    echo "Building knowledge index..."
    python scripts/build_knowledge_index.py
else
    echo "Knowledge index already exists, skipping build"
fi

# Start the application
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}"
