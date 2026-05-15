FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install 'fastapi>=0.115' 'uvicorn>=0.32' 'psycopg[binary,pool]>=3.2' 'httpx>=0.27'

COPY src/ ./src/
RUN pip install --no-deps -e .

EXPOSE 8000

CMD ["uvicorn", "receiver.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
