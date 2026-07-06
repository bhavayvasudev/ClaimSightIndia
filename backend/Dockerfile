FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

EXPOSE 8000

# Shell form so $PORT (injected by the hosting provider) is expanded at
# container start; falls back to 8000 when unset (e.g. local `docker run`).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
