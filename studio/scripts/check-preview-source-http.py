#!/usr/bin/env python3
"""Verify that Studio serves the exact bundled catalog source bytes over HTTP.

All HTTP operations are GET requests to the supplied local Studio origin. Hash
comparisons against both public and dist reject missing-asset SPA fallbacks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlparse
from urllib.request import ProxyHandler, build_opener


PROJECT = Path(__file__).resolve().parents[2]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8891")
    parser.add_argument("--public", type=Path, default=PROJECT / "studio/public")
    parser.add_argument("--dist", type=Path, default=PROJECT / "studio/dist")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/evidence/preview-sources-20261014/http-source-assets.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    parsed = urlparse(args.base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.path not in {"", "/"}:
        parser.error("base must be an HTTP origin for the local Studio")
    base, public, dist = args.base.rstrip("/"), args.public.resolve(), args.dist.resolve()
    preview = public / "preview"
    resources: dict[str, dict] = {}
    errors = []

    def add(relative: str, kind: str, declared_sha256: str | None = None) -> None:
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative:
            raise ValueError("Unsafe resource path: " + relative)
        url_path = "/" + relative
        if url_path not in resources:
            public_path, dist_path = public / relative, dist / relative
            expected = public_path.read_bytes()
            built = dist_path.read_bytes()
            digest = sha256(expected)
            resources[url_path] = {"path": url_path, "kinds": [], "expected_bytes": len(expected), "expected_sha256": digest,
                                   "public_sha256": digest, "dist_sha256": sha256(built), "dist_public_match": expected == built}
            if expected != built:
                errors.append("dist differs from public: " + relative)
        item = resources[url_path]
        if kind not in item["kinds"]:
            item["kinds"].append(kind)
        if declared_sha256:
            if item["expected_sha256"] != declared_sha256:
                errors.append("manifest differs from public: " + relative)
            item["declared_sha256"] = declared_sha256

    index = json.loads((preview / "data/catalog-sources.json").read_text(encoding="utf-8"))
    packages = json.loads((preview / "data/source-packages.json").read_text(encoding="utf-8"))
    ledger = json.loads((preview / "data/notebook-conversions.json").read_text(encoding="utf-8"))
    integration = json.loads((preview / "integration-manifest.json").read_text(encoding="utf-8"))
    for path in ("data/catalog.json", "data/catalog-sources.json", "data/source-packages.json", "data/notebook-conversions.json",
                 "integration-manifest.json", "vendor-manifest.json", "sources/README.md"):
        add("preview/" + path, "metadata")
    for descriptor in index["cases"].values():
        for item in descriptor.get("files", []):
            add("preview/" + item["asset"], "catalog-source", item["sha256"])
        if descriptor.get("evidence"):
            add("preview/" + descriptor["evidence"], "catalog-evidence")
    for package in packages["packages"].values():
        for item in package.get("files", []):
            add("preview/" + item["asset"], "package-source", item["sha256"])
        for item in package.get("licenses", []):
            add("preview/" + item["asset"], "package-license", item["sha256"])
    for record in ledger["notebooks"]:
        add("preview/" + record["canonical_python"], "notebook-python", record["python_sha256"])
    for record in integration["files"]:
        add("preview/" + record["path"], "integration-file", record["sha256"])

    built_html = (dist / "index.html").read_bytes()
    root_record = {"path": "/", "kinds": ["studio-html"], "expected_bytes": len(built_html), "expected_sha256": sha256(built_html),
                   "dist_sha256": sha256(built_html), "dist_public_match": None}
    resources["/"] = root_record
    bundle_paths = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', built_html.decode("utf-8"))
    for path in bundle_paths:
        data = (dist / path.lstrip("/")).read_bytes()
        resources[path] = {"path": path, "kinds": ["studio-bundle"], "expected_bytes": len(data),
                           "expected_sha256": sha256(data), "dist_sha256": sha256(data), "dist_public_match": None}

    # Create one opener per request; proxy environment settings are irrelevant to localhost.
    def fetch(item: dict) -> dict:
        record = dict(item)
        try:
            with build_opener(ProxyHandler({})).open(base + quote(item["path"], safe="/"), timeout=15) as response:
                data = response.read()
                record.update(status=response.status, content_type=response.headers.get_content_type(),
                              http_bytes=len(data), http_sha256=sha256(data), exact_match=data is not None and
                              len(data) == item["expected_bytes"] and sha256(data) == item["expected_sha256"])
        except Exception as error:
            record.update(exact_match=False, error=type(error).__name__ + ": " + str(error))
        return record

    print(json.dumps({"event": "checking", "base": base, "resources": len(resources), "bundle_paths": bundle_paths}, ensure_ascii=False), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 16))) as executor:
        checked = list(executor.map(fetch, [resources[path] for path in sorted(resources)]))
    failed = [record for record in checked if not record["exact_match"]]
    errors.extend("HTTP bytes do not match bundle: " + record["path"] for record in failed)
    report = {"schema": "archcanvas-preview-source-http-validation/1", "generated_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Read-only HTTP GET of source, evidence, license, Notebook Python, metadata, integration and Studio bundle assets; bytes must match the local dist and public files",
              "base": base, "ok": not errors, "resources_checked": len(checked), "resources_passed": len(checked) - len(failed),
              "bundle_paths": bundle_paths, "source_metadata": {"schema": index.get("schema"), "source_layout": index.get("sourceLayout"),
              "catalog_cases": len(index["cases"]), "available_cases": sum(bool(record.get("available")) for record in index["cases"].values()),
              "packages": len(packages["packages"]), "package_counts": packages.get("counts"), "notebook_count": ledger["notebook_count"],
              "notebook_python_assets": ledger["python_asset_count"]}, "dist_public_matches": all(record["dist_public_match"] is not False for record in checked),
              "manifest_public_matches": not any(error.startswith("manifest differs") for error in errors), "errors": errors, "resources": checked}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "resources_checked": len(checked), "resources_passed": report["resources_passed"],
                      "errors": errors[:12], "report": str(args.output)}, ensure_ascii=False), flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
