# Debian-based Python image: onnxruntime / tokenizers publish wheels for glibc (the HA base images are Alpine/musl)
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 EDGE_APP=/app
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
# app/ = edgedecision package + bundles/6L + data/ (assembled by scripts/make_addon.ps1)
COPY app/ /app/
CMD ["python", "-m", "edgedecision.addon"]
