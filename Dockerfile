FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r celeryuser && useradd -r -g celeryuser celeryuser

WORKDIR /app

COPY requirements/production.txt requirements/production.txt

RUN pip install --no-cache-dir -r requirements/production.txt

COPY . .

# Set proper permissions
RUN chown -R celeryuser:celeryuser /app

# Switch to non-root user
USER celeryuser

# Create matplotlib config directory and set environment variable
ENV MPLCONFIGDIR=/tmp/matplotlib

CMD ["celery", "-A", "backend.api.celery.worker", "worker", "--loglevel=info", "-Q", "analysis,rag,agent", "--concurrency=1"]
