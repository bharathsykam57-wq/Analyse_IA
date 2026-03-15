FROM python:3.11

WORKDIR /app

COPY requirements/production.txt requirements/production.txt

RUN pip install --no-cache-dir -r requirements/production.txt

COPY . .

CMD ["celery", "-A", "backend.api.celery.worker", "worker", "--loglevel=info", "-Q", "analysis,rag,agent", "--concurrency=1"]
