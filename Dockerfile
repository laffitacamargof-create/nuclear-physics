# QCOL Quantum App Studio -- connector image
#
# Runs qcol_app_studio_connector.py (NOT qcol/api.py directly -- the
# connector adds the GitHub-inspection endpoints, catalog caching, and the
# health/repository endpoints the frontend actually calls). The nested
# qcol-app-studio-backend/qcol package is copied in so _load_qcol() finds
# it at the default QCOL_PROJECT_ROOT path.
#
# Render (and most container hosts) assign a dynamic port via the PORT
# environment variable -- this image reads it at container start rather
# than hardcoding 7860 (that fixed port only matters for Hugging Face
# Spaces specifically, which this Dockerfile does not target).

FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user ./qcol-app-studio-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=user ./qcol_app_studio_connector.py /app/qcol_app_studio_connector.py
COPY --chown=user ./qcol-app-studio-backend /app/qcol-app-studio-backend

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    QCOL_PROJECT_ROOT=/app/qcol-app-studio-backend

# Shell form so $PORT expands; Render sets this at runtime and it varies
# between deploys, so it cannot be baked in as a fixed EXPOSE/CMD value.
CMD uvicorn qcol_app_studio_connector:app --host 0.0.0.0 --port ${PORT:-8000}
