"""PHYTORYX API = the unchanged v1.0.1 app (api.main) + independent /v2/* routes.

Run:  python -m uvicorn api.v2_app:app --host 127.0.0.1 --port 8000
v1 routes (/predict, /aqi/compute, /evidence, /health, /model-card, UI) behave exactly as in v1.0.1.
"""
import logging
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.main import ALLOWED, MAX_BYTES, STATE, app  # noqa: F401  (importing api.main leaves v1 untouched)
from phyllo_v2 import AVAILABLE, DISABLED, EXPERIMENTAL, NOT_SUPPORTED, USER_INPUT_REQUIRED, UNAVAILABLE, __version__, section
from phyllo_v2 import environment, ftir, imaging

log = logging.getLogger("phyllo.v2")
router = APIRouter(prefix="/v2", tags=["v2"])
MAX_FTIR_BYTES = 10 * 1024 * 1024


GUIDANCE = {
    "ABSTAIN_UNFAMILIAR": ["This image looks unlike the photos the model was validated on (other species, cameras or backgrounds are common causes).",
                           "Retake with the whole branch/stem and its nodes visible, one plant, plain background, even daylight, 20-50 cm away.",
                           "No phyllotaxy label is shown because it could not be validated."],
    "ABSTAIN_UNCERTAIN": ["The model is not confident enough to answer.", "Retake with the stem and at least two nodes visible and sharper focus."],
    "REJECT_QUALITY": ["The photo failed the quality gate (blur, exposure, size or noise).", "Retake in good light, hold still, and fill the frame with the branch."],
    "NOT_A_LEAF": ["The classifier does not recognise this as a validated leaf photo."],
}
UNFAMILIAR_CAUTION = ("On 236 real leaf photos of other species (PlantDoc test split), the classifier never accepted an answer and called 65% of them "
                      "'not a leaf' - so this verdict does not prove the object is not a leaf; it means the photo is outside what was validated.")


def _phyllotaxy_section(r, img=None):
    st = r["decision"]["status"]
    p = r["phyllotaxy"]
    rel = r["reliability"]
    familiarity = {"in_distribution": rel["in_distribution"], "mahalanobis_score": rel["mahalanobis_score"],
                   "mahalanobis_threshold": rel["mahalanobis_threshold"], "knn_similarity": rel["knn_similarity"],
                   "knn_threshold": rel["knn_threshold"]}
    if st == "NOT_A_LEAF" and img is not None:
        ll = imaging.leaf_like(img)
        if ll["leaf_like"]:   # wording only; never promotes to ACCEPT
            return section(AVAILABLE, "The classifier did not recognise this as a validated leaf photo, but the image contains a large green leaf-like region, "
                           "so 'not a leaf' is treated as unreliable.", label="Unknown/Uncertain", decision_status=st, calibrated_confidence=p["confidence"],
                           probabilities=p["probabilities"], familiarity=familiarity, leaf_like_check=ll, caution=UNFAMILIAR_CAUTION,
                           guidance=GUIDANCE["ABSTAIN_UNFAMILIAR"], supported_classes=["Alternate", "Opposite", "Whorled", "Not_a_leaf"],
                           spiral="NOT_SUPPORTED: no genuinely labelled Spiral data has been acquired, so Spiral cannot be predicted.")
    base = dict(decision_status=st, calibrated_confidence=p["confidence"], probabilities=p["probabilities"],
                supported_classes=["Alternate", "Opposite", "Whorled", "Not_a_leaf"],
                spiral="NOT_SUPPORTED: no genuinely labelled Spiral data has been acquired, so Spiral cannot be predicted.",
                context_note="Phyllotaxy is defined by how leaves attach along a stem. An isolated leaf blade or a close-up may not "
                             "show the nodes needed to judge it, so treat any answer as dataset-specific, not a botanical determination.",
                validation_note="Validated only on the project's own small held-out set (64/65 test images); not tested on new species or cameras.")
    base["familiarity"] = familiarity
    if st != "ACCEPT":
        base["guidance"] = GUIDANCE.get(st, GUIDANCE["ABSTAIN_UNCERTAIN"])
    if st == "ACCEPT":
        return section(AVAILABLE, r["decision"]["headline"], label=p["class"], **base)
    if st == "NOT_A_LEAF":
        return section(AVAILABLE, r["decision"]["headline"], label="Not_a_leaf", caution=UNFAMILIAR_CAUTION, **base)
    if st == "REJECT_QUALITY":
        return section(UNAVAILABLE, r["decision"]["headline"], label="Unknown", **base)
    return section(AVAILABLE, r["decision"]["headline"], label="Unknown/Uncertain", **base)


def _leaf_aqi_section(r):
    a = r["aqi"]
    return section(NOT_SUPPORTED if a["value"] is None else EXPERIMENTAL,
                   a["message"] + " Leaf-image AQI estimation has no demonstrated skill in this project and is not an ambient or official AQI.",
                   v1_status=a["status"], value=a["value"], evidence=a["evidence"])


