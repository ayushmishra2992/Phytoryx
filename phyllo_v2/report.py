"""Server-side PDF report (fpdf2, core fonts -> text is sanitised to Latin-1). Built from the /v2/analyze result only; nothing is invented."""
import base64
import io
import secrets
from datetime import datetime, timezone

from fpdf import FPDF

TAG = "Intelligence Rooted in Nature."
DISCLAIMER = ("PHYTORYX is an experimental AI research platform. Its predictions and analytical outputs may be uncertain and should not be treated as "
              "definitive botanical, medical, microbiological or environmental measurements. Dataset limitations, model uncertainty and module-specific "
              "constraints should be considered when interpreting results.")
LIMITS = [
    "Phyllotaxy classification was validated only on a small held-out set from the project's own photo collection; it has not been shown to generalise to new species or cameras.",
    "Leaf measurements are approximate, in image pixels, from a colour-threshold segmentation; physical units appear only when a scale was supplied.",
    "Modelled air quality (Open-Meteo/CAMS) is a model estimate for a grid cell, not a measurement; its free tier is non-commercial. OpenAQ values are station observations.",
    "Leaf-photograph-based AQI estimation has no demonstrated skill in this project and is not provided.",
    "FTIR band ranges (if shown) are indicative and do not identify pollutants.",
]


def new_report_id():
    now = datetime.now(timezone.utc)
    return f"PHX-{now:%Y%m%d}-{secrets.token_hex(4).upper()}", now.isoformat(timespec="seconds")


def _t(s):
    """Latin-1 safe text."""
    s = "" if s is None else str(s)
    for a, b in (("–", "-"), ("—", "-"), ("≥", ">="), ("≤", "<="), ("·", "-"), ("→", "->"), ("’", "'"), ("“", '"'),
                 ("”", '"'), ("μ", "u"), ("≈", "~"), ("−", "-"), ("×", "x"), ("…", "...")):
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


class _Pdf(FPDF):
    def header(self):
        self.set_fill_color(38, 70, 49)
        self.rect(0, 0, 210, 16, "F")
        self.set_xy(10, 4)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.cell(40, 8, "PHYTORYX")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 8, TAG)
        self.set_text_color(0, 0, 0)
        self.set_y(20)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, _t(f"PHYTORYX report {getattr(self, 'rid', '')} - page {self.page_no()}/{{nb}} - experimental research output"), align="C")
        self.set_text_color(0, 0, 0)


