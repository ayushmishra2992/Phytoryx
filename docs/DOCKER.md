# PHYTORYX — Docker backend (CPU)

**Status: built and tested.** On 2026-11-14 the image was built with Docker Engine 29.1.3 (`docker.io` from Ubuntu 24.04 inside WSL2) and run as a real Linux container with `--cpus=2 --memory=4g --read-only`; results are in section 6 (real container) and 7 (earlier clean-room emulation). Not yet tested: other hosts/kernels, other platforms (arm64), and any hosting provider.

## 1. What the image contains
Python 3.12-slim, CPU `torch==2.14.1` / `torchvision==0.29.1` (the tested versions; Linux x86_64 CPU wheels verified to exist), `requirements.txt` (including `fpdf2` for PDFs), and only: `phyllo/`, `phyllo_v2/`, `api/`, `models/` (both ViT checkpoints, ~655 MB), `artifacts/`, `results/`, the single legacy file `legacy/results/aqi_regression/aqi_ridge_model.joblib`, and `docs/MODEL_CARD.md`. It does **not** contain the frontend, datasets, tests, `.git`, env files, or the rest of `legacy/` (those CSVs hold absolute local paths). No secret or API key is baked in; the app writes nothing to disk (uploads and PDFs are processed in memory). Runs as uid 1000, single uvicorn worker, entry point `api.v2_app:app`.

## 2. Build (needs the real weight files)
The weights are Git LFS files. Without them the build context holds ~130-byte pointer files and the build **fails on purpose** ("Model weights missing or still Git LFS pointers").
```bash
git lfs install
git clone --branch release/1.1.0 https://github.com/ayushmishra2992/Phytoryx.git && cd Phytoryx   # LFS objects download here (~0.65 GiB of the owner's GitHub LFS bandwidth)
git lfs pull                                                                                     # only if you cloned with LFS smudging disabled
docker build -t phytoryx-backend .
```

## 3. Run (all settings at run time)
```bash
docker run --rm -p 7860:7860 --memory=4g --cpus=2 \
  -e PHYLLO_CORS_ORIGINS=https://your-frontend.example \
  -e OPENAQ_API_KEY=*** \
  phytoryx-backend
```
`OPENAQ_API_KEY` is optional (measured air quality only) and must come from your platform's secret store, never from the image or the frontend. Other variables: `PORT` (default 7860), `PHYLLO_LOAD_AQI_MODEL` (0 saves ~350 MB), `PHYLLO_RATE_LIMIT` / `PHYLLO_RATE_WINDOW_S` / `PHYLLO_TRUST_PROXY` (set `PHYLLO_TRUST_PROXY=1` only behind a trusted reverse proxy), `OMP_NUM_THREADS` (default 2). See `.env.example`. A container health check calls `/health` (the first start takes ~20–60 s while the models load).

Frontend: build with `NEXT_PUBLIC_API_URL=https://<backend-host>`; the backend must list that exact origin in `PHYLLO_CORS_ORIGINS` (any `localhost` port is always allowed). Serve both over HTTPS.

## 4. Smoke test (inside the running container's published port)
```bash
curl -s localhost:7860/health                                   # status "healthy", device "cpu"
curl -s "localhost:7860/v2/geocode?q=Gurugram"
curl -s -F file=@leaf.jpg -F place=Gurugram -F "collected_at=2026-03-01 17:00" localhost:7860/v2/analyze -o analysis.json
curl -s -H "Content-Type: application/json" --data-binary @analysis.json -o report.pdf localhost:7860/v2/report/pdf   # starts with %PDF-
docker stats --no-stream                                        # memory
```

