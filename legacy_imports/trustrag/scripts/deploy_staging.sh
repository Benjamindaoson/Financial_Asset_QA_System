#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 TrustRAG Staging Deployment Script"
echo "=========================================================="

# Ensure we're in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Ensure artifacts directory structure exists
mkdir -p artifacts/monitoring
mkdir -p artifacts/canonical_facts
mkdir -p artifacts/ingestion

# Create a staging config override to use the docker services
echo "-> Creating staging config override (config_staging.json)..."
cat << 'EOF' > config_staging.json
{
  "database": {
    "host": "postgres",
    "port": 5432,
    "user": "trust_rag",
    "password": "password",
    "database": "trust_rag"
  },
  "embedding": {
    "provider": "bge",
    "model_name": "BAAI/bge-m3",
    "dimension": 1024
  },
  "rerank": {
    "enabled": true,
    "model_name": "BAAI/bge-reranker-v2-gemma"
  }
}
EOF

echo "-> Building Docker images..."
docker-compose build

echo "-> Stopping existing staging services..."
TRUSTRAG_ENV=staging docker-compose down

echo "-> Starting staging services..."
TRUSTRAG_ENV=staging docker-compose up -d

echo ""
echo "✅ Staging deployment initiated successfully."
echo "Wait a few moments for the database to initialize and the API to become healthy."
echo ""
echo "Useful Commands:"
echo " - Monitor logs: docker-compose logs -f"
echo " - Check status: docker-compose ps"
echo " - Run load test: python scripts/load_test.py"
echo "=========================================================="
