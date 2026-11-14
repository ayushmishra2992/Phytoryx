# PHYTORYX backend image: FastAPI (v1 + /v2 routes) + both ViT checkpoints, CPU inference only.
# Target: >= 4 GB RAM and >= 2 vCPU (measured: ~1.5 GB working set / ~2.5 GB committed; see docs/DOCKER.md).
#
# BUILD PREREQUISITE: the model weights are Git LFS files. Run `git lfs pull` BEFORE `docker build`, otherwise the build context contains
# ~130-byte pointer files; the guard below then fails the build instead of producing a broken image.
#
# No secrets are baked in: OPENAQ_API_KEY and every other setting are supplied at RUN time (docker run -e ...). See .env.example.
# STATUS: built and smoke-tested on 2026-11-14 with Docker Engine 29.1.3 (legacy builder, WSL2 Ubuntu 24.04); results in docs/DOCKER.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PORT=7860 PHYLLO_LOAD_AQI_MODEL=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false

WORKDIR /app

# Same torch/torchvision versions the project was tested with (CPU wheels; verified to exist for cp312 manylinux x86_64 on 2026-11-14).
RUN pip install "torch==2.14.1" "torchvision==0.29.1" --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

# Hugging Face Spaces and many PaaS run containers as uid 1000 (files are only read at runtime; uploads are processed in memory).
RUN useradd -m -u 1000 app
COPY --chown=1000:1000 phyllo ./phyllo
COPY --chown=1000:1000 phyllo_v2 ./phyllo_v2
COPY --chown=1000:1000 api ./api
COPY --chown=1000:1000 models ./models
COPY --chown=1000:1000 artifacts ./artifacts
COPY --chown=1000:1000 results ./results
# Only the legacy AQI regressor is needed at runtime (the rest of legacy/results contains local absolute paths and is not shipped).
COPY --chown=1000:1000 legacy/results/aqi_regression/aqi_ridge_model.joblib ./legacy/results/aqi_regression/aqi_ridge_model.joblib
COPY --chown=1000:1000 docs/MODEL_CARD.md ./docs/MODEL_CARD.md

# Fail the build loudly if the weights are Git LFS pointer files (or missing).
RUN python -c "import os,sys; bad=[(p,os.path.getsize(p) if os.path.exists(p) else -1) for p in ('models/vit_phyllotaxy_4class/model.safetensors','models/vit_phyllotaxy/model.safetensors') if not os.path.exists(p) or os.path.getsize(p)<50_000_000]; sys.exit('Model weights missing or still Git LFS pointers %s - run git lfs pull before docker build' % bad) if bad else print('model weights present')"

# Matplotlib (pulled in by scikit-image) wants a writable config dir; /tmp works with a read-only root filesystem (docker run --read-only --tmpfs /tmp).
ENV MPLCONFIGDIR=/tmp/matplotlib
USER app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7860')+'/health', timeout=4)"
# PHYTORYX API = v1 routes + /v2 routes (api.v2_app). Single worker: the rate limiter and the models are per process.
CMD ["sh", "-c", "exec uvicorn api.v2_app:app --host 0.0.0.0 --port ${PORT}"]
