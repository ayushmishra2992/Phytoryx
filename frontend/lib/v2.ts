export type ModuleStatus =
  | "AVAILABLE"
  | "EXPERIMENTAL"
  | "USER_INPUT_REQUIRED"
  | "UNAVAILABLE"
  | "NOT_SUPPORTED"
  | "DISABLED";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Section = { status: ModuleStatus; reason: string } & Record<string, any>;

export interface AnalyzeResponse {
  version: string;
  report_id: string;
  generated_utc: string;
  filename: string;
  collected_at: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  location: { status: ModuleStatus; lat: number | null; lon: number | null; label: string | null; source: string; reason?: string } & Record<string, any>;
  image_preview_jpeg_base64: string;
  combined_interpretation: { summary: string[]; missing_information: string[]; cautions: string[] };
  image_quality: Section;
  phyllotaxy: Section;
  species: Section;
  morphology: Section;
  leaf_health: Section;
  dust_deposition: Section;
  leaf_based_aqi: Section;
  ambient_environment: Section;
  modelled_environment: Section;
  ftir: Section;
  biological: Section;
  separation_notice: string;
  latency_ms: number;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class V2Error extends Error {}

export interface AnalyzeInput {
  file: File;
  place?: string;
  lat?: string;
  lon?: string;
  collectedAt?: string;
  pixelsPerCm?: string;
  ftir?: File | null;
  ftirUnits?: string;
  ftirWavenumberScale?: string;
}

export async function analyze(input: AnalyzeInput): Promise<AnalyzeResponse> {
  const fd = new FormData();
  fd.append("file", input.file);
  if (input.place?.trim()) fd.append("place", input.place.trim());
  if (input.pixelsPerCm?.trim()) fd.append("pixels_per_cm", input.pixelsPerCm.trim());
  if (input.lat?.trim()) fd.append("lat", input.lat.trim());
  if (input.lon?.trim()) fd.append("lon", input.lon.trim());
  if (input.collectedAt?.trim()) fd.append("collected_at", input.collectedAt.trim());
  if (input.ftir) {
    fd.append("ftir_file", input.ftir);
    fd.append("ftir_y_units", input.ftirUnits ?? "absorbance");
    if (input.ftirWavenumberScale?.trim()) fd.append("ftir_wavenumber_scale", input.ftirWavenumberScale.trim());
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/v2/analyze`, { method: "POST", body: fd });
  } catch {
    throw new V2Error(
      `Could not reach the PHYTORYX backend at ${API_BASE_URL}. Start it with RUN_V2.bat (python -m uvicorn api.v2_app:app).`
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const b = await res.json();
      detail = typeof b?.detail === "string" ? b.detail : JSON.stringify(b?.detail ?? "");
    } catch {
      /* ignore */
    }
    throw new V2Error(detail || `The backend returned an error (${res.status}).`);
  }
  return (await res.json()) as AnalyzeResponse;
}

/** Ask the backend to render the PDF for this analysis result and save it as a file. */
export async function downloadPdf(r: AnalyzeResponse): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/v2/report/pdf`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(r) });
  } catch {
    throw new V2Error(`Could not reach the PHYTORYX backend at ${API_BASE_URL} to build the PDF.`);
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json())?.detail ?? ""; } catch { /* ignore */ }
    throw new V2Error(`PDF could not be created: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `PHYTORYX-${r.report_id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export function reportHtml(r: AnalyzeResponse): string {
  const esc = (s: unknown) =>
    String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
  const rows = (
    [
      ["Image quality", r.image_quality],
      ["Phyllotaxy", r.phyllotaxy],
      ["Species", r.species],
      ["Morphology", r.morphology],
      ["Visible condition", r.leaf_health],
      ["Dust / deposition", r.dust_deposition],
      ["Leaf-based AQI", r.leaf_based_aqi],
      ["Ambient environment (measured)", r.ambient_environment],
      ["Ambient environment (modelled)", r.modelled_environment],
      ["FTIR", r.ftir],
      ["Biological", r.biological],
    ] as [string, Section][]
  )
    .map(([n, s]) => `<tr><td>${esc(n)}</td><td>${esc(s.status)}</td><td>${esc(s.reason)}</td></tr>`)
    .join("");
  const list = (items: unknown[]) => (items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "");
  const readings = (rd: { parameter: string; value: number; unit: string; timestamp_utc?: string }[] | undefined) =>
    rd?.length
      ? `<table><tr><th>Parameter</th><th>Value</th><th>Unit</th><th>Time</th></tr>${rd
          .map((x) => `<tr><td>${esc(x.parameter)}</td><td>${esc(x.value)}</td><td>${esc(x.unit)}</td><td>${esc(x.timestamp_utc ?? "")}</td></tr>`)
          .join("")}</table>`
      : "";
  const probs = Object.entries((r.phyllotaxy.probabilities ?? {}) as Record<string, number>)
    .map(([k, v]) => `${k} ${(v * 100).toFixed(1)}%`)
    .join(" · ");
  const st = r.ambient_environment.nearest_station;
  const peaks = ((r.ftir.peaks ?? []) as { "wavenumber_cm-1": number; absorbance: number }[])
    .slice(0, 10)
    .map((p) => `${p["wavenumber_cm-1"]} cm-1 (A=${p.absorbance})`);
  const details = `<h2>Details</h2>
<h3>Phyllotaxy</h3><p>${esc(probs)}</p>${r.phyllotaxy.caution ? `<p><i>${esc(r.phyllotaxy.caution)}</i></p>` : ""}${list(r.phyllotaxy.guidance ?? [])}
<h3>Measured ambient readings</h3>${st ? `<p>${esc(st.name)} · ${esc(st.distance_km)} km · provider ${esc(st.provider)}</p>${readings(st.readings)}` : "<p>None.</p>"}
<h3>Modelled air quality (not a measurement)</h3>${readings(r.modelled_environment.readings)}${
    r.modelled_environment.value_time_local
      ? `<p>Value time (local): ${esc(r.modelled_environment.value_time_local)} | timezone ${esc(r.modelled_environment.timezone)} | model grid point ${esc(r.modelled_environment.model_grid_point?.latitude)}, ${esc(r.modelled_environment.model_grid_point?.longitude)} | retrieved ${esc(r.modelled_environment.retrieved_utc)} UTC</p>`
      : ""
  }${
    r.modelled_environment.index_info
      ? `<p><b>Provider-computed indices:</b> ${esc(Object.entries(r.modelled_environment.index_info as Record<string, { value: number; category: string }>).map(([k, v]) => `${k} ${v.value} (${v.category})`).join("; "))}</p>`
      : ""
  }${r.modelled_environment.index_note ? `<p><i>${esc(r.modelled_environment.index_note)}</i></p>` : ""}${
    r.modelled_environment.validation_note ? `<p><b>Validation note:</b> ${esc(r.modelled_environment.validation_note)}</p>` : ""
  }${r.modelled_environment.attribution ? `<p>${esc(r.modelled_environment.attribution)} <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a></p>` : ""}${
    r.location.attribution ? `<p>Location data based on <a href="https://www.geonames.org/">GeoNames</a> via the Open-Meteo Geocoding API (CC BY 4.0).</p>` : ""
  }
<h3>FTIR peaks (indicative)</h3>${list(peaks)}`;
  const mo = r.morphology;
  const morph = mo.status === "AVAILABLE"
    ? `<h3>Leaf morphology (${esc(mo.units)})</h3><table><tr><th>Measurement</th><th>Value</th></tr>
<tr><td>Area</td><td>${esc(mo.area_px)} px²</td></tr><tr><td>Perimeter</td><td>${esc(mo.perimeter_px)} px</td></tr>
<tr><td>Length × width</td><td>${esc(mo.length_px)} × ${esc(mo.width_px)} px</td></tr><tr><td>Aspect ratio / solidity / circularity</td><td>${esc(mo.aspect_ratio)} / ${esc(mo.solidity)} / ${esc(mo.circularity)}</td></tr>
${mo.physical ? `<tr><td>Physical (user scale)</td><td>${esc(mo.physical.length_cm)} × ${esc(mo.physical.width_cm)} cm; ${esc(mo.physical.area_cm2)} cm²</td></tr>` : ""}</table>
${list(mo.reliability_flags ?? [])}<p><i>${esc(mo.caveat)}</i></p>`
    : `<h3>Leaf morphology</h3><p>Not available: ${esc(mo.reason)}</p>`;
  const ci = r.combined_interpretation;
  const loc = r.location;
  return `<!doctype html><meta charset="utf-8"><title>PHYTORYX report ${esc(r.report_id)}</title>
<style>body{font:14px system-ui;margin:2rem;max-width:900px}td,th{border:1px solid #ccc;padding:6px;vertical-align:top}table{border-collapse:collapse;width:100%}img{max-width:260px;border-radius:8px}@media print{body{margin:1cm}}</style>
<h1>PHYTORYX analysis report</h1><p><i>Intelligence Rooted in Nature.</i></p>
<p><b>Report ID:</b> ${esc(r.report_id)} · <b>Generated (UTC):</b> ${esc(r.generated_utc)} · backend v${esc(r.version)}</p>
<img alt="Analysed leaf" src="data:image/jpeg;base64,${esc(r.image_preview_jpeg_base64)}">
<p><b>File:</b> ${esc(r.filename)}<br><b>Location:</b> ${esc(loc.label ?? "not supplied")}${loc.lat != null ? ` (${esc(loc.lat)}, ${esc(loc.lon)}; ${esc(loc.source)})` : ""}<br>
<b>Collection time:</b> ${esc(r.collected_at ?? "not supplied (environmental values describe current conditions)")}</p>
<h2>Combined interpretation</h2>${list(ci.summary ?? [])}<h3>Missing or unavailable</h3>${list(ci.missing_information ?? [])}<h3>Cautions</h3>${list(ci.cautions ?? [])}
${morph}
<h2>Module status</h2><table><tr><th>Module</th><th>Status</th><th>Explanation</th></tr>${rows}</table>
<p><b>Phyllotaxy label:</b> ${esc(r.phyllotaxy.label)} (calibrated confidence ${esc(
    Math.round((r.phyllotaxy.calibrated_confidence ?? 0) * 100)
  )}%)</p><p>${esc(r.separation_notice)}</p>
${details}
<p>Unsupported or unavailable modules are shown as such; no values are invented. Full data: attached JSON.</p>`;
}
