# The backend image: the same image runs in development, staging and
# production; only its environment differs (docs/ARCHITECTURE_ASSESSMENT.md §11).
# Build from the repository root:  docker build -f backend/Dockerfile -t gnosis-api .
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd --create-home --uid 10001 gnosis
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
# the shared domain package (pure modules; the backend imports nothing else from it) and the backend
COPY coach/ coach/
COPY backend/ backend/
WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app
USER gnosis
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
# migrations run as a separate step (infra/compose.yaml "migrate"), never implicitly on start
CMD ["uvicorn", "gnosis.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
