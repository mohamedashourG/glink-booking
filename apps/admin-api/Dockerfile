FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the monorepo root (../..) so we can pull in the workspace
# packages alongside admin-api itself.
RUN pip install --upgrade pip && \
    pip install \
        'fastapi>=0.115' \
        'uvicorn>=0.32' \
        'httpx>=0.27' \
        'pyjwt[crypto]>=2.8' \
        'python-multipart>=0.0.18' \
        'email-validator>=2.0'

COPY packages/shared /app/packages/shared
RUN pip install --no-deps /app/packages/shared

COPY packages/provisioning /app/packages/provisioning
RUN pip install --no-deps /app/packages/provisioning

COPY apps/admin-api /app/admin-api
RUN pip install --no-deps -e /app/admin-api

EXPOSE 8002

CMD ["uvicorn", "admin_api.main:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers"]
