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
# F-4 / C-6: the container must be able to FIND the OAuth client secret, whose
# documented path is config/google_oauth_client.json (src/config.py) — pre-F-4
# this image had no config path at all and could never authenticate. Only the
# tracked, non-secret whitelist is baked in: the OAuth client JSON is a RUNTIME
# MOUNT (compose), because an image layer keeps a copy forever and CLAUDE.md
# §2.2 forbids committing OAuth client credentials anywhere at all.
COPY config/whitelist.json /app/config/whitelist.json
# RAG mirror source (audit 2026-09-14): VaultIndex reads the vault, so the
# boot mirror needs the repo's 04_Resources/ inside the image.
COPY 04_Resources/ 04_Resources/
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
