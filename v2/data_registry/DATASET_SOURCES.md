# PHYTORYX — dataset sources and licences (checked 2026-11-14)

Rule: an entry is **verified** only if its licence was read from the original source in this session. Nothing is assumed from memory. Machine-readable version: [`dataset_registry.csv`](dataset_registry.csv). Full citations: [`../../CITATIONS.md`](../../CITATIONS.md).

## Acquired / included
| Dataset | Licence | Samples | Use in PHYTORYX |
|---|---|---|---|
| [PlantDoc](https://github.com/pratikkayal/PlantDoc-Dataset) test split | **CC BY 4.0** (LICENSE.txt read) | 236 images, 27 folders (12 in the repo, all 236 in the dataset archive; SHA-256 manifest) | Real **unfamiliar-leaf** test set (other species, field photos). No phyllotaxy labels. |
| [Cannabis sativa leaf IR spectra, Zenodo 17165736](https://zenodo.org/records/17165736) | **CC BY 4.0**, open | 2 of 19 files (`W1_C.xlsx`: 8 spectra × 7,468 points; codification file); MD5 verified | Real leaf spectra to test the FTIR parser/viewer. Not pollution data; not paired with images or AQI. |
| Project leaf photographs (Alternate/Opposite/Whorled) | **Not recorded — project owner to confirm** | 265 unique images | Training/evaluation of the phyllotaxy model. Species/plant/date/location fields are unfilled. |

Format quirks of the Zenodo file (found by inspection, not stated on the record): wavenumbers are integers ×1000 (4000123 → 4000.123 cm⁻¹, inferred from a 0.482 cm⁻¹ step and an end value of 400.157) and absorbance uses comma decimals; the parser accepts `wavenumber_scale=1000`.

## Integrated live services (no data stored)
- **Open-Meteo Air Quality API** — **CC BY 4.0**, no key, **free use non-commercial only**, attribution to the CAMS ENSEMBLE data provider and Open-Meteo required. Values are **modelled** (CAMS; ~11 km Europe / ~45 km global), not station measurements. Live-tested 2026-11-14 (current and a historical hour).
- **OpenAQ v3** — licences are per source (exposed by the API); free API key required; 60 requests/min, 2,000/hour. CPCB is not mentioned on the pages read, so licences must be read per location at run time. **Live retrieval was not verified (no key)**; mock-tested only.

## Used internally, not redistributed
- **COCO 2017 images** as the Not_a_leaf class (150 images). The Terms of Use text could not be retrieved, so the image licences are unverified; the images are **not** included in this repository, ZIP or dataset archive. Not_a_leaf checks are therefore SKIPPED / NOT TESTED in the public package and the experiments need local images.

## Registered, not acquired
- **PlantVillage** — no licence found on the GitHub README or TFDS page read; do not use until confirmed.
- **Latvian herbal FTIR-ATR (Zenodo 16892975)** — CC BY 4.0 but files are access-restricted and the samples are powdered herbs; needs a manual access request (not bypassed).

## Not verified / not found
Roboflow `phyllotaxie_` (HTTP 403 to the automated fetch — open in a browser), Spiral phyllotaxy (none found), species identification (none verified), dust-deposition masks (none found), CPCB portal terms and bacterial/fungal laboratory datasets (not investigated).

## Consequences
Phyllotaxy keeps its 4 classes; species, Spiral, dust, leaf-image AQI and biological modules are disclosed as unsupported/disabled; no multimodal fusion is attempted (no genuinely paired image + FTIR + pollution records exist).
