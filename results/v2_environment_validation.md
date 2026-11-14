# Environmental data validation — Gurugram, 2026-03-01 17:00 (PM10 = 1229 µg/m³)

Performed 2026-11-14. Evidence from the raw Open-Meteo Air Quality API (CAMS global domain, `timezone=auto`) compared with the application. Scripts used are scratch scripts; the regression tests added to `tests/run_tests_workflow.py` encode the checks that matter.

## 1. Is 1229 µg/m³ an application error? — No
- App output equals the raw provider response for all six pollutants and both indices (PM10 1229.3, PM2.5 142.0, CO 540.0, NO2 14.8, SO2 15.3, O3 117.0 µg/m³; `us_aqi` 486; `european_aqi` 356), the same hour (index 17 of the local day, `Asia/Kolkata`, UTC+5:30), and the same grid point (28.5, 77.0 for the requested 28.46, 77.03). Test: `env LIVE: app values == raw provider response`.
- The request uses `hourly=` (not daily maxima), `timezone=auto`, and a single-day window. Only `cams_global` serves India (`cams_europe`: "No data is available for this location"). Units come from the provider's `hourly_units` (µg/m³; indices `USAQI`/`EAQI`); nothing is multiplied or converted.
- It is not an isolated spike: hourly PM10 on 2026-03-01 rises smoothly from 286 to 1229 µg/m³; daily means 27 Feb–3 Mar were 214, 271, 705, 970, 1323 µg/m³.

## 2. Is it plausible? — Not as a ground-level value (unvalidated)
- Context check, same grid cell, 17:00 on 1–30 March 2025: model PM10 min 101, **median 872**, mean 1047, max 3092 µg/m³; about **35 % of hourly values exceeded 1000** µg/m³. The reference paper's Table 5.4 PM10 column for the same days (provenance unverified; the project audit found its two sites have identical targets) has median 223, mean 230, max 410: the model's mean is about **4.5×** that series; correlation of the daily 17:00 values −0.05. No station data could be checked (no OpenAQ key; CPCB portal not accessible here).
- Conclusion: the value is genuine model output but, over this region, model PM10 looks biased high (or dust-dominated) relative to the only comparator available. It cannot be validated here, so PHYTORYX now labels modelled PM10 and the provider's AQI values as **unvalidated** in the dashboard, PDF, HTML and combined interpretation, and recommends measured station data.

## 3. Provider indices (US AQI 486, European AQI 356)
- The provider's `us_aqi` equals its `us_aqi_pm10` (486; PM2.5 sub-index 182), i.e. the index is driven by PM10. 486 corresponds to about 590 µg/m³ in the EPA PM10 band (505–604 → 401–500), close to the trailing 24-hour mean of the hourly PM10 (591 µg/m³ ending 16:00; 624 ending 17:00), **not** to the hourly 1229 (which the EPA formula would cap at 500). The provider's index also exceeds 500 at other hours (550 at 20:00), so it is not capped. The exact provider averaging could not be reproduced exactly; the app therefore does **not** recompute these values, labels them "provider-computed", gives the category (US EPA bands; European bands as documented by Open-Meteo: above 100 = extremely poor), and states they are not reproducible from the listed hourly concentrations.
- US/European/CPCB indices are never combined or substituted for one another.

## 4. CPCB AQI implementation (`phyllo/aqi_standard.py`)
12 hand-calculated sub-indices from the CPCB 2014 breakpoint table and linear formula (PM10, PM2.5, NO2, O3, CO, SO2) matched the code exactly; values above the top breakpoint cap at 500; AQI requires ≥ 3 pollutants including PM2.5 or PM10. CPCB is used only for the OpenAQ "indicative index from latest readings" (CPCB uses 24-hour/8-hour averages), labelled indicative.

## 5. Defects found and fixed
| # | Defect | Fix | Regression test |
|---|---|---|---|
| A | A date without a time silently returned the 00:00 hour as if it were the collection hour | now `USER_INPUT_REQUIRED` (no request, no assumed hour) | `date-only time never silently becomes 00:00` |
| B | If the provider omitted the requested hour, the code returned a different hour | now `UNAVAILABLE` ("no other hour is substituted") | `missing requested hour never substituted` |
| C | A "CPCB-formula index" was shown from a single pollutant | only shown with ≥ 3 pollutants incl. PM; otherwise `index_note` | `CPCB index needs >=3 pollutants…` |
| D | OpenAQ units spelled with Greek μ (U+03BC) were not recognised, silently dropping the index | unit normalisation (µ, μ, "u", ³/3); other units (e.g. ppb) are not converted | same test |
| E | Provider AQI values carried no category/scale context | `index_info` (value + category) and `index_note` shown everywhere | `provider AQI values labelled…` |
| F | HTML report omitted the modelled value time, time zone and grid point that the PDF showed | added | cross-surface check |
| G | No caution about unvalidated model PM10 | `validation_note` in section, dashboard, PDF, HTML, interpretation | workflow tests |

## 6. Not verified
Live OpenAQ retrieval (no key); any comparison with ground-station data; the provider's exact averaging; the dashboard's results state in a real browser (its rendering code displays the JSON fields unchanged; PDF and HTML were compared value-by-value with the JSON).
