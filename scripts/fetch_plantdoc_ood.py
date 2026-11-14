"""Extract PlantDoc (CC BY 4.0) `test/` images + LICENSE from a GitHub tarball into a Windows-safe folder, with a manifest.

PlantDoc-Dataset (Singh et al., CoDS-COMAD 2020, DOI 10.1145/3371158.3371196) has filenames containing characters Windows cannot store
(`?`, `=` ...), so a normal git checkout fails on Windows. This script sanitises names and records original path, sanitised path and SHA-256.
Usage: python scripts/fetch_plantdoc_ood.py <tarball.tgz> <out_dir>
Tarball: https://api.github.com/repos/pratikkayal/PlantDoc-Dataset/tarball/master
"""
import csv
import hashlib
import re
import sys
import tarfile
from pathlib import Path

IMG = (".jpg", ".jpeg", ".png")


def safe(name):
    return re.sub(r'[<>:"|?*=&%\\]', "_", name)[:120]


def main(tgz, out):
    out = Path(out)
    rows = []
    with tarfile.open(tgz, "r:gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            parts = m.name.split("/", 1)[1].split("/") if "/" in m.name else [m.name]
            rel = "/".join(parts)
            if rel in ("LICENSE.txt", "README.md"):
                dst = out / rel
            elif parts[0] == "test" and rel.lower().endswith(IMG):
                dst = out / "test" / safe(parts[1]) / safe(parts[-1])
            else:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = tf.extractfile(m).read()
            dst.write_bytes(data)
            if parts[0] == "test":
                rows.append({"original_path": rel, "local_path": str(dst.relative_to(out)).replace("\\", "/"),
                             "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["original_path", "local_path", "sha256", "bytes"])
        w.writeheader()
        w.writerows(rows)
    print(f"extracted {len(rows)} test images -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
