"""How does the deployed pipeline treat leaves it has never seen (PlantDoc test images: other species, field photos)?

PlantDoc has NO phyllotaxy labels, so accuracy cannot be computed. We report only the decision breakdown (accepted / abstained /
rejected) and which class was accepted - an ACCEPTED answer on these images cannot be verified and should be read as over-confidence risk.
Usage: python scripts/ood_familiarity_eval.py <plantdoc_test_dir> [out_json]
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageOps  # noqa: E402

from phyllo.paths import RESULTS  # noqa: E402


def main(root, out=None):
    from phyllo.pipeline import PhylloEngine
    eng = PhylloEngine(load_aqi_model=False)
    imgs = sorted(p for p in Path(root).rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    status, accepted_cls = Counter(), Counter()
    per_group = {}
    for p in imgs:
        with Image.open(p) as im:
            img = ImageOps.exif_transpose(im).convert("RGB")
        r = eng.predict(img, explain=False)
        st = r["decision"]["status"]
        status[st] += 1
        if st == "ACCEPT":
            accepted_cls[r["phyllotaxy"]["class"]] += 1
        g = per_group.setdefault(p.parent.name, Counter())
        g[st] += 1
    n = len(imgs)
    res = {"dataset": "PlantDoc test split (CC BY 4.0), no phyllotaxy labels", "n_images": n, "decision_status": dict(status),
           "fraction": {k: round(v / n, 3) for k, v in status.items()}, "accepted_by_class": dict(accepted_cls),
           "per_folder": {k: dict(v) for k, v in sorted(per_group.items())},
           "note": "Accepted answers cannot be verified (no labels). A high ACCEPT fraction on unfamiliar species/field photos would indicate over-confidence."}
    out = Path(out) if out else RESULTS / "v2_unfamiliar_eval.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_images", "decision_status", "fraction", "accepted_by_class")}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
