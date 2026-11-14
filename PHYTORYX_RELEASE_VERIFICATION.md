# PHYTORYX 1.0 — release verification

*Intelligence Rooted in Nature.* Verification date 2026-11-14. Windows 11, RTX 3050 4 GB, Node 24.21.0, Python 3.12. Test labels: **REAL** = real images/files/HTTP · **SYNTHETIC** = generated parser input · **MOCK** = mocked service · **LIVE** = real network call.

The ZIP's SHA-256 and size are in the release notes and the `.sha256` sidecar (an archive cannot contain its own hash). The released ZIP is the verified tree plus this file.

## Gate 1 — freeze of the pre-rename build (Phyllo-ViT 2.0 code, fresh extraction + `INSTALL.bat`)
PASS: `pip check` clean; v1 12/13 + 1 SKIP; v2 26/27 + 1 SKIP (incl. LIVE Open-Meteo); `check_classes.py`; PlantDoc unfamiliar-image evaluation (236 images); frontend build; both model hashes identical to v1.0.1; `RUN_V2.bat` live workflow (real upload + FTIR + location → live modelled air quality). The SKIPs are the Not_a_leaf checks, whose COCO images are intentionally absent from the public package. Rebranding started only after this gate passed. Two small code changes followed it (leaf-like images re-worded as `Unknown/Uncertain` now also get measurements; richer HTML report) and the full suite was re-run below.

## Gate 2 — the PHYTORYX 1.0 package (fresh extraction `C:\pvfinalx`, own `.venv`, `INSTALL.bat`)
| # | Verification | Result |
|---|---|---|
| 1 | Package contents (1,301 entries) | PASS — no `.venv`, `node_modules`, `.next`, `__pycache__`, `.git`, `.env`, `.env.local`, `AGENTS.md`, or COCO Not_a_leaf folders. |
| 2 | `INSTALL.bat` | PASS — completed; torch 2.14.1+cu126 with CUDA; `pip check`: no broken requirements; `npm ci`: 0 vulnerabilities. |
| 3 | Model hashes | PASS — both `model.safetensors` identical to the v1.0.1 release. |
| 4 | **Public form** v1 tests | 12/13 PASS, **1 SKIP** (non-leaf: COCO images not shipped). |
| 5 | **Public form** v2 tests | 26/27 PASS, **1 SKIP** (REAL non-leaf), 0 failed — includes SYNTHETIC/REAL FTIR parsing, MOCK OpenAQ and Open-Meteo, **LIVE Open-Meteo** (current value + a historical hour), REAL held-out leaves, REAL unfamiliar leaves (PlantDoc sample), invalid uploads, CORS. |
| 6 | **Public form** `check_classes.py` | Alternate 0.988, Opposite 0.988, Whorled 0.980 ACCEPT/PASS; Not_a_leaf **NOT TESTED** (images absent); overall "PASS (NOT TESTED: Not_a_leaf)". |
| 7 | **Full-data run** (local COCO images copied into the scratch copy only; not part of the release) | v1 13/13, v2 27/27, `check_classes.py` all four classes PASS (Not_a_leaf 0.925 NOT_A_LEAF). So non-leaf rejection is verified, but only with local data. |
| 8 | Unfamiliar-image evaluation (`scripts/ood_familiarity_eval.py`, PlantDoc test split, 236 real leaf photos of other species) | 0 accepted; 154 `NOT_A_LEAF` (65.3 %), 80 `ABSTAIN_UNFAMILIAR` (33.9 %), 2 `REJECT_QUALITY` (0.8 %). No labels exist for phyllotaxy, so no accuracy is claimed. The v2 layer re-words leaf-like `NOT_A_LEAF` verdicts as `Unknown/Uncertain` with retake guidance and a caution. |
| 9 | Frontend production build | PASS — routes `/`, `/lab`, `/v2`. Warning: React 18 deprecated in Next.js 16 (unchanged). |
| 10 | `RUN_V2.bat` live run (only my process tree stopped; ports 3000/8000 free before and after) | PASS — backend healthy ~9 s; `/v2` 200; landing page, built-in UI and `/v2` show PHYTORYX and the tagline with no old name; API title "PHYTORYX". Real upload of an unfamiliar leaf + FTIR file + location from origin `:3000`: `Unknown/Uncertain` (ABSTAIN_UNFAMILIAR), 3 guidance items, morphology AVAILABLE, visible condition EXPERIMENTAL, **modelled air quality AVAILABLE (LIVE, 2026-03-01T17:00)**, measured air quality USER_INPUT_REQUIRED (no key), FTIR AVAILABLE (12 peaks), species/dust/leaf-AQI NOT_SUPPORTED, biological DISABLED. A familiar leaf → Whorled 0.980; text upload → 400; CORS allowed for `:3000`. |
| 11 | Report generation (`reportHtml`, run in Node on a REAL API response) | PASS — contains all modules, probabilities, guidance, modelled readings and FTIR peaks; no `undefined`/`NaN`. |
| 12 | Windows scripts | PASS — all `.bat` files have consistent CRLF; `INSTALL.bat`/`RUN*.bat` show the PHYTORYX banner; `INSTALL.bat` and `RUN_V2.bat` executed. |
| 13 | Encoding hygiene | PASS — scan of source/docs for mojibake or BOM: none. |

## Defect found and fixed during this work
Earlier scripted edits (`Get-Content`/`Set-Content`) corrupted non-ASCII characters in `CLAUDE.md` and `README.md` (and `µg/m³` in `environment.py`, caught by a failing test). `CLAUDE.md` and `README.md` were also affected in the published *Phyllo-ViT* v1.0.1 tag in the old repository, which was deliberately not modified; the PHYTORYX repository has the repaired files.

## NOT verified
- **Live OpenAQ retrieval** (needs an API key; MOCK only). Modelled air quality (Open-Meteo/CAMS) **is** live-verified but is modelled, not measured.
- Non-leaf rejection **in the public package** (SKIPPED); it was verified only with local images (row 7).
- A real-browser click-through of the dashboard and an actual file download from the browser (the report generator was run in Node; pages were fetched over HTTP).
- Docker image; macOS/Linux; the `PUSH_TO_GITHUB.bat` helper was removed from this package.
- Morphology / visible-condition quality against labelled data (no labels exist).

## Limitations (scientific)
Image→AQI has no demonstrated skill (46 pairs, p = 0.45) and is withheld; phyllotaxy was validated only on a small held-out set from the training collection (colour-only shortcut 95.6 %; 10/65 test images have near-duplicates in train/val); Not_a_leaf ≠ complete OOD detection and 65 % of real unseen leaves are called "not a leaf"; species, Spiral, dust masks, a trained health model, fusion and bacterial/fungal analysis do not exist for lack of verified labelled data; FTIR band ranges are indicative; modelled air quality is not a measurement and its free tier is non-commercial. Dataset licences: `v2/data_registry/DATASET_SOURCES.md` — the COCO images are not redistributed, and the project leaf photographs have no recorded licence (owner to confirm).

## Verdict
All executed checks passed; every skipped or unverified item is listed above. **PHYTORYX 1.0 is release-ready as a transparent, limited research platform.**
