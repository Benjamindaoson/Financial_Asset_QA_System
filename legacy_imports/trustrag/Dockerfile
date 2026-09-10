FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
COPY requirements/ ./requirements/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY trust_rag/ ./trust_rag/
COPY init_artifacts.py .
COPY artifacts/ ./artifacts/
COPY demo_data/ ./demo_data/

# Initialize artifacts if needed
RUN python init_artifacts.py

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "trust_rag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
