# Debian (glibc) base: sherpa-onnx publishes aarch64/amd64 wheels for glibc, not for Alpine/musl
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY app/ /app/
# The model is downloaded on first start into /data/models (kept across restarts and updates)
CMD ["python", "/app/edgestt_server.py"]
