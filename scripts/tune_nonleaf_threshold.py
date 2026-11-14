"""Select the P(Not_a_leaf) threshold for the NOT_A_LEAF decision using DEVELOPMENT data only.

PRE-REGISTERED RULE (written before running):
  development leaves  = PlantDoc TRAIN images (CC BY 4.0), minus exact SHA-256 duplicates of any PlantDoc TEST image, minus within-train duplicates
  development non-leaf = COCO VALIDATION images (local only, not redistributed; the model never trained on them)
  tau = the largest value of the grid {0.50, 0.55, ..., 0.95} for which ALL development non-leaf images keep P(Not_a_leaf) >= tau
        (recall 100 % on the 22 COCO validation images).
  The threshold is written to the artifact ONLY IF the false-NOT_A_LEAF rate on development leaves at tau is <= 10 %;
  otherwise the artifact is left unchanged (previous argmax behaviour) and this is reported.
Not used for selection: the PlantDoc TEST split (already inspected), the COCO TEST images, any own-collection leaf.
Limits: near-duplicates across PlantDoc train/test are not measured (exact duplicates only); only 22 non-leaf images; no leaf-like negatives.

Usage: python scripts/tune_nonleaf_threshold.py <plantdoc.tgz> <plantdoc_test_manifest.csv> <coco_val_dir> [--write]
"""
import csv
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy.special import softmax

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phyllo.paths import ARTIFACTS, RESULTS  # noqa: E402
from phyllo.pipeline import PhylloEngine  # noqa: E402

GRID = [round(x, 2) for x in np.arange(0.50, 0.951, 0.05)]
MAX_DEV_FALSE_RATE = 0.10


def p_nonleaf(eng, img):
    enc = eng.clf.encode([img], attentions=False)
    return float(softmax(enc["logits"] / eng.T, axis=1)[0][eng.classes.index("Not_a_leaf")])


def main(tgz, test_manifest, coco_val, write):
    test_hashes = {r["sha256"] for r in csv.DictReader(open(test_manifest, encoding="utf-8"))}
    eng = PhylloEngine(load_aqi_model=False)
    dev, seen, dup_test, dup_train = [], set(), 0, 0
    with tarfile.open(tgz, "r:gz") as tf:
        for m in tf:
            if not m.isfile() or not m.name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            parts = m.name.split("/", 1)[1].split("/")
            if parts[0] != "train":
                continue
            data = tf.extractfile(m).read()
            h = hashlib.sha256(data).hexdigest()
            if h in test_hashes:
                dup_test += 1
                continue
            if h in seen:
                dup_train += 1
                continue
            seen.add(h)
            try:
                img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            except Exception:  # noqa: BLE001
                continue
            dev.append(p_nonleaf(eng, img))
    leaf = np.array(dev)
    coco = []
    for p in sorted(Path(coco_val).iterdir()):
        with Image.open(p) as im:
            coco.append(p_nonleaf(eng, ImageOps.exif_transpose(im).convert("RGB")))
    coco = np.array(coco)

    table = []
    for t in GRID:
        table.append({"tau": t, "dev_leaf_false_notaleaf_rate": round(float((leaf >= t).mean()), 4),
                      "dev_nonleaf_recall": round(float((coco >= t).mean()), 4)})
    ok = [r for r in table if r["dev_nonleaf_recall"] == 1.0]
    chosen = max(ok, key=lambda r: r["tau"]) if ok else None
    rng = np.random.default_rng(0)
    ci = None
    if chosen:
        bs = [float((leaf[rng.integers(0, len(leaf), len(leaf))] >= chosen["tau"]).mean()) for _ in range(2000)]
        ci = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
    accept = bool(chosen and chosen["dev_leaf_false_notaleaf_rate"] <= MAX_DEV_FALSE_RATE)
    res = {"rule": __doc__.split("PRE-REGISTERED RULE")[1].split("Not used for selection")[0].strip(),
           "n_dev_leaves": int(len(leaf)), "excluded_exact_duplicates_of_test": dup_test, "excluded_within_train_duplicates": dup_train,
           "n_dev_nonleaf_coco_val": int(len(coco)), "coco_val_p_nonleaf_min": round(float(coco.min()), 4),
           "dev_leaf_p_nonleaf_quantiles": {q: round(float(np.quantile(leaf, q)), 4) for q in (0.1, 0.5, 0.9, 0.99)},
           "grid": table, "chosen": chosen, "chosen_false_rate_ci95_bootstrap": ci, "applied": accept,
           "limits": "exact-duplicate dedup only; 22 development non-leaf images; no leaf-like negatives; PlantDoc test already inspected (exploratory)"}
    (RESULTS / "v2_nonleaf_threshold.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_dev_leaves", "excluded_exact_duplicates_of_test", "n_dev_nonleaf_coco_val", "coco_val_p_nonleaf_min",
                                           "dev_leaf_p_nonleaf_quantiles", "chosen", "chosen_false_rate_ci95_bootstrap", "applied")}, indent=2))
    if write and accept:
        p = ARTIFACTS / "reliability_ft4.json"
        cfg = json.loads(p.read_text(encoding="utf-8"))
        cfg["thresholds"]["nonleaf_probability"] = chosen["tau"]
        cfg["nonleaf_probability_provenance"] = ("selected on development data only (PlantDoc train minus exact test duplicates; COCO validation); "
                                                 "see results/v2_nonleaf_threshold.json; NOT tuned on PlantDoc test or COCO test")
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print("artifact updated:", p)
    elif write:
        print("NOT applied: rule not satisfied; artifact unchanged")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], "--write" in sys.argv)
