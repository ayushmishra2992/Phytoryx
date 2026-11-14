"""Generate docs/PHYTORYX_DATASET_DOCUMENTATION.pdf from the dataset registry + CITATIONS.md using headless Edge/Chrome.
Usage: python scripts/make_dataset_pdf.py [out.pdf]
"""
import csv
import html
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
e = html.escape
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def main(out):
    rows = list(csv.DictReader(open(ROOT / "v2/data_registry/dataset_registry.csv", encoding="utf-8", newline="")))
    inv = "".join(f"<tr><td>{e(r['dataset_id'])}</td><td>{e(r['name'])}</td><td>{e(r['licence'])}</td><td>{e(r['redistribution_status'])}</td>"
                  f"<td>{e(r['project_status'])}</td></tr>" for r in rows)
    keys = ("task", "publisher_or_source", "source_url", "licence", "licence_verified_from_source", "access", "permission_summary",
            "redistribution_status", "rights_basis", "n_samples", "labels", "metadata_available", "project_status", "suitability",
            "limitations", "citation", "checked_on")
    detail = ""
    for r in rows:
        detail += f"<h3>{e(r['name'])}</h3><table class='kv'>" + "".join(
            f"<tr><th>{e(k.replace('_', ' '))}</th><td>{e(r[k])}</td></tr>" for k in keys if r.get(k)) + "</table>"
    cit = (ROOT / "CITATIONS.md").read_text(encoding="utf-8")
    cit_html = "".join(f"<li>{e(l[2:])}</li>" for l in cit.splitlines() if l.startswith("- "))
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>PHYTORYX dataset documentation</title><style>
@page {{ size: A4; margin: 16mm; }} body {{ font: 10.5pt/1.4 'Segoe UI', Arial, sans-serif; color:#1b2a1b; }}
h1 {{ font-size: 24pt; margin: 0; }} .tag {{ color:#4d6b4d; margin: 2px 0 14px; }}
h2 {{ font-size: 14pt; border-bottom: 2px solid #8fb08f; padding-bottom: 2px; margin-top: 18px; }} h3 {{ font-size: 11pt; margin: 14px 0 4px; page-break-after: avoid; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.5pt; }} td, th {{ border: 1px solid #c9d6c9; padding: 4px 6px; vertical-align: top; text-align: left; }}
th {{ background: #eef4ee; }} table.kv th {{ width: 24%; }} li {{ margin-bottom: 4px; font-size: 9pt; }}
.note {{ background:#fff7e0; border:1px solid #e6d28a; padding:6px 8px; font-size: 9.5pt; }}</style></head><body>
<h1>PHYTORYX</h1><div class="tag">Intelligence Rooted in Nature.</div>
<h2>Dataset documentation</h2>
<p>Third-party entries are marked verified only if their licence was read from the original source. Access, use and redistribution are recorded as separate permissions; public accessibility never implies redistribution rights.</p>
<div class="note"><b>Key points.</b> (1) The 265 original leaf photographs are included with redistribution status <b>owner-authorised</b>, based on the project owner's confirmation of rights/permission; <b>no Creative Commons or other public licence is asserted</b>, labels and sample identifiers are unchanged, and author/date/location/species are not recorded. (2) PlantDoc (test split) and two Zenodo FTIR files are redistributed under their verified CC BY 4.0 licences, with attribution. (3) The 150 COCO non-leaf images are <b>excluded from public redistribution</b> until their licence terms are verified. (4) Open-Meteo values are <b>modelled</b> (CAMS), not measured; the free tier is non-commercial. (5) No species, Spiral, dust-mask, bacterial/fungal or paired image-FTIR-pollution dataset was found or verified.</div>
<h2>Inventory</h2><table><tr><th>ID</th><th>Name</th><th>Licence</th><th>Redistribution status</th><th>Status in PHYTORYX</th></tr>{inv}</table>
<h2>Details</h2>{detail}<h2>Citations and attributions</h2><ul>{cit_html}</ul>
</body></html>"""
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("Edge/Chrome not found")
    with tempfile.TemporaryDirectory() as t:
        h = Path(t) / "doc.html"
        h.write_text(doc, encoding="utf-8")
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", h.as_uri()],
                       check=True, capture_output=True, timeout=120)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "PHYTORYX_DATASET_DOCUMENTATION.pdf")
