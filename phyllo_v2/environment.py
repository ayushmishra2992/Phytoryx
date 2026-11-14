"""Ambient air-quality retrieval from OpenAQ (v3). Requires a user-supplied API key (env OPENAQ_API_KEY).

OpenAQ aggregates government monitors; licences are per source (read from each location's response, never assumed).
Everything returned here is an AMBIENT reading from a monitoring station - NOT something measured from the leaf photo, and
it may not represent the exact leaf location (station distance is reported).
"""
import math
import os
from datetime import datetime, timezone

import httpx

from phyllo.aqi_standard import compute_aqi

from . import AVAILABLE, UNAVAILABLE, USER_INPUT_REQUIRED, section

BASE = os.environ.get("OPENAQ_BASE_URL", "https://api.openaq.org/v3")
SEARCH_RADIUS_M = int(os.environ.get("OPENAQ_RADIUS_M", "25000"))   # OpenAQ v3 maximum radius is 25 km
NAMES = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO2", "co": "CO", "o3": "O3", "so2": "SO2"}
WANTED = set(NAMES)


def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def _get(client, path, key, **params):
    r = client.get(f"{BASE}{path}", params=params, headers={"X-API-Key": key}, timeout=20)
    if r.status_code == 429:
        raise RuntimeError("OpenAQ rate limit reached (HTTP 429); try again later.")
    if r.status_code in (401, 403):
        raise RuntimeError(f"OpenAQ rejected the API key (HTTP {r.status_code}).")
    r.raise_for_status()
    return r.json()


