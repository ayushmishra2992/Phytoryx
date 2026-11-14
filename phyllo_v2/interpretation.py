"""Combined botanical + environmental interpretation, built ONLY from fields actually present in the analysis result.

It never states or implies that the leaf measured, caused or represents the local pollution level.
"""


def _pm(readings, name):
    for r in readings or []:
        if r.get("parameter") == name and r.get("value") is not None:
            return f"{name} {r['value']} {r.get('unit') or ''}".strip()
    return None


def build(out):
    ph, mo = out["phyllotaxy"], out["morphology"]
    summary, missing = [], []

    # ---- botanical
    lab = ph.get("label")
    conf = ph.get("calibrated_confidence")
    if ph.get("decision_status") == "ACCEPT":
        summary.append(f"Phyllotaxy: {lab} (calibrated confidence {round(conf * 100)}%). The image matched the validated training evidence; "
                       "this is a dataset-specific classification, not a botanical determination.")
    elif lab == "Not_a_leaf":
        summary.append("The photograph was not recognised as a leaf, so no phyllotaxy was assigned.")
        missing.append("Phyllotaxy: not recognised as a leaf photograph")
    else:
        summary.append(f"No phyllotaxy label was given ({lab}): " + (ph.get("reason") or "insufficient validated evidence") +
                       " The image may show an unfamiliar plant or photographing style; see the retake guidance.")
        missing.append("Phyllotaxy: no reliable label")
    if mo["status"] == "AVAILABLE":
        phys = mo.get("physical")
        size = (f"about {phys['length_cm']} x {phys['width_cm']} cm (from the scale you supplied)" if phys
                else f"about {mo['length_px']} x {mo['width_px']} px (no physical scale supplied)")
        summary.append(f"Leaf outline {size}, aspect ratio {mo['aspect_ratio']}; segmentation is approximate"
                       + ("; the leaf touches the image border, so values are lower bounds." if mo.get("touches_image_border") else "."))
    else:
        missing.append("Morphology: " + mo["reason"])

    # ---- environmental
    loc = out.get("location", {})
    where = loc.get("label") or "the supplied location"
    mod, amb = out["modelled_environment"], out["ambient_environment"]
    if mod["status"] == "AVAILABLE":
        parts = [p for p in (_pm(mod["readings"], "PM2.5"), _pm(mod["readings"], "PM10"), _pm(mod["readings"], "NO2"), _pm(mod["readings"], "O3")) if p]
        info = mod.get("index_info") or {}
        aqi = "; ".join(f"provider-computed {k} {v['value']} ({v['category']})" for k, v in info.items())
        summary.append(f"Modelled air quality (CAMS, not a measurement) for {where} at {mod['value_time_local']} (local): " + ", ".join(parts)
                       + (f"; {aqi}" if aqi else "") + ".")
    else:
        missing.append("Modelled air quality: " + mod["reason"])
    if amb["status"] == "AVAILABLE":
        st = amb["nearest_station"]
        summary.append(f"Measured air quality: monitoring station '{st['name']}' ({st['distance_km']} km away), latest readings "
                       + ", ".join(f"{r['parameter']} {r['value']} {r['unit']}" for r in st["readings"][:4])
                       + (f" - note: {amb['time_note']}" if amb.get("time_note") else "."))
    else:
        missing.append("Measured air quality (OpenAQ): " + amb["reason"])

    cautions = [
        "The leaf photograph did not measure, cause or represent the air-quality values shown; they come from separate sources for the supplied location.",
        "Modelled values are grid-cell estimates and station readings may be kilometres away; street-level exposure can differ substantially.",
        "Phyllotaxy and leaf shape are not indicators of AQI or pollutant levels, and PHYTORYX makes no such claim.",
        "Pollutant concentrations (with units) and AQI index values are different quantities on different scales and are never combined.",
    ]
    if mod["status"] == "AVAILABLE":
        cautions.append("Modelled PM10 and the provider's AQI values are unvalidated model output and may be far above station observations "
                        "(see the validation note in the modelled-air-quality section); they should not be read as measured ground conditions.")
    if out.get("collected_at") and mod["status"] == "AVAILABLE" and mod.get("requested_time"):
        cautions.append("Modelled values correspond to the requested collection hour; measured station values (if any) are the latest available, not collection-time readings.")
    elif out.get("collected_at"):
        cautions.append("A collection time was supplied but historical environmental data was not available; any values shown are NOT collection-time values.")
    else:
        cautions.append("No collection time was supplied, so environmental values describe current conditions, not the day the leaf was collected.")
    return {"summary": summary, "missing_information": missing, "cautions": cautions}
