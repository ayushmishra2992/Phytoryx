# PHYTORYX

**Intelligence Rooted in Nature.**

Reliability-aware leaf analysis: phyllotaxy recognition (Alternate / Opposite / Whorled / Not_a_leaf) with calibrated abstention, an experimental visible-condition view, optional FTIR spectrum analysis, location-aware air-quality context, and an evidence audit of leaf-photo AQI claims. Every module states plainly what it can and cannot tell you.

> PHYTORYX was developed as *Phyllo-ViT* (Bennett University, B.Tech CSE final-year research project; Ayush Mishra — ML/backend, Riya Katiyar — literature/frontend/docs). The reference paper's own method is also named "Phyllo-ViT"; this project audits that paper's claims. Python package names (`phyllo`, `phyllo_v2`) and `PHYLLO_*` environment variables keep their original names.

## What it is, and what it is not
A reference paper proposes predicting street-level AQI from roadside leaf photographs, FTIR spectra and CPCB readings. PHYTORYX (1) classifies phyllotaxy **and knows when not to answer**, and (2) **audits** the paper's image→AQI claims on the data supplied with it: no model beats the mean (46 verified pairs, permutation p = 0.45), so leaf-photo AQI is **withheld**. A leaf photograph cannot measure AQI, PM2.5, chemical composition or microbes, and PHYTORYX never claims so.

## Modules and status
| Module | Status | Basis |
|---|---|---|
| Phyllotaxy (Alternate / Opposite / Whorled / Not_a_leaf; `Unknown/Uncertain` on abstention) | **Available** | Fine-tuned ViT-B/16, temperature-calibrated, Mahalanobis + kNN out-of-distribution abstention |
| Unfamiliar-image handling | **Available** | On 236 real leaf photos of other species (PlantDoc), **0 were accepted** (65% `NOT_A_LEAF`, 34% `ABSTAIN_UNFAMILIAR`, 1% quality-rejected); leaf-like images are re-worded as `Unknown/Uncertain` with retake guidance |
| Morphology (area fraction, aspect ratio, solidity, eccentricity) | **Available** (pixel space) | Classical segmentation; no physical scale |
| Visible leaf condition (yellowish / brownish / dark fractions) | **Experimental** | Colour heuristics, not validated against labels |
| FTIR (CSV/TSV/TXT, XLSX, JCAMP-DX) | **Available for user-supplied spectra** | Smoothing, peak detection, *indicative* group ranges; no pollutant attribution |
| Modelled air quality (Open-Meteo / CAMS) | **Available** (live-tested) | Modelled, not measured; CC BY 4.0, non-commercial use |
| Measured air quality (OpenAQ) | **Available when configured** | Needs a free `OPENAQ_API_KEY`; **live retrieval unverified**, mock-tested only |
| Species, Spiral, dust/deposition, leaf-image AQI | **Not supported** | No verified labelled data / no demonstrated skill |
| Bacterial / fungal analysis | **Disabled** | Cannot be determined from RGB photographs |
| Multimodal fusion | **Not built** | No genuinely paired image + FTIR + pollution records |

## Architecture
```
photo -> quality gate -> ViT-B/16 (4-class) -> temperature calibration -> OOD check -> decision (ACCEPT / ABSTAIN_* / NOT_A_LEAF / REJECT_QUALITY)
      -> attention-rollout heatmap
v2 layer: leaf-like check + guidance, morphology, visible condition, FTIR, modelled + measured air quality, status-per-module report
```
Stack: Python 3.12 · PyTorch (CUDA 12.6 build; CPU works) · Transformers 5.18 · scikit-learn · FastAPI/Uvicorn · Next.js 16 / React 18 / TypeScript / Tailwind · Git LFS for weights.

## Models
`models/vit_phyllotaxy_4class` (deployed classifier) and `models/vit_phyllotaxy` (original 3-class model whose embedding space the AQI regressor uses — do not replace). Stored with Git LFS (install `git-lfs` before cloning).

