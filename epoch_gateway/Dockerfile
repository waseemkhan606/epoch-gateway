# EPOCH gateway — epoch-api:v1, built for linux/amd64 (Cloud Run runs amd64
# only). Slim Python base, non-root `epoch` user, uvicorn on :8000.
#
# Build from the REPO ROOT so the COPY paths resolve:
#   docker buildx build --platform linux/amd64 -f epoch_gateway/Dockerfile -t epoch-api:v1 .
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# deps first, for layer caching
COPY epoch_gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -g 1000 epoch \
    && useradd -u 1000 -g epoch -s /bin/bash -m epoch

COPY epoch_gateway/ ./epoch_gateway/
RUN chown -R epoch:epoch /app

USER epoch
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "epoch_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
