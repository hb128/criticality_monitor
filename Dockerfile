FROM python:3.11-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium || echo "Playwright install skipped"

COPY cm_modular/ ./cm_modular/
COPY scripts/ ./scripts/

RUN mkdir -p /app/cm_logs /app/site /app/config /app/logs

ENV PYTHONPATH=/app

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

CMD ["python", "--version"]