## Install and run (Windows)
Keep the path short (260-character limit). Needs Python 3.12; Node.js ≥ 20.9 for the web UI.
1. `INSTALL.bat` — creates `.venv`, installs PyTorch + requirements (~4 GB, 10–20 min), runs `npm ci`.
2. `RUN_V2.bat` — backend at http://127.0.0.1:8000 (API docs `/docs`, built-in v1 UI `/`) and the PHYTORYX dashboard at http://localhost:3000/v2. `RUN.bat`/`RUN_ME.bat` start the v1 views.
3. `RUN_TESTS.bat` (v1) · `RUN_TESTS_V2.bat` (v1 + v2) · `CHECK_CLASSES.bat` · `PACKAGE_FINAL.bat`.

Configuration (`.env.example`): `OPENAQ_API_KEY` (optional, measured stations), `PHYLLO_CORS_ORIGINS`, `PHYLLO_LOAD_AQI_MODEL`, frontend `NEXT_PUBLIC_API_URL`.

## API
`POST /v2/analyze` (multipart: `file`, optional `lat`, `lon`, `collected_at`, `ftir_file`, `ftir_y_units`, `ftir_wavenumber_scale`) · `POST /v2/ftir/analyse` · `GET /v2/modules` · v1: `POST /predict`, `POST /aqi/compute` (CPCB formula on *measured* concentrations), `GET /health|/evidence|/model-card`. Every v2 section is `{status, reason, …}` with status ∈ AVAILABLE / EXPERIMENTAL / USER_INPUT_REQUIRED / UNAVAILABLE / NOT_SUPPORTED / DISABLED. Measured readings, modelled estimates, leaf-based estimates and visible-condition indicators are never merged.

## Evaluation (small sets — read with the limitations)
Held-out, deployed pipeline: 64/65 test images correct (Wilson 95% CI 91.8–99.7%); Alternate 13/14 (the miss is abstained), Opposite 13/13, Whorled 15/15, Not_a_leaf 23/23 rejected; with abstention 41/42 leaves accepted, all correct. These images come from the same photo collection as training, so this shows the pipeline works, **not** that it generalises. Unfamiliar-leaf behaviour (above) is a separate real-data test; PlantDoc has no phyllotaxy labels, so no accuracy is claimed there.

## Tests
`tests/run_tests.py` (13 v1 tests) and `tests/run_tests_v2.py` (27 v2 tests; each labelled REAL / SYNTHETIC / MOCK / LIVE). The public package omits the COCO Not_a_leaf images (licence unverified), so the non-leaf checks report **SKIP / NOT TESTED** there; they run in full when the images are present locally. See `PHYTORYX_RELEASE_VERIFICATION.md`.

## Data
See [`v2/data_registry/DATASET_SOURCES.md`](v2/data_registry/DATASET_SOURCES.md), [`dataset_registry.csv`](v2/data_registry/dataset_registry.csv) and [`CITATIONS.md`](CITATIONS.md). Project leaf photographs: 265 unique images, provenance fields (species/plant/date/location) unfilled; rights to be confirmed by the project owner. COCO non-leaf images are used internally and not redistributed. PlantDoc (CC BY 4.0) and one Zenodo FTIR sample (CC BY 4.0) are included with attribution.

## Known limitations
Image→AQI has no demonstrated skill (withheld); matched pairs exist only for Whorled at one site; colour-only shortcut reaches 95.6% and 10 of 65 test images have near-duplicates in train/val; Not_a_leaf ≠ complete OOD detection; a single isolated leaf may not show the nodes that define phyllotaxy; live OpenAQ, a real-browser click-through, and the Docker image are unverified; React 18 is deprecated in Next.js 16 (not upgraded); modelled air quality can differ sharply from street level and its free tier is non-commercial.

## Future scope
Species- and plant-grouped validation once provenance is annotated; genuinely paired image–FTIR–station data (`docs/DATA_COLLECTION_PROTOCOL.md`); Spiral class and species/dust/health models once licensed labelled data exists; CPCB integration; React 19 migration; deployment (`docs/DEPLOY.md`).

## Layout
`api/` FastAPI (+ `v2_app.py`) · `phyllo/` v1 core · `phyllo_v2/` v2 modules · `frontend/` Next.js (`/lab` v1, `/v2` dashboard) · `experiments/` e01–e07 · `artifacts/` · `results/` · `models/` · `data/` · `v2/data_registry/` · `docs/` (incl. `history/` earlier verification reports) · `legacy/` untouched v2 · `tests/`.