## 5. Docker on this machine (installed 2026-11-14 with Option A below, after approval)
**Gotchas found:** (1) Ubuntu 24.04's `docker.io` has no buildx plugin, so `docker build` uses the deprecated *legacy builder* (works; `--progress` is not accepted). (2) **WSL stops its VM when no WSL session is open**, which stops running containers (the first test container exited with code 0 right after startup). Keep a WSL session open while containers run (e.g. a terminal, or `wsl -d Ubuntu -u root -- sleep infinity` in a hidden process), or set `vmIdleTimeout` in `.wslconfig`. (3) Build from the repo directory so the real `.dockerignore` applies (the context is ~0.7 GB because of the weights).
Original findings and options:
Findings (2026-11-14): Windows 11 Home (build 26200), virtualization enabled, hypervisor present, **WSL2 with an Ubuntu 24.04 distro (systemd enabled, 7.4 GB RAM / 12 cores visible, root available)**; no Docker Desktop, no Docker in the distro, not running as Windows admin. Two ways, minimum steps:
- **A. Docker Engine inside the existing WSL distro (no Windows admin needed):**
  `wsl -d Ubuntu -u root -- sh -c "apt-get update && apt-get install -y docker.io git-lfs && systemctl enable --now docker"` (Ubuntu's `docker.io` 28.2.2 was available), then build from `/mnt/c/.../phytoryx` or, faster, from a copy inside the Linux filesystem. Give WSL enough memory (`%USERPROFILE%\.wslconfig`: `[wsl2]` / `memory=6GB` / `processors=2`) if you want to test the 4 GB / 2 vCPU target (`wsl --shutdown` to apply).
- **B. Docker Desktop** (`winget install Docker.DockerDesktop`, needs admin, uses WSL2). Check Docker's current licence terms for your use before installing (not verified here).

## 6. Real container validation (2026-11-14; Docker Engine 29.1.3, WSL2 kernel 6.6.87, cgroup v2)
**Build:** `docker build -t phytoryx-backend .` from the repo (branch `release/1.1.0`, commit `6cc399f` plus the uncommitted Dockerfile/.dockerignore/docs changes) — 21 steps, **477 s** cold (75 s with cached layers), exit 0; the LFS guard printed "model weights present" (weight files verified against their committed LFS pointer SHA-256 first). **Image size: 1.17 GB compressed content, 3.74 GB unpacked on disk** (`docker images`); `pip list` 71 packages; Python 3.12.16, `torch 2.14.1+cpu` (CUDA unavailable), transformers 5.18.0, fastapi 0.142.2, fpdf2 2.9.0. Inside: runs as uid 1000, `/app` not writable, 0 legacy CSVs, 0 files with local paths/personal info, no secrets in image config/history (the `GPG_KEY`/`PYTHON_SHA256` entries come from the public Python base image).
**Run:** `docker run -d --memory=4g --memory-swap=4g --cpus=2 --read-only --tmpfs /tmp -p 7860:7860 -e PHYLLO_CORS_ORIGINS=https://frontend.example phytoryx-backend` (no OpenAQ key).
| Check | Result |
|---|---|
| Startup to healthy (from Windows via the port forward) | **18.1 s** cold, 12.1 s warm; Docker HEALTHCHECK `healthy` after 19 s; models loaded offline in 0.7–0.8 s, no Hub/download lines; CPU used during startup ≈ 14.9 s |
| `/health` | healthy, device `cpu`, cuda false, 4 classes, `nonleaf_probability` 0.9 |
| `/v2/geocode`, `/v2/analyze` (place + time + scale, live geocoding and Open-Meteo), `/v2/report/pdf` | all pass: Gurugram resolved; Whorled 0.98; morphology and modelled air quality available; PDF 55 KB (`%PDF-`) in 0.15 s |
| Legacy `/predict` | 200 in 0.92 s → Whorled, ACCEPT, 0.98 (also `/model-card`, `/evidence`, `/v2/modules` 200; invalid upload 400) |
| Missing OpenAQ key | measured section `USER_INPUT_REQUIRED` with the setup instruction; nothing invented |
| CORS | `https://frontend.example` allowed (preflight incl. `content-type`), `https://evil.example` not |
| Rate limiting (`-e PHYLLO_RATE_LIMIT=3`) | `200, 200, 429, 429` after one prior analyze; `Retry-After` and CORS headers present; `/health` and `/v2/modules` unaffected |
| Runtime-only secret | a dummy `OPENAQ_API_KEY` set with `-e` was used by the app (OpenAQ answered 401) and never appeared in responses, `/health` or logs |
| Persistence | `--read-only` root filesystem enforced and the app ran normally; `docker diff` 0 entries |
| Latency (2 CPUs, `OMP_NUM_THREADS=2`) | `/v2/analyze` without external calls median **1.18 s** (1.16–1.37); with live geocoding + Open-Meteo 4.85 s; `/predict?explain=true` ≈ 1.0–1.2 s |
| CPU | 1.5 of 2.0 cores used on average during sequential requests; idle 0.2 % |
| Memory | cold-cache run (cgroup counts page cache): 871 MB after startup, 1,557 MB after all tests, **peak 1,592 MB of the 4,096 MB limit**. Warm-cache runs (weights memory-mapped, cache charged elsewhere): anonymous memory 375 MB idle → 425 MB after 12 analyses + 3 heatmaps, `memory.peak` 494 MB. The true footprint is ≈ 1.1–1.2 GB (anon + mapped weights), matching the clean-room figure |
| Log hygiene | no tracebacks; after setting `MPLCONFIGDIR=/tmp/matplotlib` the read-only-filesystem Matplotlib warning is gone (the rebuilt image is the one described above) |

## 7. Clean-room validation results (2026-11-14; earlier emulation on Windows, NOT a container)
Method: the Dockerfile's exact COPY set (63 files, 665 MB) in an empty directory, a fresh venv with `torch==2.14.1+cpu`, `torchvision==0.29.1+cpu` and `requirements.txt` (`pip check` clean), a fresh empty Hugging Face cache, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `OMP_NUM_THREADS=2`, run as `uvicorn api.v2_app:app`, on Windows (12-thread CPU).
| Check | Result |
|---|---|
| Startup to healthy | 26 s (19.8 s with `PHYLLO_LOAD_AQI_MODEL=0`); `/health` → healthy, device `cpu`, 4 classes, thresholds incl. `nonleaf_probability` |
| Models load offline, no Hub access | yes; empty HF cache stayed empty; 0 download/traceback lines in the logs |
| Memory (both models) | 1.12 GB working set after load; 1.19 GB (peak 1.22 GB, private 1.26 GB) after 14 analyses incl. heatmaps |
| Memory (`PHYLLO_LOAD_AQI_MODEL=0`) | 0.79 GB after load; 0.83 GB (peak 0.86 GB, private 0.91 GB) after use |
| `/v2/geocode`, `/v2/analyze` with place + time, `/v2/report/pdf` | all pass: Gurugram resolved live; Whorled 0.98; modelled air quality live; PDF 55 KB (`%PDF-`) in 0.10 s |
| `/v2/analyze` latency without external calls | ≈ 0.9 s (OMP_NUM_THREADS=2) |
| v1 `/predict`, `/model-card`, `/evidence`, invalid upload | 200 / 1,930 chars / 200 / 400 |
| CORS for a separate frontend | `PHYLLO_CORS_ORIGINS=https://frontend.example` allowed; `https://evil.example` not |
| Runtime-only configuration | rate limit set by env (`200,200,200,429,429` at limit 3); `OPENAQ_API_KEY` read from the environment at run time (a dummy key reached OpenAQ and was rejected with 401), never echoed in responses or `/health` |
| Uploads/reports persisted? | no: 0 files created or changed in the app directory or cache |
| Baked-in local paths / secrets in the image file set | none (after excluding `legacy/results/*` except the one joblib) |
| Build guard | passes with real weights; fails with a clear message on Git LFS pointer files and on missing files |
Estimated image size ≈ 2.0–2.3 GB uncompressed (base ≈ 0.13 GB + Python packages ≈ 1.2 GB + app/weights 0.67 GB; **an estimate from the Windows environment, not a measurement**). Memory above is lower than the earlier 1.5 GB figure because the earlier run used the CUDA-capable torch build.

## 8. Not verified
Any hosting provider; other CPUs/kernels and arm64; a limit below 4 GB (the measured footprint suggests ≈ 2 GB would work, untested); sustained concurrent load (only sequential requests were measured); real browsers against the container (the browser suite ran against the non-container backend); OpenAQ with a real key. `/health` reports `version` 3.0.0 (the inherited v1 package version), not the product version.
(The earlier "real build/run, cgroup limits, image size, health check" gaps were closed in section 6.)
