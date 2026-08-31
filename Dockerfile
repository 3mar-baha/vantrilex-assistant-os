FROM python:3.12-slim

# ffmpeg: voice pipeline. Node 24 via NodeSource: the OmniRoute gateway is an
# npm application whose engines demand node >=22.22 — Debian's stock nodejs is
# far older, so the gateway child could never start without this layer (v1.0.1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY common/ common/
COPY scripts/omniroute/ scripts/omniroute/
COPY scripts/supervise.py scripts/supervise.py

# The vendored clone pins the gateway version (RUNBOOK §4 step 2); installing it
# globally exposes the `omniroute` binary on PATH for OMNIROUTE_CMD.
RUN npm install -g /app/scripts/omniroute

RUN useradd --system --home /app sara && chown -R sara /app

USER sara

ENV TZ=Asia/Amman
ENV OMNIROUTE_CMD="omniroute run"

# HF Spaces / any container host: the container listens on $PORT (app_port in the
# README metadata / ORACLE guide). The core child reads $PORT and serves /health +
# the bridge WSS on it; scripts/supervise.py runs OmniRoute + core as ONE process
# tree (first exit wins).
CMD ["python", "scripts/supervise.py"]
