"""PHYTORYX integrated-workflow tests: threshold logic, morphology units, location, environment, combined report, PDF.
Labels: REAL (real images/HTTP), SYNTHETIC (generated input with known geometry), MOCK (mocked service), LIVE (real network; SKIP if offline).
Run: python tests/run_tests_workflow.py
"""
import io
import json
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from phyllo.paths import SPLIT_4  # noqa: E402
from phyllo_v2 import environment, imaging, report  # noqa: E402

REG = ROOT / "v2" / "data_registry"
os.environ["PHYLLO_RATE_LIMIT"] = "0"      # rate limiting is tested explicitly (and re-enabled temporarily) below; off for the other tests
RESULTS = []


class Skip(Exception):
    pass


def check(name, fn):
    try:
        fn()
        RESULTS.append(True)
        print(f"  PASS  {name}")
    except Skip as e:
        RESULTS.append(None)
        print(f"  SKIP  {name}: {e}")
    except Exception as e:  # noqa: BLE001
        RESULTS.append(False)
        print(f"  FAIL  {name}: {e!r}")
        traceback.print_exc(limit=3)


def own(cls, n=0):
    d = SPLIT_4 / "test" / cls
    return sorted(d.iterdir())[n]


def plantdoc_sample():
    return sorted((REG / "samples" / "plantdoc_ood").glob("*.[jJ][pP]*[gG]"))


