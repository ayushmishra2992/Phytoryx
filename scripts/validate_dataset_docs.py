"""Validate dataset-rights documentation consistency and that the 265 leaf photographs are untouched. Read-only.

Usage: python scripts/validate_dataset_docs.py [--baseline hashes.csv] [--archive new.zip] [--published-archive old.zip]
  --baseline            CSV lines "<split>/<Class>/<file>,<SHA256 upper>" recorded BEFORE the documentation edits
  --archive             the next-release permitted-dataset archive to inspect
  --published-archive   the already-published archive (e.g. v1.0.0 asset, local copy) to compare image hashes against
"""
import argparse
import csv
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "v2" / "data_registry"
RESULTS = []


def check(name, fn):
    try:
        info = fn()
        RESULTS.append(True)
        print(f"  PASS  {name}" + (f" - {info}" if info else ""))
    except Exception as ex:  # noqa: BLE001
        RESULTS.append(False)
        print(f"  FAIL  {name}: {ex}")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def leaf_entries(zf):
    out = {}
    for i in zf.infolist():
        n = i.filename.replace("\\", "/")
        m = re.match(r"^project_leaf_photos/split_4class/((?:train|val|test)/(?:Alternate|Opposite|Whorled)/[^/]+\.(?:jpeg|jpg|png))$", n, re.I)
        if m:
            out[m.group(1)] = hashlib.sha256(zf.read(i)).hexdigest().upper()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline")
    ap.add_argument("--archive")
    ap.add_argument("--published-archive")
    a = ap.parse_args()
    man = list(csv.DictReader(open(REG / "LEAF_PHOTOS_MANIFEST.csv", encoding="utf-8", newline="")))
    reg = {r["dataset_id"]: r for r in csv.DictReader(open(REG / "dataset_registry.csv", encoding="utf-8", newline=""))}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sources = (REG / "DATASET_SOURCES.md").read_text(encoding="utf-8")
    cites = (ROOT / "CITATIONS.md").read_text(encoding="utf-8")
    base = {}
    if a.baseline:
        for line in open(a.baseline, encoding="utf-8"):
            k, _, h = line.strip().partition(",")
            if k:
                base[k] = h.upper()

    def t_manifest():
        assert len(man) == 265 and len({r["key"] for r in man}) == 265
        counts = {}
        for r in man:
            p = ROOT / r["file"]
            assert p.exists(), r["file"]
            assert sha(p) == r["sha256"].upper(), f"hash changed: {r['file']}"
            assert r["label"] == p.parent.name == r["key"].split("/")[0] and r["key"].split("/")[1] == p.name
            assert r["redistribution_status"] == "owner-authorised"
            counts[r["label"]] = counts.get(r["label"], 0) + 1
        assert counts == {"Alternate": 88, "Opposite": 83, "Whorled": 94}, counts
        n_files = sum(1 for p in (ROOT / "data/processed/split_4class").rglob("*") if p.suffix.lower() in (".jpeg", ".jpg", ".png")
                      and "not_a_leaf" not in str(p).lower())
        assert n_files == 265, n_files
        return f"265 files, hashes match manifest, labels {counts}"

    def t_baseline():
        if not base:
            return "skipped (no --baseline)"
        cur = {r["file"].replace("data/processed/split_4class/", ""): r["sha256"].upper() for r in man}
        assert set(cur) == set(base), (len(cur), len(base), list(set(cur) ^ set(base))[:3])
        diff = [k for k in cur if cur[k] != base[k]]
        assert not diff, diff[:3]
        return f"identical to pre-edit baseline ({len(base)} paths/hashes)"

    def t_archive():
        if not a.archive:
            return "skipped (no --archive)"
        with zipfile.ZipFile(a.archive) as zf:
            names = [i.filename.replace("\\", "/") for i in zf.infolist()]
            lf = leaf_entries(zf)
            assert len(lf) == 265, len(lf)
            exp = {r["file"].replace("data/processed/split_4class/", ""): r["sha256"].upper() for r in man}
            assert lf == exp, "archive leaf images differ from manifest"
            assert not [n for n in names if "not_a_leaf" in n.lower()], "COCO/non-leaf path in archive"
            rights = zf.read("project_leaf_photos/RIGHTS_STATUS.txt").decode("utf-8")
            assert "owner-authorised" in rights and "No Creative Commons" in rights and "NOT included" in rights
        return "265 identical leaf images, no non-leaf/COCO paths, RIGHTS_STATUS correct"

    def t_published():
        if not a.published_archive:
            return "skipped (no --published-archive)"
        with zipfile.ZipFile(a.published_archive) as zf:
            old = leaf_entries(zf)
        exp = {r["file"].replace("data/processed/split_4class/", ""): r["sha256"].upper() for r in man}
        assert len(old) == 265 and old == exp, (len(old), len([k for k in exp if old.get(k) != exp[k]]))
        return "all 265 image hashes/paths/labels identical to the published v1.0.0 archive"

    def t_registry():
        lp = reg["images_project_leaf_photos"]
        assert lp["redistribution_status"] == "owner-authorised"
        assert "Project owner confirmation" in lp["rights_basis"] and lp["licence"].startswith("No licence asserted")
        assert "265" in lp["n_samples"] and lp["project_status"].startswith("INCLUDED (owner-authorised)")
        for rid, r in reg.items():
            if rid == "images_project_leaf_photos":
                continue   # its licence text says "no Creative Commons ... is claimed"; checked precisely below (no CC BY / CC0 token)
            if re.search(r"CC[- ]?BY|CC0|Creative Commons", r["licence"], re.I) and rid not in (
                    "ftir_hemp_zenodo_17165736", "ftir_latvian_herbs_zenodo_16892975", "disease_plantdoc", "env_openmeteo_cams", "env_openaq", "geo_openmeteo_geocoding"):
                raise AssertionError(f"unexpected CC licence claim on {rid}")
        assert not re.search(r"CC[- ]?BY|CC0", lp["licence"] + lp["rights_basis"])
        co = reg["images_coco_non_leaf"]
        assert co["redistribution_status"].startswith("EXCLUDED") and "NOT redistributed" in co["project_status"]
        for rid in ("disease_plantdoc", "ftir_hemp_zenodo_17165736"):
            assert "CC BY 4.0" in reg[rid]["licence"].replace("CC-BY-4.0", "CC BY 4.0"), f"third-party licence lost on {rid}: {reg[rid]['licence']!r}"
        assert all(r.get("permission_summary") for r in reg.values())
        return "owner-authorised row, no CC claim on leaf/COCO rows, COCO excluded, all rows have permission_summary"

    def t_docs_agree():
        for name, txt in (("README", readme), ("DATASET_SOURCES", sources), ("CITATIONS", cites)):
            assert "owner-authorised" in txt or name == "CITATIONS" and "owner-authorised" in txt, name
            assert not re.search(r"owner to confirm|rights to be confirmed|No licence recorded", txt, re.I), f"stale rights wording in {name}"
        for name, txt in (("README", readme), ("DATASET_SOURCES", sources), ("CITATIONS", cites)):
            assert re.search(r"COCO", txt) and re.search(r"exclud|not redistributed", txt, re.I), name
        assert "No Creative Commons" in sources and "no Creative Commons" in readme.replace("No Creative", "no Creative")
        assert "10.1145/3371158.3371196" in cites and "10.5281/zenodo.17165736" in cites and cites.count("CC BY 4.0") >= 3
        assert "LEAF_PHOTOS_MANIFEST.csv" in sources and "LEAF_PHOTOS_MANIFEST.csv" in readme
        return "README, DATASET_SOURCES, CITATIONS and registry agree; PlantDoc/Zenodo attribution intact"

    def t_readme_ack():
        need = ["### Acknowledgements & Dataset Attribution",
                "PHYTORYX is built upon the contributions of researchers, dataset creators and the open scientific community.",
                "We sincerely thank the original dataset authors, researchers and institutions whose work and publicly available resources supported the development, experimentation and evaluation of this project.",
                "We acknowledge each dataset provider in accordance with its applicable licence and attribution requirements. Original dataset ownership remains with its respective creators and rights holders.",
                "The original leaf-image collection used in this project is included with the project owner's authorisation. Other datasets and research materials are redistributed only where their applicable terms permit.",
                "Please refer to `CITATIONS.md` and `v2/data_registry/DATASET_SOURCES.md` for individual dataset sources, licences and attribution details.",
                "### Disclaimer",
                "PHYTORYX is an experimental AI research platform. Its predictions and analytical outputs may be uncertain and should not be treated as definitive botanical, medical, microbiological or environmental measurements.",
                "Dataset limitations, model uncertainty and module-specific constraints should be considered when interpreting results."]
        missing = [s[:50] for s in need if s not in readme]
        assert not missing, missing
        assert readme.rstrip().endswith(need[-1]), "acknowledgements must be at the end of the README"
        return "verbatim section present at the end"

    for n, f in [("manifest: 265 images, hashes, labels, status", t_manifest), ("images unchanged vs pre-edit baseline", t_baseline),
                 ("next-release archive contents", t_archive), ("images identical to the published v1.0.0 archive", t_published),
                 ("registry: rights status, no unsupported CC, COCO excluded", t_registry), ("README / sources / citations agree", t_docs_agree),
                 ("README acknowledgements + disclaimer (verbatim, at end)", t_readme_ack)]:
        check(n, f)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    main()
