FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY common/ common/
COPY scripts/omniroute/ scripts/omniroute/
COPY scripts/supervise.py scripts/supervise.py

RUN useradd --system --home /app sara && chown -R sara /app

USER sara

ENV TZ=Asia/Amman

# HF Spaces: container must listen on $PORT (Space contract); app_port set in README
# metadata. The core child reads $PORT and serves /health + the bridge WSS on it;
# scripts/supervise.py runs OmniRoute + core as ONE process tree (first exit wins).
CMD ["python", "scripts/supervise.py"]
