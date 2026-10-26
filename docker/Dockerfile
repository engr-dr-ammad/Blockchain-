FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for RocksDB
RUN apt-get update && apt-get install -y \
    build-essential \
    librocksdb-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY config/ config/

# Create data directory
RUN mkdir -p /data

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

# Default environment
ENV NODE_ID=node-1
ENV NODE_PORT=8001
ENV DB_PATH=/data
ENV LOG_LEVEL=INFO

# Run node
CMD ["python", "-m", "src.node.main"]
