# Multi-stage Python build for Criticality Monitor services
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

# Copy the application code
COPY cm_modular/ ./cm_modular/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/cm_logs /app/site /app/config /app/logs

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check script
COPY deployment/healthcheck.py /app/healthcheck.py

# Default command (will be overridden in docker-compose)
CMD ["python", "--version"]