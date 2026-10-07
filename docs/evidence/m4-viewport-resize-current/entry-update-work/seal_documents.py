"""Seal finalized stage docs and their named byte relationships; no product action."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def bind(path, base):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(base)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path):
    return json.loads((ROOT / path).read_bytes())


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--readback", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    facts, readback = read(args.facts), read(args.readback)
    assert facts["status"] == "final_facts_ready" and readback["passed"] == readback["total"]
    external = {row["path"]: row for row in readback["currentInputs"] + facts["evidenceBindings"]}
    checks = read(facts["buildReceipt"])
    for row in checks["inputs"] + checks["build"] + checks["publicationInputs"]:
        external[row["path"]] = {k: row[k] for k in ["path", "bytes", "sha256"]}
    archive = read("docs/evidence/m4-viewport-resize-current/entry-update-work/before-entry-manifest.json")
    for row in archive["inputs"]:
        external[row["snapshot"]] = {"path": row["snapshot"], "bytes": row["bytes"], "sha256": row["sha256"]}
    external[args.facts] = bind(ROOT / args.facts, ROOT)
    external[args.readback] = bind(ROOT / args.readback, ROOT)
    for path in sorted(HERE.rglob("*")):
        if path.is_file():
            external[str(path.relative_to(ROOT))] = bind(path, ROOT)
    for path, row in sorted(external.items()):
        assert bind(ROOT / path, ROOT) == row, path
    output = ROOT / args.output
    assert ROOT in output.parents and not output.exists(), "Retain earlier seals"
    output.mkdir(parents=True)
    report = {"schema": "archcanvas-viewport-document-seal/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
              "sourceReceiptBindingsExact": 126, "documentationReadbackPassed": readback["passed"],
              "documentationReadbackTotal": readback["total"], "externalBindingCount": len(external),
              "externalBindings": list(external.values()),
              "scope": "Named final docs/preparation/current source/build/publication and frozen evidence byte relationships; not a full transitive distribution, browser pixel, model execution, researcher or presented performance certification."}
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest_raw = (output / "manifest.json").read_bytes()
    print(json.dumps({"bindingsExact": len(external), "manifestSha256": hashlib.sha256(manifest_raw).hexdigest()}))


if __name__ == "__main__":
    main()