def _h(pdf, text):
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(38, 70, 49)
    pdf.cell(0, 7, _t(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(150, 180, 150)
    pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _p(pdf, text, size=9.5, bold=False, italic=False):
    pdf.set_font("Helvetica", ("B" if bold else "") + ("I" if italic else ""), size)
    pdf.multi_cell(0, 4.8, _t(text), new_x="LMARGIN", new_y="NEXT")


def _kv(pdf, rows):
    for k, v in rows:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(48, 5, _t(k))
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _t(v), new_x="LMARGIN", new_y="NEXT")


def _table(pdf, head, rows, widths):
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(232, 240, 232)
    for h, w in zip(head, widths):
        pdf.cell(w, 5.5, _t(h), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8.5)
    for r in rows:
        for c, w in zip(r, widths):
            pdf.cell(w, 5.2, _t(c)[:int(w * 0.62)], border=1)
        pdf.ln()


def build_pdf(a, compress=True):
    """a = the dict returned by POST /v2/analyze. Returns PDF bytes."""
    pdf = _Pdf(format="A4")
    pdf.rid = a.get("report_id", "n/a")
    pdf.set_compression(compress)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, 16)
    pdf.set_margins(10, 20, 10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, "Leaf and Environment Analysis Report", new_x="LMARGIN", new_y="NEXT")
    loc = a.get("location", {})
    _kv(pdf, [("Report ID", a.get("report_id", "n/a")), ("Generated (UTC)", a.get("generated_utc", "n/a")), ("Image file", a.get("filename", "n/a")),
              ("Collection location", loc.get("label") or "not supplied"),
              ("Coordinates", f"{loc['lat']}, {loc['lon']}" if loc.get("lat") is not None else "not available"),
              ("Collection date/time", a.get("collected_at") or "not supplied (environmental values describe current conditions)"),
              ("Software version", f"PHYTORYX analysis API v{a.get('version', '?')}")])
    if a.get("image_preview_jpeg_base64"):
        try:
            pdf.ln(2)
            pdf.image(io.BytesIO(base64.b64decode(a["image_preview_jpeg_base64"])), x=10, w=70)
            pdf.ln(2)
        except Exception:  # noqa: BLE001
            _p(pdf, "(image preview could not be embedded)", italic=True)

    ph = a["phyllotaxy"]
    _h(pdf, "1. Botanical analysis - phyllotaxy")
    _kv(pdf, [("Result", ph.get("label", "n/a")), ("Decision status", ph.get("decision_status", "n/a")),
              ("Calibrated confidence", f"{round((ph.get('calibrated_confidence') or 0) * 100)}%")])
    if ph.get("probabilities"):
        _table(pdf, ["Class", "Calibrated probability"], [[k, f"{v * 100:.1f}%"] for k, v in sorted(ph["probabilities"].items(), key=lambda kv: -kv[1])], [60, 45])
    _p(pdf, ph.get("reason", ""), italic=True)
    for g in ph.get("guidance", []) or []:
        _p(pdf, "- " + g, 9)
    if ph.get("caution"):
        _p(pdf, ph["caution"], 9, italic=True)
    q = a["image_quality"]
    _p(pdf, f"Image quality: {q['status']} - {q['reason']}", 9)

    mo = a["morphology"]
    _h(pdf, "2. Leaf morphology (image pixels, approximate)")
    if mo["status"] == "AVAILABLE":
        rows = [["Area", f"{mo['area_px']} px^2"], ["Perimeter", f"{mo['perimeter_px']} px"], ["Length (major axis)", f"{mo['length_px']} px"],
                ["Width (minor axis)", f"{mo['width_px']} px"], ["Aspect ratio", mo["aspect_ratio"]], ["Solidity", mo["solidity"]],
                ["Circularity", mo["circularity"]], ["Eccentricity", mo["eccentricity"]], ["Leaf share of frame", f"{mo['leaf_area_fraction'] * 100:.1f}%"],
                ["Mean colour RGB", "/".join(str(x) for x in mo["mean_rgb_in_leaf"])]]
        if mo.get("physical"):
            ph_ = mo["physical"]
            rows += [["Area (physical)", f"{ph_['area_cm2']} cm^2"], ["Length (physical)", f"{ph_['length_cm']} cm"], ["Width (physical)", f"{ph_['width_cm']} cm"]]
        _table(pdf, ["Measurement", "Value"], rows, [60, 55])
        _p(pdf, mo["reason"], 9, italic=True)
        for f in mo.get("reliability_flags", []):
            _p(pdf, "Note: " + f, 9)
        _p(pdf, mo["caveat"], 8.5, italic=True)
    else:
        _p(pdf, "Not available: " + mo["reason"])
    h = a.get("leaf_health", {})
    if h.get("status") == "EXPERIMENTAL":
        fr = h["colour_fractions"]
        _p(pdf, "Visible-condition colour fractions (EXPERIMENTAL, not validated): " + ", ".join(f"{k} {v * 100:.1f}%" for k, v in fr.items()), 9)

    _h(pdf, "3. Environmental analysis")
    _p(pdf, f"Location: {loc.get('label') or 'not supplied'}"
            + (f" ({loc['lat']}, {loc['lon']})" if loc.get("lat") is not None else "") + f". Resolution source: {loc.get('source', 'n/a')}.", 9)
    mod = a["modelled_environment"]
    _p(pdf, "3a. MODELLED air quality (Open-Meteo / CAMS) - an atmospheric model estimate, NOT a ground measurement", bold=True)
    if mod["status"] == "AVAILABLE":
        _table(pdf, ["Parameter", "Value", "Unit"], [[r["parameter"], r["value"], r.get("unit") or ""] for r in mod["readings"]], [75, 30, 30])
        _p(pdf, f"Value time (local): {mod['value_time_local']} | timezone {mod.get('timezone')} | model grid point "
                f"{mod['model_grid_point']['latitude']}, {mod['model_grid_point']['longitude']} | retrieved {mod['retrieved_utc']} UTC", 8.5)
        if mod.get("index_info"):
            _p(pdf, "Provider-computed indices: " + "; ".join(f"{k} {v['value']} ({v['category']})" for k, v in mod["index_info"].items()), 8.5, bold=True)
        _p(pdf, "AQI note: " + (mod.get("index_note") or "the indices are the model service's own, on different scales, shown separately and never combined; "
                                "they are not the Indian CPCB AQI."), 8.5, italic=True)
        if mod.get("validation_note"):
            _p(pdf, "Validation note: " + mod["validation_note"], 8.5, bold=True)
        _p(pdf, mod["attribution"], 8, italic=True)
    else:
        _p(pdf, f"{mod['status']}: {mod['reason']}")
    amb = a["ambient_environment"]
    _p(pdf, "3b. MEASURED air quality (OpenAQ monitoring stations)", bold=True)
    if amb["status"] == "AVAILABLE":
        st = amb["nearest_station"]
        _p(pdf, f"Station: {st['name']} (id {st['station_id']}), {st['distance_km']} km from the location; provider {st.get('provider')}; "
                f"licence {', '.join(st.get('licences') or []) or 'not stated'}", 9)
        _table(pdf, ["Parameter", "Value", "Unit", "Observation time (UTC)"],
               [[r["parameter"], r["value"], r["unit"], r.get("timestamp_utc") or ""] for r in st["readings"]], [35, 25, 25, 60])
        if amb.get("indicative_index_from_latest"):
            i = amb["indicative_index_from_latest"]
            _p(pdf, f"Indicative CPCB-formula index from the latest single readings: {i['aqi']} ({i['category']}). {i['note']}", 8.5, italic=True)
        if amb.get("index_note"):
            _p(pdf, amb["index_note"], 8.5, italic=True)
        if amb.get("time_note"):
            _p(pdf, amb["time_note"], 8.5, italic=True)
        _p(pdf, amb["representativeness_note"], 8.5, italic=True)
    else:
        _p(pdf, f"{amb['status']}: {amb['reason']}")

    ci = a.get("combined_interpretation", {})
    _h(pdf, "4. Combined interpretation")
    for s in ci.get("summary", []):
        _p(pdf, "- " + s, 9.5)
    _p(pdf, "Cautions", bold=True)
    for s in ci.get("cautions", []):
        _p(pdf, "- " + s, 9)
    _p(pdf, "Missing or unavailable information", bold=True)
    for s in ci.get("missing_information", []) or ["None reported."]:
        _p(pdf, "- " + s, 9)

    f = a.get("ftir", {})
    if f.get("status") == "AVAILABLE":
        _h(pdf, "5. FTIR spectrum (user-supplied; indicative only)")
        _p(pdf, f"{f['n_points']} points, {f['range_cm1'][0]}-{f['range_cm1'][1]} cm^-1, {f['n_peaks']} peaks detected.", 9)
        _table(pdf, ["Peak (cm^-1)", "Absorbance", "Candidate group ranges (indicative)"],
               [[p["wavenumber_cm-1"], p["absorbance"], "; ".join(c["assignment"] for c in p["candidate_groups"]) or "-"] for p in f["peaks"][:8]], [28, 25, 135])
        _p(pdf, f["caveat"], 8.5, italic=True)

    _h(pdf, "6. Data sources and attribution")
    for s in ("Phyllotaxy: PHYTORYX fine-tuned ViT-B/16 (google/vit-base-patch16-224-in21k backbone) trained on the project's original leaf photographs.",
              mod.get("attribution") if mod["status"] == "AVAILABLE" else "Open-Meteo / CAMS: not retrieved for this report.",
              "OpenAQ (measured stations): https://openaq.org - source and licence per station as listed above." if amb["status"] == "AVAILABLE" else "OpenAQ: no station data in this report.",
              loc.get("attribution") or ""):
        if s:
            _p(pdf, "- " + s, 8.5)
    _h(pdf, "7. Limitations")
    for s in LIMITS:
        _p(pdf, "- " + s, 8.5)
    _h(pdf, "Disclaimer")
    _p(pdf, DISCLAIMER, 9, italic=True)
    return bytes(pdf.output())