def ellipse(w=1600, h=1200, a=400, b=200, cx=None, cy=None):
    im = Image.new("RGB", (w, h), (255, 255, 255))
    ImageDraw.Draw(im).ellipse([(cx or w // 2) - a, (cy or h // 2) - b, (cx or w // 2) + a, (cy or h // 2) + b], fill=(40, 140, 50))
    return im


def jpeg(im):
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=92)
    return b.getvalue()


# ----------------------------------------------------------------- morphology (SYNTHETIC, known geometry)
def t_morphology_units():
    m = imaging.morphology_section(ellipse())          # 1600x1200 -> analysis copy is downscaled; results must be in ORIGINAL pixels
    assert m["status"] == "AVAILABLE" and m["units"].startswith("pixels") and "physical" not in m
    true_area = np.pi * 400 * 200
    assert abs(m["area_px"] - true_area) / true_area < 0.06, (m["area_px"], true_area)
    assert abs(m["length_px"] - 800) / 800 < 0.06 and abs(m["width_px"] - 400) / 400 < 0.06, (m["length_px"], m["width_px"])
    assert abs(m["aspect_ratio"] - 2.0) < 0.15 and m["image_size_px"] == [1600, 1200]
    assert not m["touches_image_border"] and m["segmentation_reliability"] == "approximate" and "approximate" in m["caveat"]


def t_morphology_scale_and_validation():
    m = imaging.morphology_section(ellipse(), pixels_per_cm=100.0)
    assert abs(m["physical"]["length_cm"] - 8.0) < 0.5 and abs(m["physical"]["area_cm2"] - np.pi * 4 * 2) < 2.0 and "user-supplied scale" in m["physical"]["basis"]
    for bad in (-1, 0, 1e9):
        try:
            imaging.morphology_section(ellipse(), pixels_per_cm=bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted scale {bad}")


def t_morphology_flags_cropped_leaf():
    m = imaging.morphology_section(ellipse(cx=300, a=400))     # ellipse runs off the left edge
    assert m["status"] == "AVAILABLE" and m["touches_image_border"] and any("border" in f for f in m["reliability_flags"])


def t_morphology_real_leaves():
    for cls in ("Alternate", "Opposite", "Whorled"):
        m = imaging.morphology_section(Image.open(own(cls)).convert("RGB"))
        assert m["status"] in ("AVAILABLE", "UNAVAILABLE")
        if m["status"] == "AVAILABLE":
            assert m["area_px"] > 0 and m["perimeter_px"] > 0 and m["length_px"] >= m["width_px"] > 0 and 0 < m["circularity"] <= 1


# ----------------------------------------------------------------- engine: threshold behaviour (REAL images)
def t_engine_threshold_logic():
    from phyllo.pipeline import PhylloEngine
    eng = PhylloEngine(load_aqi_model=False)
    tau = eng.thr.get("nonleaf_probability")
    assert tau is not None and 0.5 <= tau <= 0.95, tau
    for cls in ("Alternate", "Opposite", "Whorled"):                      # supported leaves are unaffected
        r = eng.predict(Image.open(own(cls, 1)).convert("RGB"), explain=False)
        assert r["decision"]["status"] == "ACCEPT" and r["decision"]["leaf_evidence"]["assessment"] == "likely_supported_leaf"
    changed = 0
    for p in plantdoc_sample():
        img = Image.open(p).convert("RGB")
        new = eng.predict(img, explain=False)
        le = new["decision"]["leaf_evidence"]
        assert new["decision"]["status"] != "ACCEPT"
        if new["decision"]["status"] == "NOT_A_LEAF":
            assert le["p_not_a_leaf"] >= tau
        saved = eng.thr.pop("nonleaf_probability")                       # fallback = previous behaviour when the artifact has no threshold
        try:
            old = eng.predict(img, explain=False)
        finally:
            eng.thr["nonleaf_probability"] = saved
        assert old["decision"]["leaf_evidence"]["nonleaf_threshold"] is None
        if old["decision"]["status"] == "NOT_A_LEAF" and new["decision"]["status"] != "NOT_A_LEAF":
            changed += 1
            assert new["decision"]["status"] in ("ABSTAIN_UNFAMILIAR", "ABSTAIN_UNCERTAIN") and new["phyllotaxy"]["accepted"] is False
    assert changed >= 1, "expected the new threshold to change at least one weak NOT_A_LEAF verdict in the real unfamiliar-leaf sample"


def t_threshold_provenance_recorded():
    cfg = json.loads((ROOT / "artifacts" / "reliability_ft4.json").read_text(encoding="utf-8"))
    res = json.loads((ROOT / "results" / "v2_nonleaf_threshold.json").read_text(encoding="utf-8"))
    assert cfg["thresholds"]["nonleaf_probability"] == res["chosen"]["tau"] and res["applied"]
    assert "NOT tuned on PlantDoc test" in cfg["nonleaf_probability_provenance"] and res["n_dev_leaves"] > 2000


# ----------------------------------------------------------------- environmental correctness regressions (bugs found in the AQI validation)
def _om_hourly(hours):
    return {"latitude": 1, "longitude": 1, "timezone": "UTC", "hourly_units": {"pm10": "ug/m3"},
            "hourly": {"time": [f"2026-03-01T{h:02d}:00" for h in hours], "pm10": [float(h) for h in hours]}}


def t_date_only_time_not_silently_midnight():
    calls = []

    def h(q):
        calls.append(q)
        return httpx.Response(200, json=_om_hourly(range(24)))
    r = environment.fetch_modelled(28, 77, "2026-03-01", client=mock_client(h))
    assert r["status"] == "USER_INPUT_REQUIRED" and "no hour is assumed" in r["reason"] and not calls     # no request, no 00:00 substitution
    assert environment.fetch_modelled(28, 77, "2026-03-01 17:00", client=mock_client(h))["value_time_local"] == "2026-03-01T17:00"


def t_missing_hour_never_substituted():
    r = environment.fetch_modelled(1, 1, "2026-03-01 17:00", client=mock_client(lambda q: httpx.Response(200, json=_om_hourly(range(6)))))
    assert r["status"] == "UNAVAILABLE" and "no other hour is substituted" in r["reason"] and "readings" not in r


def _oaq_station(units, params, values):
    loc = {"id": 7, "name": "S", "coordinates": {"latitude": 28.47, "longitude": 77.04}, "provider": {"name": "P"}, "licenses": [],
           "sensors": [{"id": i + 1, "parameter": {"name": n, "units": units}} for i, n in enumerate(params)]}

    def h(q):
        if q.url.path.endswith("/locations"):
            return httpx.Response(200, json={"results": [loc]})
        return httpx.Response(200, json={"results": [{"sensorsId": i + 1, "value": v, "datetime": {"utc": "2026-11-14T06:00:00Z"}} for i, v in enumerate(values)]})
    return environment.fetch_ambient(28.46, 77.03, client=mock_client(h), api_key="k")


def t_cpcb_index_needs_three_pollutants_and_any_mu_spelling():
    one = _oaq_station("µg/m³", ["pm25"], [92.0])
    assert one["status"] == "AVAILABLE" and one["indicative_index_from_latest"] is None and "at least 3 pollutants" in one["index_note"]
    for mu in ("µg/m³", "μg/m³", "ug/m3", "µg/m3"):
        three = _oaq_station(mu, ["pm25", "pm10", "no2"], [92.0, 160.0, 45.0])
        idx = three["indicative_index_from_latest"]
        assert idx and idx["aqi"] == 204 and idx["dominant_pollutant"] == "PM2.5" and idx["pollutants_used"] == ["NO2", "PM10", "PM2.5"], (mu, three)
    ppb = _oaq_station("ppb", ["pm25", "pm10", "no2"], [92.0, 160.0, 45.0])          # other units are NOT converted or guessed
    assert ppb["indicative_index_from_latest"] is None


def t_provider_indices_labelled_not_recalculated():
    om = {"latitude": 1, "longitude": 1, "timezone": "UTC", "current_units": {"pm10": "ug/m3", "us_aqi": "USAQI", "european_aqi": "EAQI"},
          "current": {"time": "2026-03-01T17:00", "pm10": 1229.3, "us_aqi": 486, "european_aqi": 356}}
    r = environment.fetch_modelled(1, 1, client=mock_client(lambda q: httpx.Response(200, json=om)))
    assert r["index_info"]["US AQI"] == {"value": 486, "category": "Hazardous"} and r["index_info"]["European AQI"]["category"].startswith("Extremely poor")
    assert "computed by the data provider" in r["index_note"] and "not the Indian CPCB AQI" in r["index_note"]
    assert environment._index_category("us_aqi", 550) == "Beyond the 0-500 scale" and environment._index_category("european_aqi", 15) == "Good"


def t_modelled_equals_raw_provider_response_live():
    """LIVE: the app's pollutant values, units, hour and grid point must equal the raw provider response (no unit/index/timezone error)."""
    try:
        raw = httpx.get(environment.OM_BASE, params={"latitude": 28.46, "longitude": 77.03, "hourly": ",".join(environment.OM_VARS), "timezone": "auto",
                                                     "start_date": "2026-03-01", "end_date": "2026-03-01"}, timeout=30)
        app = environment.fetch_modelled(28.46, 77.03, "2026-03-01 17:00")
    except Exception as e:  # noqa: BLE001
        raise Skip(f"network: {e}")
    if raw.status_code != 200 or app["status"] != "AVAILABLE":
        raise Skip(f"live service unavailable: {raw.status_code} / {app.get('reason')}")
    j = raw.json()
    i = j["hourly"]["time"].index("2026-03-01T17:00")
    assert app["value_time_local"] == "2026-03-01T17:00" and app["timezone"] == j["timezone"]
    assert app["model_grid_point"] == {"latitude": j["latitude"], "longitude": j["longitude"]}
    by = {x["parameter"]: x for x in app["readings"]}
    for var, name in environment.OM_NAMES.items():
        if j["hourly"][var][i] is not None:
            assert by[name]["value"] == j["hourly"][var][i] and by[name]["unit"] == j["hourly_units"][var], (var, by[name], j["hourly"][var][i])


# ----------------------------------------------------------------- rate limiting
def t_ratelimiter_unit():
    from phyllo_v2.ratelimit import RateLimiter, _int_env
    rl = RateLimiter()
    assert [rl.check("a", 3, 60, now=t)[0] for t in (0, 1, 2)] == [True, True, True]
    ok, retry = rl.check("a", 3, 60, now=3)
    assert not ok and 1 <= retry <= 60, retry
    assert rl.check("b", 3, 60, now=3)[0]                          # other clients have their own budget
    assert rl.check("a", 3, 60, now=61)[0]                         # the oldest hit (t=0) has left the window
    assert rl.check("a", 3, 60, now=61.5)[0] and rl.check("a", 3, 60, now=62)[0]    # hits at t=1,2 have not yet expired: budget refilled by one slot at a time
    assert not rl.check("a", 3, 60, now=62.5)[0]
    assert all(rl.check("c", 0, 60, now=i)[0] for i in range(100))  # limit 0 disables
    os.environ["PHYLLO_RATE_LIMIT_TEST"] = "not-a-number"
    assert _int_env("PHYLLO_RATE_LIMIT_TEST", 30) == 30             # bad settings fall back to the default
    os.environ.pop("PHYLLO_RATE_LIMIT_TEST")


# ----------------------------------------------------------------- location (MOCK + LIVE)
def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


GEO_OK = {"results": [{"name": "Gurugram", "admin1": "Haryana", "country": "India", "latitude": 28.46, "longitude": 77.03, "timezone": "Asia/Kolkata", "feature_code": "PPLA2"},
                      {"name": "Gurgaon", "admin1": "Haryana", "country": "India", "latitude": 28.45, "longitude": 77.02}]}


def t_geocode_mock():
    r = environment.geocode("Gurugram", client=mock_client(lambda q: httpx.Response(200, json=GEO_OK)))
    assert r["status"] == "AVAILABLE" and r["resolved"]["country"] == "India" and len(r["alternatives"]) == 1 and "Verify" in r["reason"]
    assert environment.geocode("", client=mock_client(lambda q: httpx.Response(200, json=GEO_OK)))["status"] == "USER_INPUT_REQUIRED"
    for h in (lambda q: httpx.Response(200, json={}), lambda q: httpx.Response(429), lambda q: httpx.Response(500), lambda q: httpx.Response(200, text="x")):
        assert environment.geocode("Nowhere", client=mock_client(h))["status"] == "UNAVAILABLE"


def t_attribution_links_present():
    r = environment.geocode("Gurugram", client=mock_client(lambda q: httpx.Response(200, json=GEO_OK)))
    assert "geonames.org" in r["attribution"] and "CC BY 4.0" in r["attribution"]
    m = environment.fetch_modelled(1, 1, client=mock_client(lambda q: httpx.Response(200, json={
        "latitude": 1, "longitude": 1, "timezone": "UTC", "current_units": {"pm10": "ug/m3"}, "current": {"time": "2026-03-01T17:00", "pm10": 5.0}})))
    assert "https://open-meteo.com/" in m["attribution"] and "CAMS" in m["attribution"]


def t_geocode_live():
    try:
        r = environment.geocode("Gurugram")
    except Exception as e:  # noqa: BLE001
        raise Skip(f"network: {e}")
    if r["status"] == "UNAVAILABLE" and "Could not resolve" in r["reason"]:
        raise Skip(r["reason"])
    assert r["status"] == "AVAILABLE" and abs(r["resolved"]["latitude"] - 28.46) < 0.5 and r["resolved"]["country"] == "India"


# ----------------------------------------------------------------- API workflow
OM = {"latitude": 28.5, "longitude": 77.0, "timezone": "Asia/Kolkata", "hourly_units": {"pm2_5": "ug/m3", "pm10": "ug/m3", "us_aqi": "USAQI"},
      "hourly": {"time": [f"2026-03-01T{h:02d}:00" for h in range(24)], "pm2_5": [float(i) for i in range(24)], "pm10": [2.0 * i for i in range(24)],
                 "us_aqi": [100 + i for i in range(24)]}}
OAQ_LOC = {"id": 7, "name": "Mock Station", "coordinates": {"latitude": 28.47, "longitude": 77.04}, "provider": {"name": "MockProv"}, "licenses": [{"name": "CC BY 4.0"}],
           "sensors": [{"id": 1, "parameter": {"name": "pm25", "units": "µg/m³"}}, {"id": 2, "parameter": {"name": "pm10", "units": "µg/m³"}}]}


def oaq_handler(req):
    if req.url.path.endswith("/locations"):
        return httpx.Response(200, json={"results": [OAQ_LOC]})
    return httpx.Response(200, json={"results": [{"sensorsId": 1, "value": 77.0, "datetime": {"utc": "2026-11-14T06:00:00Z"}}]})   # PM10 missing on purpose


def api_tests():
    from fastapi.testclient import TestClient
    from api.v2_app import app

    with TestClient(app) as c:
        def post_img(path, data=None, files=None, name="x.jpg", ctype="image/jpeg", **kw):
            return c.post(path, files={"file": (name, kw.pop("img"), ctype), **(files or {})}, data=data or {})

        def patched(geo=None, om=None, oaq=None, key="k"):
            """Context-free patch helper returning an undo function (all network replaced by MOCK transports)."""
            saved = (environment.geocode, environment.fetch_modelled, environment.fetch_ambient)
            if geo is not None:
                g = environment.geocode
                environment.geocode = lambda place, client=None, count=5: g(place, client=mock_client(geo))
            if om is not None:
                m = environment.fetch_modelled
                environment.fetch_modelled = lambda lat, lon, when=None, client=None: m(lat, lon, when, client=mock_client(om))
            if oaq is not None:
                a = environment.fetch_ambient
                environment.fetch_ambient = lambda lat, lon, when=None, client=None, api_key=None, max_stations=3: a(lat, lon, when, client=mock_client(oaq), api_key=key)

            def undo():
                environment.geocode, environment.fetch_modelled, environment.fetch_ambient = saved
            return undo

        def leaf_bytes(cls="Whorled", n=0):
            return own(cls, n).read_bytes()

        full_result = {}

        def wf_place_and_time_mocked():
            undo = patched(geo=lambda q: httpx.Response(200, json=GEO_OK), om=lambda q: httpx.Response(200, json=OM), oaq=oaq_handler)
            try:
                r = post_img("/v2/analyze", data={"place": "Gurugram", "collected_at": "2026-03-01 17:00", "pixels_per_cm": "50"}, img=leaf_bytes()).json()
            finally:
                undo()
            assert re.fullmatch(r"PHX-\d{8}-[0-9A-F]{8}", r["report_id"]) and r["generated_utc"].endswith("+00:00")
            assert r["location"]["status"] == "AVAILABLE" and r["location"]["label"] == "Gurugram, Haryana, India" and "geocoded" in r["location"]["source"]
            assert r["collected_at"] == "2026-03-01 17:00"
            m = r["modelled_environment"]
            assert m["status"] == "AVAILABLE" and m["kind"] == "modelled" and m["value_time_local"] == "2026-03-01T17:00"
            pm = {x["parameter"]: x for x in m["readings"]}
            assert pm["PM2.5"]["value"] == 17.0 and pm["PM2.5"]["unit"] and "US AQI (model-derived)" in pm
            a = r["ambient_environment"]
            assert a["status"] == "AVAILABLE" and a["nearest_station"]["name"] == "Mock Station" and a["time_note"]    # latest, not collection time
            assert {x["parameter"] for x in a["nearest_station"]["readings"]} == {"PM2.5"}                          # missing pollutant NOT invented
            assert r["morphology"]["status"] in ("AVAILABLE", "UNAVAILABLE")
            if r["morphology"]["status"] == "AVAILABLE":
                assert "physical" in r["morphology"]
            ci = r["combined_interpretation"]
            assert ci["summary"] and ci["cautions"] and any("did not measure, cause or represent" in s for s in ci["cautions"])
            assert any("PM10" in s or "Measured" in s for s in ci["summary"] + ci["missing_information"])
            full_result.update(r)

        def wf_coordinates_gps_style():
            current = {"latitude": 28.5, "longitude": 77.0, "timezone": "Asia/Kolkata", "current_units": {"pm2_5": "ug/m3"},
                       "current": {"time": "2026-11-14T10:30", "pm2_5": 93.4}}
            undo = patched(om=lambda q: httpx.Response(200, json=current if "current" in dict(q.url.params) else OM))
            try:
                r = post_img("/v2/analyze", data={"lat": "28.46", "lon": "77.03"}, img=leaf_bytes("Opposite")).json()
            finally:
                undo()
            assert r["location"]["source"].startswith("user-supplied coordinates") and r["modelled_environment"]["status"] == "AVAILABLE"
            assert any("current conditions" in s for s in r["combined_interpretation"]["cautions"])

        def wf_geocode_failure_is_honest():
            undo = patched(geo=lambda q: httpx.Response(200, json={}))
            try:
                r = post_img("/v2/analyze", data={"place": "Qwertyuiop"}, img=leaf_bytes()).json()
            finally:
                undo()
            assert r["location"]["status"] == "UNAVAILABLE" and "No place matching" in r["location"]["reason"]
            assert r["modelled_environment"]["status"] == "USER_INPUT_REQUIRED" and r["ambient_environment"]["status"] == "USER_INPUT_REQUIRED"
            assert r["combined_interpretation"]["missing_information"]

        def wf_no_location():
            r = post_img("/v2/analyze", img=leaf_bytes()).json()
            assert r["location"]["status"] == "USER_INPUT_REQUIRED" and r["modelled_environment"]["status"] == "USER_INPUT_REQUIRED"

        def wf_api_failures_do_not_crash():
            undo = patched(om=lambda q: httpx.Response(500), oaq=lambda q: httpx.Response(429))
            try:
                r = post_img("/v2/analyze", data={"lat": "28.46", "lon": "77.03", "collected_at": "2026-03-01 17:00"}, img=leaf_bytes()).json()
            finally:
                undo()
            assert r["modelled_environment"]["status"] == "UNAVAILABLE" and r["ambient_environment"]["status"] == "UNAVAILABLE"
            assert r["phyllotaxy"]["label"] == "Whorled"                      # botanical result survives environmental failure
            assert any("not collection-time" in s or "NOT collection-time" in s for s in r["combined_interpretation"]["cautions"])

        def wf_no_station_and_no_key():
            undo = patched(oaq=lambda q: httpx.Response(200, json={"results": []}))
            try:
                r = post_img("/v2/analyze", data={"lat": "0.0", "lon": "-140.0"}, img=leaf_bytes()).json()
            finally:
                undo()
            assert r["ambient_environment"]["status"] == "UNAVAILABLE" and "No OpenAQ monitoring station" in r["ambient_environment"]["reason"]
            import os
            old = os.environ.pop("OPENAQ_API_KEY", None)
            try:
                r2 = post_img("/v2/analyze", data={"lat": "28.46", "lon": "77.03"}, img=leaf_bytes()).json()
            finally:
                if old:
                    os.environ["OPENAQ_API_KEY"] = old
            assert r2["ambient_environment"]["status"] == "USER_INPUT_REQUIRED" and "API key" in r2["ambient_environment"]["reason"]

        def wf_bad_scale_400():
            assert post_img("/v2/analyze", data={"pixels_per_cm": "-3"}, img=leaf_bytes()).status_code == 400

        def wf_unfamiliar_and_lowquality():
            p = plantdoc_sample()[0]
            r = post_img("/v2/analyze", data={"lat": "28.46", "lon": "77.03"}, img=p.read_bytes(), name=p.name).json()
            assert r["phyllotaxy"]["decision_status"] != "ACCEPT" and r["phyllotaxy"]["guidance"]
            blur = Image.open(own("Opposite")).convert("RGB").filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(30))
            r2 = post_img("/v2/analyze", img=jpeg(blur)).json()
            assert r2["image_quality"]["status"] == "UNAVAILABLE" and r2["phyllotaxy"]["label"] == "Unknown" and r2["morphology"]["status"] == "UNAVAILABLE"

        def pdf_download_and_content():
            assert full_result, "workflow result missing"
            resp = c.post("/v2/report/pdf", json=full_result)
            assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
            assert full_result["report_id"] in resp.headers["content-disposition"] and resp.content[:5] == b"%PDF-" and len(resp.content) > 8000
            raw = report.build_pdf(full_result, compress=False)
            n_pages = len(re.findall(rb"/Type /Page\b", raw))
            assert n_pages >= 2, n_pages
            for needle in (b"PHYTORYX", full_result["report_id"].encode(), b"MODELLED", b"NOT a ground measurement", b"MEASURED air quality", b"Gurugram, Haryana, India",
                           b"Mock Station", b"Combined interpretation", b"Disclaimer", b"2026-03-01T17:00", b"Intelligence Rooted in Nature", b"Limitations"):
                assert needle in raw, needle
            measured = raw.split(b"3b. MEASURED")[1].split(b"4. Combined")[0]
            assert b"(PM10)" not in measured, "missing measured PM10 must not appear as a reading in the report"   # table cell, not the explanatory note
            assert b"(PM2.5)" in measured and b"at least 3 pollutants" in measured

        def pdf_for_non_location_and_failure_cases():
            r = post_img("/v2/analyze", img=leaf_bytes("Alternate", 2)).json()         # no location at all
            resp = c.post("/v2/report/pdf", json=r)
            assert resp.status_code == 200 and resp.content[:5] == b"%PDF-"
            raw = report.build_pdf(r, compress=False)
            assert b"USER_INPUT_REQUIRED" in raw and b"not supplied" in raw
            p = plantdoc_sample()[1]
            r2 = post_img("/v2/analyze", img=p.read_bytes(), name=p.name).json()       # unfamiliar leaf
            assert c.post("/v2/report/pdf", json=r2).status_code == 200

        def pdf_rejects_bad_input():
            assert c.post("/v2/report/pdf", json={"hello": "world"}).status_code == 400
            bad = dict(full_result)
            bad["phyllotaxy"] = "not a dict"
            assert c.post("/v2/report/pdf", json=bad).status_code == 400

        def json_report_machine_readable():
            s = json.dumps(full_result)
            back = json.loads(s)
            for k in ("report_id", "generated_utc", "location", "collected_at", "phyllotaxy", "morphology", "modelled_environment", "ambient_environment",
                      "combined_interpretation", "image_preview_jpeg_base64", "version"):
                assert k in back, k
            assert len(base64_decode(back["image_preview_jpeg_base64"])) > 1000

        def geocode_endpoint():
            undo = patched(geo=lambda q: httpx.Response(200, json=GEO_OK))
            try:
                r = c.get("/v2/geocode", params={"q": "Gurugram"}).json()
            finally:
                undo()
            assert r["status"] == "AVAILABLE"

        def rate_limit_api():
            from phyllo_v2.ratelimit import limiter
            g = environment.geocode
            environment.geocode = lambda place, client=None, count=5: g(place, client=mock_client(lambda q: httpx.Response(200, json=GEO_OK)))
            keys = ("PHYLLO_RATE_LIMIT", "PHYLLO_RATE_WINDOW_S", "PHYLLO_TRUST_PROXY")
            old = {k: os.environ.get(k) for k in keys}
            try:
                os.environ["PHYLLO_RATE_LIMIT"], os.environ["PHYLLO_RATE_WINDOW_S"] = "3", "60"
                os.environ.pop("PHYLLO_TRUST_PROXY", None)
                limiter.reset()
                origin = {"Origin": "http://localhost:3000"}
                codes = [c.get("/v2/geocode", params={"q": "Gurugram"}, headers={**origin, "X-Forwarded-For": f"9.9.9.{i}"}).status_code for i in range(5)]
                assert codes == [200, 200, 200, 429, 429], codes                    # spoofed X-Forwarded-For does not bypass the limit
                r = c.get("/v2/geocode", params={"q": "x"}, headers=origin)
                assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "Rate limit exceeded" in r.json()["detail"]
                assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"      # the browser can read the 429 message
                assert c.get("/v2/modules").status_code == 200 and c.get("/health").status_code == 200   # cheap and v1 routes unaffected
                assert post_img("/v2/analyze", img=leaf_bytes()).status_code == 429                    # analyze and PDF share the budget
                assert c.post("/v2/report/pdf", json={"a": 1}).status_code == 429
                os.environ["PHYLLO_TRUST_PROXY"] = "1"
                limiter.reset()
                ok = [c.get("/v2/geocode", params={"q": "G"}, headers={"X-Forwarded-For": f"1.1.1.{i}"}).status_code for i in range(5)]
                assert ok == [200] * 5, ok                                          # behind a trusted proxy each forwarded client has its own budget
                os.environ["PHYLLO_RATE_LIMIT"] = "0"
                limiter.reset()
                assert all(c.get("/v2/geocode", params={"q": "G"}).status_code == 200 for _ in range(6))   # 0 disables
            finally:
                environment.geocode = g
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                os.environ["PHYLLO_RATE_LIMIT"] = "0"
                limiter.reset()

        def live_end_to_end():
            try:
                r = post_img("/v2/analyze", data={"place": "Gurugram", "collected_at": "2026-03-01 17:00"}, img=leaf_bytes()).json()
            except Exception as e:  # noqa: BLE001
                raise Skip(f"network: {e}")
            if r["location"]["status"] != "AVAILABLE" or r["modelled_environment"]["status"] != "AVAILABLE":
                raise Skip(f"live services unavailable: {r['location'].get('reason')} / {r['modelled_environment']['reason']}")
            assert r["modelled_environment"]["value_time_local"] == "2026-03-01T17:00" and r["modelled_environment"]["kind"] == "modelled"
            assert r["phyllotaxy"]["label"] == "Whorled"
            assert c.post("/v2/report/pdf", json=r).status_code == 200

        for name, fn in [("workflow MOCK: place + collection time -> location, modelled + measured env, missing pollutant honest, interpretation", wf_place_and_time_mocked),
                         ("workflow MOCK: coordinates only (GPS style), current-conditions caution", wf_coordinates_gps_style),
                         ("workflow MOCK: geocoding fails -> honest unavailable, no invented env", wf_geocode_failure_is_honest),
                         ("workflow: no location supplied", wf_no_location),
                         ("workflow MOCK: env API 500/429 does not crash; botanical result survives", wf_api_failures_do_not_crash),
                         ("workflow MOCK: no station in range; missing OpenAQ key", wf_no_station_and_no_key),
                         ("workflow: invalid scale -> 400", wf_bad_scale_400),
                         ("workflow REAL: unfamiliar leaf + blurred image", wf_unfamiliar_and_lowquality),
                         ("PDF: download, header, filename, pages, content, no invented PM10", pdf_download_and_content),
                         ("PDF: no-location and unfamiliar-leaf reports", pdf_for_non_location_and_failure_cases),
                         ("PDF: malformed/foreign input -> 400", pdf_rejects_bad_input),
                         ("JSON report machine-readable fields + embedded preview", json_report_machine_readable),
                         ("geocode endpoint (MOCK)", geocode_endpoint),
                         ("rate limit: 429 + Retry-After + CORS-readable; spoofed X-Forwarded-For ignored; trusted-proxy mode; 0 disables", rate_limit_api),
                         ("LIVE end-to-end: real geocoding + real Open-Meteo history + PDF", live_end_to_end)]:
            check("api: " + name, fn)


def base64_decode(s):
    import base64
    return base64.b64decode(s)


if __name__ == "__main__":
    print("PHYTORYX workflow test suite")
    for n, f in [("morphology: SYNTHETIC ellipse area/length/width in ORIGINAL pixels", t_morphology_units),
                 ("morphology: user scale -> cm; invalid scale rejected", t_morphology_scale_and_validation),
                 ("morphology: cropped leaf flagged", t_morphology_flags_cropped_leaf), ("morphology: REAL leaves", t_morphology_real_leaves),
                 ("engine: threshold logic on REAL images + fallback without threshold", t_engine_threshold_logic),
                 ("engine: threshold provenance recorded (dev data only)", t_threshold_provenance_recorded),
                 ("geocode: MOCK success/empty/429/500/garbage", t_geocode_mock), ("attribution: GeoNames + Open-Meteo links in section data", t_attribution_links_present),
                 ("geocode: LIVE", t_geocode_live),
                 ("rate limiter: window, clients, disable, bad settings", t_ratelimiter_unit),
                 ("env regression: date-only time never silently becomes 00:00", t_date_only_time_not_silently_midnight),
                 ("env regression: missing requested hour never substituted", t_missing_hour_never_substituted),
                 ("env regression: CPCB index needs >=3 pollutants; any mu spelling; other units not guessed", t_cpcb_index_needs_three_pollutants_and_any_mu_spelling),
                 ("env: provider AQI values labelled with category/note, not recalculated", t_provider_indices_labelled_not_recalculated),
                 ("env LIVE: app values == raw provider response (values, units, hour, tz, grid)", t_modelled_equals_raw_provider_response_live)]:
        check(n, f)
    api_tests()
    failed, skipped = RESULTS.count(False), RESULTS.count(None)
    print(f"\n{len(RESULTS) - failed - skipped}/{len(RESULTS)} passed, {skipped} skipped, {failed} failed")
    sys.exit(1 if failed else 0)