def fetch_ambient(lat, lon, collected_at=None, client=None, api_key=None, max_stations=3):
    """Return an environment section. `client` may be injected (tests use a mock transport and say so)."""
    if lat is None or lon is None:
        return section(USER_INPUT_REQUIRED, "Provide a location (latitude/longitude) to look up nearby monitoring stations.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return section(USER_INPUT_REQUIRED, "Latitude must be in [-90, 90] and longitude in [-180, 180].")
    key = api_key or os.environ.get("OPENAQ_API_KEY", "")
    if not key:
        return section(USER_INPUT_REQUIRED, "No OpenAQ API key configured (set OPENAQ_API_KEY; free registration at explore.openaq.org/register). "
                       "No ambient data is shown.")
    own = client is None
    client = client or httpx.Client()
    try:
        locs = _get(client, "/locations", key, coordinates=f"{lat},{lon}", radius=SEARCH_RADIUS_M, limit=20)
        results = locs.get("results", [])
        if not results:
            return section(UNAVAILABLE, f"No OpenAQ monitoring station within {SEARCH_RADIUS_M // 1000} km of this location.")
        for r in results:
            c = r.get("coordinates") or {}
            r["_dist"] = haversine_km(lat, lon, c.get("latitude", lat), c.get("longitude", lon)) if c else 1e9
        results.sort(key=lambda r: r["_dist"])
        stations = []
        for loc in results:
            if len(stations) >= max_stations:
                break
            sensors = {s["id"]: s for s in loc.get("sensors", []) if (s.get("parameter") or {}).get("name") in WANTED}
            if not sensors:
                continue
            latest = _get(client, f"/locations/{loc['id']}/latest", key).get("results", [])
            readings = []
            for item in latest:
                s = sensors.get(item.get("sensorsId"))
                if not s:
                    continue
                p = s["parameter"]
                dt = (item.get("datetime") or {}).get("utc")
                readings.append({"parameter": NAMES[p["name"]], "value": item.get("value"), "unit": p.get("units"), "timestamp_utc": dt})
            if not readings:
                continue
            stations.append({
                "station_id": loc["id"], "name": loc.get("name"), "distance_km": round(loc["_dist"], 2),
                "provider": (loc.get("provider") or {}).get("name"), "licences": [l.get("name") for l in (loc.get("licenses") or [])],
                "readings": readings})
        if not stations:
            return section(UNAVAILABLE, "Stations were found nearby but none reported PM2.5/PM10/NO2/CO/O3/SO2 latest values.")
        best = stations[0]
        indicative = None
        conc = {}
        for r in best["readings"]:
            if r["value"] is None or r["value"] < 0:
                continue
            if r["parameter"] in ("PM2.5", "PM10", "NO2", "O3") and r["unit"] in ("\u00b5g/m\u00b3", "ug/m3"):
                conc[r["parameter"]] = r["value"]
            elif r["parameter"] == "CO" and r["unit"] in ("\u00b5g/m\u00b3", "ug/m3"):
                conc["CO"] = r["value"] / 1000.0   # CPCB CO unit is mg/m3
        if conc:
            try:
                a = compute_aqi(conc)
                indicative = {"aqi": a["aqi"], "category": a["category"], "dominant_pollutant": a.get("dominant_pollutant"),
                              "note": "CPCB-formula index applied to the LATEST single readings. The official AQI uses 24-hour averages, "
                                      "so this is indicative only and not an official AQI."}
            except ValueError:
                indicative = None
        note = None
        if collected_at:
            note = (f"Station values are the latest available readings, not the readings at the supplied collection time ({collected_at}). "
                    "Historical retrieval is not implemented.")
        return section(AVAILABLE, "Ambient readings from OpenAQ monitoring stations; not measured from the leaf and possibly not representative of the exact leaf location.",
                       source="OpenAQ API v3 (https://api.openaq.org/v3)", retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       query={"lat": lat, "lon": lon, "radius_km": SEARCH_RADIUS_M // 1000}, nearest_station=best, other_stations=stations[1:],
                       indicative_index_from_latest=indicative, time_note=note,
                       representativeness_note=f"Nearest station is {best['distance_km']} km away; street-level and leaf-level exposure can differ substantially.")
    except Exception as e:  # network, auth, rate limit, malformed response
        return section(UNAVAILABLE, f"Could not retrieve ambient data: {e}")
    finally:
        if own:
            client.close()


# ---------------------------------------------------------------------------------------------------------------
# Modelled (NOT measured) ambient air quality: Open-Meteo Air Quality API (CAMS ENSEMBLE / CAMS global). No API key.
# Licence CC BY 4.0 with attribution to the CAMS ENSEMBLE data provider and Open-Meteo; FREE USE IS NON-COMMERCIAL ONLY.
# ---------------------------------------------------------------------------------------------------------------
OM_BASE = os.environ.get("OPENMETEO_AQ_URL", "https://air-quality-api.open-meteo.com/v1/air-quality")
OM_VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide", "ozone", "european_aqi", "us_aqi"]
OM_NAMES = {"pm10": "PM10", "pm2_5": "PM2.5", "carbon_monoxide": "CO", "nitrogen_dioxide": "NO2",
            "sulphur_dioxide": "SO2", "ozone": "O3", "european_aqi": "European AQI (model-derived)", "us_aqi": "US AQI (model-derived)"}
OM_ATTRIBUTION = ("Contains modified CAMS ENSEMBLE data (Copernicus Atmosphere Monitoring Service; METEO FRANCE, Ineris, Aarhus University, MET Norway, "
                  "IEK-J\u00fclich, IEP-NRI, KNMI, TNO, SMHI, FMI, ENEA, BSC) served by Open-Meteo.com under CC BY 4.0. Free use is non-commercial only.")


def _parse_when(collected_at):
    from datetime import datetime
    if not collected_at:
        return None
    s = collected_at.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return "bad"


def fetch_modelled(lat, lon, collected_at=None, client=None):
    """Model-based ambient estimate for the grid cell at (lat, lon): current values, or the hour matching `collected_at` (local time)."""
    if lat is None or lon is None:
        return section(USER_INPUT_REQUIRED, "Provide a location (latitude/longitude) to look up modelled air quality.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return section(USER_INPUT_REQUIRED, "Latitude must be in [-90, 90] and longitude in [-180, 180].")
    when = _parse_when(collected_at)
    if when == "bad":
        return section(USER_INPUT_REQUIRED, "Collection time not understood; use 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' (local time at the location).")
    own = client is None
    client = client or httpx.Client()
    try:
        params = {"latitude": lat, "longitude": lon, "timezone": "auto"}
        if when is None:
            params["current"] = ",".join(OM_VARS)
        else:
            d = when.strftime("%Y-%m-%d")
            params.update(hourly=",".join(OM_VARS), start_date=d, end_date=d)
        r = client.get(OM_BASE, params=params, timeout=20)
        if r.status_code == 400:
            try:
                why = r.json().get("reason", "bad request")
            except Exception:  # noqa: BLE001
                why = "bad request"
            return section(UNAVAILABLE, f"Open-Meteo could not serve this request: {why}")
        if r.status_code == 429:
            return section(UNAVAILABLE, "Open-Meteo rate limit reached (HTTP 429); try again later.")
        r.raise_for_status()
        j = r.json()
        units = j.get("current_units" if when is None else "hourly_units", {})
        if when is None:
            vals, ts = j["current"], j["current"]["time"]
        else:
            hours = j["hourly"]["time"]
            target = when.strftime("%Y-%m-%dT%H:00")
            if target not in hours:
                target = hours[min(len(hours) - 1, when.hour)] if hours else None
            if target is None:
                return section(UNAVAILABLE, "Open-Meteo returned no hourly data for that date.")
            i = hours.index(target)
            vals, ts = {k: j["hourly"][k][i] for k in OM_VARS if k in j["hourly"]}, target
        readings = [{"parameter": OM_NAMES[k], "value": vals.get(k), "unit": units.get(k)} for k in OM_VARS if vals.get(k) is not None]
        if not readings:
            return section(UNAVAILABLE, "Open-Meteo returned no values for this location/time (outside model coverage or period).")
        return section(AVAILABLE, "MODELLED air quality for the surrounding grid cell (CAMS, about 11 km in Europe / 45 km global). "
                       "It is not a station measurement, not measured from the leaf, and may differ from street-level conditions.",
                       kind="modelled", source="Open-Meteo Air Quality API (CAMS ENSEMBLE / CAMS global)", attribution=OM_ATTRIBUTION,
                       licence="CC BY 4.0 (free use non-commercial only)", retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       model_grid_point={"latitude": j.get("latitude"), "longitude": j.get("longitude")}, timezone=j.get("timezone"),
                       value_time_local=ts, requested_time=collected_at, readings=readings)
    except Exception as e:  # noqa: BLE001
        return section(UNAVAILABLE, f"Could not retrieve modelled air quality: {e}")
    finally:
        if own:
            client.close()
