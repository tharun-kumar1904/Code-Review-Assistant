FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (shared with backend)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (workers need access to services)
COPY backend/ ./backend/
COPY workers/ ./workers/

# Add backend to Python path
ENV PYTHONPATH=/app/backend:/app

CMD ["celery", "-A", "workers.celery_app:celery", "worker", "--loglevel=info", "--concurrency=4", "-Q", "code_review"]
