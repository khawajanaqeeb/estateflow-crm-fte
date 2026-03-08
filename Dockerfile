FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default: run the API server
# Override with command in docker-compose / k8s for the worker
CMD ["uvicorn", "production.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