async def _read_image(file: UploadFile):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "Unsupported file type. Upload a JPG, PNG, WEBP or BMP image.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image larger than 15 MB.")
    try:
        return STATE["engine"].read_image(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Unable to read image: {exc}")


async def _read_spectrum(ftir_file, y_units, column, wavenumber_scale):
    data = await ftir_file.read()
    if not data:
        raise HTTPException(400, "Empty FTIR file.")
    if len(data) > MAX_FTIR_BYTES:
        raise HTTPException(413, "FTIR file larger than 10 MB.")
    try:
        sp = ftir.parse_spectrum(ftir_file.filename, data, y_units=y_units, column=column, wavenumber_scale=wavenumber_scale)
        return ftir.analyse(sp)
    except ValueError as exc:
        raise HTTPException(400, f"FTIR file rejected: {exc}")


@router.get("/modules")
def modules():
    """Honest capability map: what is implemented, experimental, or unsupported - and why."""
    return {"version": __version__, "modules": {
        "phyllotaxy": section(AVAILABLE, "4-class ViT with calibrated abstention (v1.0.1 engine)."),
        "species": imaging.species_section(),
        "morphology": section(AVAILABLE, "Classical pixel-space leaf measurements."),
        "leaf_health": section(EXPERIMENTAL, "Colour heuristics; not validated against labelled data."),
        "dust_deposition": imaging.dust_section(),
        "ambient_environment": section(USER_INPUT_REQUIRED, "Measured station readings: needs a location and an OpenAQ API key (OPENAQ_API_KEY); live OpenAQ retrieval is unverified without a key."),
        "modelled_environment": section(USER_INPUT_REQUIRED, "Modelled (CAMS via Open-Meteo, keyless, CC BY 4.0, non-commercial use): needs a location; not a measurement."),
        "ftir": section(USER_INPUT_REQUIRED, "Needs a user-supplied spectrum (CSV/TSV/TXT, XLSX, JCAMP-DX). Indicative band ranges only."),
        "biological": imaging.biological_section(),
        "leaf_based_aqi": section(NOT_SUPPORTED, "No demonstrated skill (46 pairs, permutation p = 0.45); withheld.")}}


@router.post("/ftir/analyse")
async def ftir_only(ftir_file: UploadFile = File(...), y_units: str = Form("absorbance"), column: int = Form(1),
                    wavenumber_scale: float | None = Form(None)):
    return await _read_spectrum(ftir_file, y_units, column, wavenumber_scale)


@router.post("/analyze")
async def analyze(file: UploadFile = File(...), lat: float | None = Form(None), lon: float | None = Form(None),
                  collected_at: str | None = Form(None), ftir_file: UploadFile | None = File(None),
                  ftir_y_units: str = Form("absorbance"), ftir_column: int = Form(1), ftir_wavenumber_scale: float | None = Form(None)):
    t0 = time.time()
    img = await _read_image(file)
    engine = STATE["engine"]
    r = engine.predict(img, explain=False)
    accepted_leaf = r["decision"]["status"] == "ACCEPT"
    quality = r["quality"]
    phy = _phyllotaxy_section(r, img)
    usable = quality["passed"] and phy["label"] != "Not_a_leaf"   # leaf-like images re-worded as Unknown/Uncertain still get measurements

    out = {"version": __version__, "filename": file.filename,
           "image_quality": section(AVAILABLE if quality["passed"] else UNAVAILABLE,
                                    "Image passed the quality gate." if quality["passed"] else "Image failed the quality gate: " + "; ".join(quality["issues"]),
                                    sharpness=quality["sharpness"], noise=quality["noise"], warnings=quality["warnings"]),
           "phyllotaxy": phy, "species": imaging.species_section()}
    if usable:
        out["morphology"] = imaging.morphology_section(img)
        out["leaf_health"] = imaging.health_section(img)
    else:
        why = "Skipped: the image is not a usable leaf photo (failed quality gate or not a leaf)."
        out["morphology"] = section(UNAVAILABLE, why)
        out["leaf_health"] = section(UNAVAILABLE, why)
    out["dust_deposition"] = imaging.dust_section()
    out["leaf_based_aqi"] = _leaf_aqi_section(r)
    out["ambient_environment"] = environment.fetch_ambient(lat, lon, collected_at)    # measured (OpenAQ, needs key)
    out["modelled_environment"] = environment.fetch_modelled(lat, lon, collected_at)  # modelled (CAMS via Open-Meteo, keyless)
    out["ftir"] = (await _read_spectrum(ftir_file, ftir_y_units, ftir_column, ftir_wavenumber_scale)
                   if ftir_file is not None and ftir_file.filename else
                   section(USER_INPUT_REQUIRED, "No FTIR spectrum supplied. No spectrum is generated or assumed."))
    out["biological"] = imaging.biological_section()
    out["separation_notice"] = ("Ambient station readings, any leaf-based estimate, visible-condition indicators and FTIR band ranges are different "
                                "kinds of evidence and are never combined into one number.")
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    log.info("v2 analyze %s status=%s latency=%sms", file.filename, r["decision"]["status"], out["latency_ms"])
    return out


app.include_router(router)
