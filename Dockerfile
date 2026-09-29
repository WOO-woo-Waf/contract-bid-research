FROM python:3.10-slim-bookworm@sha256:802b8b85b6aa755fdbbe99e579e8b6eda6f64b621a7ba99669171935aa78b7e0

ARG BUN_VERSION=1.3.14
ARG GBRAIN_REPOSITORY_URL=https://github.com/garrytan/gbrain.git
ARG GBRAIN_COMMIT=3fafb69b077e602e1286af9cb092ed94455657a8

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-x64.zip" -o /tmp/bun.zip \
    && unzip -q /tmp/bun.zip -d /tmp/bun \
    && install -m 0755 /tmp/bun/bun-linux-x64/bun /usr/local/bin/bun \
    && rm -rf /tmp/bun /tmp/bun.zip

RUN git clone --filter=blob:none "${GBRAIN_REPOSITORY_URL}" /opt/gbrain \
    && git -C /opt/gbrain checkout "${GBRAIN_COMMIT}" \
    && git config --system --add safe.directory /opt/gbrain \
    && cd /opt/gbrain \
    && bun install --frozen-lockfile

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GBRAIN_REPOSITORY=/opt/gbrain

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
RUN python -m pip install .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data /artifacts \
    && chown -R appuser:appuser /data /artifacts

USER appuser

ENV CONTRACT_BID_DATA_ROOT=/data \
    CONTRACT_BID_ARTIFACTS_ROOT=/artifacts \
    CONTRACT_BID_KNOWLEDGE_DB=/data/knowledge.sqlite3

ENTRYPOINT ["contract-bid-infra"]
CMD ["config-check"]
