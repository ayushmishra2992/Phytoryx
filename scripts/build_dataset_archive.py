"""Build the permitted-dataset archive (PHYTORYX_datasets_permitted.zip) for a release.

Contents: the 265 original leaf photographs (owner-authorised), their metadata + LEAF_PHOTOS_MANIFEST.csv, the CC BY 4.0 Zenodo FTIR sample,
optionally the full PlantDoc test split (CC BY 4.0; fetched with scripts/fetch_plantdoc_ood.py), and the registry/sources/citations/PDF.
COCO-derived non-leaf images are NEVER included (redistribution rights not verified); the script refuses to add any such path.
Usage: python scripts/build_dataset_archive.py <out.zip> [--plantdoc <dir with test/, LICENSE.txt, manifest.csv>]
"""
import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "v2" / "data_registry"

RIGHTS = """RIGHTS STATUS OF THE 265 ORIGINAL LEAF PHOTOGRAPHS
Redistribution status: owner-authorised.
Basis: the project owner's explicit confirmation - "The project owner holds the rights or necessary permission to redistribute all 265 original
leaf photographs included in the Phyllo-ViT dataset." This is the owner's rights/permission confirmation, not a public licence.
No Creative Commons or other public licence is asserted. Ownership remains with the respective rights holders.
Labels (class folders Alternate/Opposite/Whorled), filenames and sample identifiers are unchanged; see LEAF_PHOTOS_MANIFEST.csv (SHA-256 per image).
Provenance NOT recorded and not claimed: author/photographer, collection date or session, location, species, plant ID, camera (images carry no EXIF).
COCO non-leaf images are deliberately NOT included (redistribution rights and licence terms unverified).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--plantdoc", default=None)
    a = ap.parse_args()
    entries = []   # (arcname, source Path or bytes)
    for split in ("train", "val", "test"):
        for label in ("Alternate", "Opposite", "Whorled"):
            for p in sorted((ROOT / "data" / "processed" / "split_4class" / split / label).iterdir()):
                if p.suffix.lower() in (".jpeg", ".jpg", ".png"):
                    entries.append((f"project_leaf_photos/split_4class/{split}/{label}/{p.name}", p))
    entries.append(("project_leaf_photos/split_4class/split_metadata.csv", ROOT / "data/processed/split_4class/split_metadata.csv"))
    for f in ("metadata.csv", "provenance_annotation_TODO.csv"):
        entries.append((f"project_leaf_photos/metadata/{f}", ROOT / "data/metadata" / f))
    entries.append(("project_leaf_photos/LEAF_PHOTOS_MANIFEST.csv", REG / "LEAF_PHOTOS_MANIFEST.csv"))
    entries.append(("project_leaf_photos/RIGHTS_STATUS.txt", RIGHTS.encode("utf-8")))
    for f in ("W1_C.xlsx", "Sample_name_codification.xlsx"):
        entries.append((f"ftir_zenodo_17165736_CC-BY-4.0/{f}", REG / "samples" / f))
    entries.append(("ftir_zenodo_17165736_CC-BY-4.0/ATTRIBUTION.txt",
                    ("Source: https://zenodo.org/records/17165736 | Licence: CC BY 4.0 | Jara Villamayor, Herrera, Marsal, Arrua Alvarenga, "
                     "DOI 10.5281/zenodo.17165736 | 2 of 19 files, unmodified, MD5 verified. Wavenumber column is integers x1000; absorbance uses comma decimals.").encode()))
    if a.plantdoc:
        pd = Path(a.plantdoc)
        for p in sorted(pd.rglob("*")):
            if p.is_file():
                entries.append(("plantdoc_test_split_CC-BY-4.0/" + p.relative_to(pd).as_posix(), p))
        entries.append(("plantdoc_test_split_CC-BY-4.0/ATTRIBUTION.txt",
                        ("Source: https://github.com/pratikkayal/PlantDoc-Dataset | Licence: CC BY 4.0 (LICENSE.txt) | Singh et al., CoDS-COMAD 2020, "
                         "DOI 10.1145/3371158.3371196 | Filenames sanitised for Windows; content unmodified; manifest.csv lists original path and SHA-256.").encode()))
    for f in ("dataset_registry.csv", "DATASET_SOURCES.md"):
        entries.append((f, REG / f))
    entries.append(("CITATIONS.md", ROOT / "CITATIONS.md"))
    pdf = ROOT / "docs" / "PHYTORYX_DATASET_DOCUMENTATION.pdf"
    if pdf.exists():
        entries.append(("PHYTORYX_DATASET_DOCUMENTATION.pdf", pdf))
    bad = [n for n, _ in entries if "not_a_leaf" in n.lower() or "coco" in n.lower().replace("coco-", "")]
    assert not bad, f"refusing to archive COCO-derived paths: {bad[:3]}"
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, src in entries:
            z.write(src, name) if isinstance(src, Path) else z.writestr(name, src)
    n_leaf = sum(1 for n, _ in entries if n.startswith("project_leaf_photos/split_4class/") and n.lower().endswith((".jpeg", ".jpg", ".png")))
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(entries)} entries, {n_leaf} leaf photographs)")


if __name__ == "__main__":
    main()
