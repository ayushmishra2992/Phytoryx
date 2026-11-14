"""PHYTORYX API = the unchanged v1.0.1 app (api.main) + independent /v2/* routes.

Run:  python -m uvicorn api.v2_app:app --host 127.0.0.1 --port 8000
v1 routes (/predict, /aqi/compute, /evidence, /health, /model-card, UI) behave exactly as in v1.0.1.
"""
import logging
import time

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from api.main import ALLOWED, MAX_BYTES, STATE, app  # noqa: F401  (importing api.main leaves v1 untouched)
from phyllo_v2 import AVAILABLE, DISABLED, EXPERIMENTAL, NOT_SUPPORTED, USER_INPUT_REQUIRED, UNAVAILABLE, __version__, section
from phyllo_v2 import environment, ftir, imaging, interpretation, report
from phyllo_v2.ratelimit import rate_limit

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
UNFAMILIAR_CAUTION = ("In an earlier evaluation of 236 real leaf photos of other species (PlantDoc test split), none was accepted as a supported class, "
                      "and the previous decision rule called 65% of them 'not a leaf' from weak votes. 'Not a leaf' now needs a minimum probability, but "
                      "that rule has only been checked against generic (COCO) non-leaf objects, not leaf-like ones.")


def _phyllotaxy_section(r, img=None):
    st = r["decision"]["status"]
    p = r["phyllotaxy"]
    rel = r["reliability"]
    familiarity = {"in_distribution": rel["in_distribution"], "mahalanobis_score": rel["mahalanobis_score"],
                   "mahalanobis_threshold": rel["mahalanobis_threshold"], "knn_similarity": rel["knn_similarity"],
                   "knn_threshold": rel["knn_threshold"]}
    base = dict(decision_status=st, calibrated_confidence=p["confidence"], probabilities=p["probabilities"],
                leaf_evidence=r["decision"].get("leaf_evidence"), decision_reasons=r["decision"]["reasons"],
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


@router.post("/ftir/analyse", dependencies=[Depends(rate_limit)])
async def ftir_only(ftir_file: UploadFile = File(...), y_units: str = Form("absorbance"), column: int = Form(1),
                    wavenumber_scale: float | None = Form(None)):
    return await _read_spectrum(ftir_file, y_units, column, wavenumber_scale)


@router.post("/analyze", dependencies=[Depends(rate_limit)])
async def analyze(file: UploadFile = File(...), lat: float | None = Form(None), lon: float | None = Form(None),
                  place: str | None = Form(None), collected_at: str | None = Form(None), pixels_per_cm: float | None = Form(None),
                  ftir_file: UploadFile | None = File(None),
                  ftir_y_units: str = Form("absorbance"), ftir_column: int = Form(1), ftir_wavenumber_scale: float | None = Form(None)):
    t0 = time.time()
    img = await _read_image(file)
    engine = STATE["engine"]
    r = engine.predict(img, explain=False)
    quality = r["quality"]
    phy = _phyllotaxy_section(r, img)
    # leaf-like images that the engine could not classify (ABSTAIN_*) still get measurements; confirmed non-leaf/unusable images do not
    usable = quality["passed"] and r["decision"]["status"] != "NOT_A_LEAF"
    report_id, generated_utc = report.new_report_id()

    # ---- location: explicit coordinates win; otherwise resolve the typed place name
    geo = None
    if lat is not None and lon is not None:
        location = {"status": "AVAILABLE", "lat": lat, "lon": lon, "label": (place or "").strip() or f"{lat:.4f}, {lon:.4f}",
                    "source": "user-supplied coordinates" + (" (e.g. GPS)" if not place else "")}
    elif place and place.strip():
        geo = environment.geocode(place)
        if geo["status"] == "AVAILABLE":
            g = geo["resolved"]
            lat, lon = g["latitude"], g["longitude"]
            location = {"status": "AVAILABLE", "lat": lat, "lon": lon, "source": "geocoded from the typed place name (Open-Meteo Geocoding)",
                        "label": ", ".join(x for x in (g["name"], g.get("admin1"), g.get("country")) if x), "geocoding": geo,
                        "attribution": geo["attribution"]}
        else:
            location = {"status": geo["status"], "lat": None, "lon": None, "label": None, "source": "geocoding failed", "reason": geo["reason"]}
    else:
        location = {"status": "USER_INPUT_REQUIRED", "lat": None, "lon": None, "label": None, "source": "none",
                    "reason": "No collection location supplied (enter a place name, coordinates, or use GPS)."}

    import base64
    import io as _io
    thumb = img.copy()
    thumb.thumbnail((640, 640))
    buf = _io.BytesIO()
    thumb.save(buf, "JPEG", quality=80)

    out = {"version": __version__, "report_id": report_id, "generated_utc": generated_utc, "filename": file.filename,
           "collected_at": collected_at, "location": location, "image_preview_jpeg_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
           "image_quality": section(AVAILABLE if quality["passed"] else UNAVAILABLE,
                                    "Image passed the quality gate." if quality["passed"] else "Image failed the quality gate: " + "; ".join(quality["issues"]),
                                    sharpness=quality["sharpness"], noise=quality["noise"], warnings=quality["warnings"]),
           "phyllotaxy": phy, "species": imaging.species_section()}
    if usable:
        try:
            out["morphology"] = imaging.morphology_section(img, pixels_per_cm)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
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
    out["combined_interpretation"] = interpretation.build(out)
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    log.info("v2 analyze %s status=%s latency=%sms", file.filename, r["decision"]["status"], out["latency_ms"])
    return out


@router.get("/geocode", dependencies=[Depends(rate_limit)])
def geocode_endpoint(q: str):
    return environment.geocode(q)


REPORT_REQUIRED = ("report_id", "phyllotaxy", "morphology", "image_quality", "ambient_environment", "modelled_environment", "combined_interpretation")


@router.post("/report/pdf", dependencies=[Depends(rate_limit)])
def report_pdf(analysis: dict = Body(...)):
    """Render the PDF report from a /v2/analyze result (the client posts back the result it received)."""
    missing = [k for k in REPORT_REQUIRED if k not in analysis]
    if missing:
        raise HTTPException(400, f"Not a PHYTORYX analysis result; missing fields: {', '.join(missing)}")
    try:
        pdf = report.build_pdf(analysis)
    except Exception as exc:  # noqa: BLE001  any malformed client-supplied structure must be a 400, never a 500
        log.warning("report_pdf rejected malformed analysis: %r", exc)
        raise HTTPException(400, f"Analysis result is incomplete or malformed: {exc!r}")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="PHYTORYX-{analysis["report_id"]}.pdf"'})


app.include_router(router)
