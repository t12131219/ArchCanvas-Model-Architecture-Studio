"""Read a declared frozen manifest; bind inputs and inventory native images.

This helper does not decide aesthetic correctness. The reviewer must personally
view each image. No browser interaction, source edits, model execution, or tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def binding(path: Path, root: Path) -> dict:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    manifest = Path(args.manifest).resolve()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    declared = json.loads(manifest.read_text())
    records = declared["records"]
    observed = []
    failures = []
    images = []
    for expected in records:
        path = (root / expected["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Input escapes project root")
        actual = binding(path, root)
        matched = actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"]
        observed.append({"expected": expected, "actual": actual, "exact": matched})
        if not matched:
            failures.append(actual["path"])
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            with Image.open(path) as im:
                size = list(im.size)
            images.append({"input": actual, "nativeSize": size})
    result = {
        "schemaVersion": 1,
        "kind": "independent-frozen-input-readback",
        "manifest": binding(manifest, root),
        "records": observed,
        "count": len(observed),
        "allDeclaredBindingsExact": not failures,
        "failures": failures,
        "images": images,
        "doesNotCertifyPixelCorrectness": True,
    }
    (out / "input-readback.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"inputCount": len(observed), "imageCount": len(images), "bindingsExact": not failures}))


if __name__ == "__main__":
    main()
