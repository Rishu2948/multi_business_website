# AI Catalog Chatbot — production Docker image
#
# Build context: ai-chatbot/
# Run:
#   docker build -t ai-chatbot .
#   docker run -p 8001:8001 --env-file .env ai-chatbot

FROM python:3.11-slim

# Install CA certs (needed for HTTPS calls to LLM APIs and MongoDB Atlas)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8001

# Health check — matches the GET /chat/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8001/chat/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
