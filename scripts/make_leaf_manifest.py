"""Write v2/data_registry/LEAF_PHOTOS_MANIFEST.csv for the 265 original leaf photographs (read-only on the images).

Sample identifier `key` = "<Class>/<filename>" exactly as used in data/metadata/provenance_annotation_TODO.csv; `label` is the class folder
(unchanged); `image_id` comes from data/metadata/metadata.csv when (label, filename) matches a non-duplicate row there.
Only facts derivable from the files/metadata are recorded. No author, date, location or licence is invented.
Usage: python scripts/make_leaf_manifest.py
"""
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / "data" / "processed" / "split_4class"
OUT = ROOT / "v2" / "data_registry" / "LEAF_PHOTOS_MANIFEST.csv"
STATUS = "owner-authorised"
BASIS = "Project owner confirmation of redistribution rights/permission (no public licence asserted)"
LABELS = ("Alternate", "Opposite", "Whorled")


def main():
    meta = {}
    with open(ROOT / "data" / "metadata" / "metadata.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["is_duplicate"] == "False":
                meta[(r["phyllotaxy"], r["filename"])] = r["image_id"]
    rows = []
    for split in ("train", "val", "test"):
        for label in LABELS:
            for p in sorted((SPLIT / split / label).iterdir()):
                if p.suffix.lower() not in (".jpeg", ".jpg", ".png"):
                    continue
                rows.append({"key": f"{label}/{p.name}", "label": label, "split": split, "image_id": meta.get((label, p.name), ""),
                             "file": f"data/processed/split_4class/{split}/{label}/{p.name}",
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size,
                             "redistribution_status": STATUS, "rights_basis": BASIS})
    keys = [r["key"] for r in rows]
    assert len(rows) == 265 and len(set(keys)) == 265, (len(rows), len(set(keys)))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[r["label"]] = by.get(r["label"], 0) + 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows {by}; image_id matched for {sum(1 for r in rows if r['image_id'])}")


if __name__ == "__main__":
    sys.exit(main())
