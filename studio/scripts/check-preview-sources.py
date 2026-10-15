#!/usr/bin/env python3
"""Independently audit the Studio catalog's source assets without executing models.

Reads the catalog, Python ASTs, source hashes and Notebook conversion ledger.
The formal authoring analyzer only reads a temporary text corpus. This script
does not import supplied model code, instantiate models or download dependencies.
Parser limitations are reported separately from missing or invalid assets.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import keyword
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone


PROJECT = Path(__file__).resolve().parents[2]
MAGIC = re.compile(r"^\s*(?:%{1,2}[A-Za-z_]\w*\b|![A-Za-z_])")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identifier(value: str) -> bool:
    return value.isidentifier() and not keyword.iskeyword(value)


def asset(root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError("Resource path is not text")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Resource path leaves the preview root: {relative}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Resource resolves outside the preview root: {relative}")
    return target


def normalized_entry(raw: str | None) -> tuple[str, str, list[str]]:
    if not isinstance(raw, str) or not raw:
        raise ValueError("Source entry is missing")
    if "::" in raw:
        path, symbol = raw.split("::", 1)
        module = path.removesuffix(".py").replace("/", ".")
    else:
        module, separator, symbol = raw.partition(":")
        if not separator:
            raise ValueError("Entry must contain module:Class or file.py::Class")
    module = module.removesuffix(".__init__")
    symbols = symbol.split(".")
    if not all(identifier(part) for part in module.split(".")) or not all(identifier(part) for part in symbols):
        raise ValueError(f"Entry is not a legal Python module and class: {raw}")
    return module + ":" + symbols[0], module, symbols


def entry_check(raw: str | None, trees: dict[str, ast.Module]) -> dict:
    entry, module, symbols = normalized_entry(raw)
    candidates = [module.replace(".", "/") + ".py", module.replace(".", "/") + "/__init__.py"]
    logical = next((path for path in candidates if path in trees), None)
    if not logical:
        raise ValueError(f"Entry file absent from source corpus: {candidates}")
    if symbols == ["__module__"]:
        return {"normalized": entry, "path": logical, "symbol": "__module__", "kind": "module", "line": 1}
    current = next((node for node in trees[logical].body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbols[0]), None)
    if current is None:
        raise ValueError(f"Entry symbol absent from {logical}: {symbols[0]}")
    kind = "class" if isinstance(current, ast.ClassDef) else "function"
    for name in symbols[1:]:
        current = next((node for node in current.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name), None)
        if current is None:
            raise ValueError(f"Entry member absent from {logical}: {'.'.join(symbols)}")
    return {"normalized": entry, "path": logical, "symbol": ".".join(symbols), "kind": kind, "line": current.lineno}


def import_audit(trees: dict[str, ast.Module]) -> list[dict]:
    """Record unresolved relative imports; no dependency is inferred or fetched."""
    result = []
    for logical, tree in trees.items():
        package = PurePosixPath(logical).parent.parts
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            if node.level > len(package):
                result.append({"path": logical, "line": node.lineno, "import": "." * node.level + (node.module or ""),
                               "status": "relative-import-outside-corpus"})
                continue
            parts = list(package[:len(package) - node.level + 1])
            if node.module:
                modules = [parts + node.module.split(".")]
            else:
                modules = [parts + [name.name] for name in node.names if name.name != "*"]
            for segments in modules:
                module = "/".join(segments)
                candidates = [module + ".py", module + "/__init__.py"]
                if not any(path in trees for path in candidates):
                    result.append({"path": logical, "line": node.lineno,
                                   "import": "." * node.level + (node.module or ",".join(name.name for name in node.names)),
                                   "candidate_paths": candidates, "status": "unprovided-relative-module-or-symbol"})
    return result


def error_category(error: Exception) -> str:
    message = str(error)
    if "Entry must" in message or "模型入口" in message:
        return "entry-contract"
    if "80" in message or "2 MB" in message or "480" in message or "1200" in message or "3600" in message:
        return "analysis-budget"
    if "inherit" in message or "继承" in message or "statically proven to derive" in message:
        return "unsupported-inheritance"
    if "constructor" in message.lower() or "构造" in message:
        return "constructor-or-config"
    if "module" in message.lower() or "source" in message.lower() or "源码" in message:
        return "module-or-source-contract"
    return "static-analysis-limitation"


def notebook_audit(root: Path, errors: list[str]) -> dict:
    ledger_path = root / "data/notebook-conversions.json"
    if not ledger_path.is_file():
        errors.append("Notebook conversion ledger is missing: data/notebook-conversions.json")
        return {"ok": False, "message": "conversion ledger missing"}
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("schema") != "archcanvas-preview-notebook-conversions/1":
        errors.append("Unknown Notebook conversion ledger schema")
    records, conversions = ledger.get("notebooks", []), ledger.get("conversions", {})
    known, failures, lines_checked = set(), [], 0
    python_hashes = set()
    for record in records:
        try:
            original = asset(root, record["notebook"])
            target = asset(root, record["canonical_python"])
            known.add(record["notebook"])
            data = target.read_bytes()
            if sha256(data) != record["python_sha256"]:
                raise ValueError("converted Python hash mismatch")
            text = data.decode("utf-8-sig")
            ast.parse(text, filename=record["canonical_python"])
            python_hashes.add(record["python_sha256"])
            conversion = conversions[record["conversion_id"]]
            if conversion.get("canonical_python") != record["canonical_python"] or conversion.get("python_sha256") != record["python_sha256"]:
                raise ValueError("conversion record does not match Notebook record")
            if record.get("notebook_retained", True):
                original_data = original.read_bytes()
                if sha256(original_data) != record["notebook_sha256"]:
                    raise ValueError("original Notebook hash mismatch")
                notebook = json.loads(original_data.decode("utf-8-sig"))
                derived_lines = text.splitlines()
                for row in conversion.get("line_map", []):
                    cell = notebook["cells"][row["cell_index"]]
                    if cell["cell_type"] != "code":
                        raise ValueError("line map points to a non-code cell")
                    raw_source = cell["source"]
                    source = "".join(raw_source) if isinstance(raw_source, list) else raw_source
                    raw = source.splitlines()[row["cell_line"] - 1]
                    if not isinstance(row["derived_line"], int):
                        raise ValueError("line map is incomplete")
                    actual = derived_lines[row["derived_line"] - 1]
                    if actual not in (raw, "# NOTEBOOK_MAGIC " + raw, "# NOTEBOOK_CELL " + raw):
                        raise ValueError("converted line differs from the recorded Notebook line")
                    if row["transform"] == "identity" and actual != raw:
                        raise ValueError("identity line was transformed")
                    if row["transform"] == "commented-magic" and not (MAGIC.match(raw) or raw.lstrip().startswith(("!", "?")) or raw.rstrip().endswith("?")):
                        raise ValueError("ordinary Python line was marked as Notebook magic")
                    lines_checked += 1
            elif original.exists():
                raise ValueError("Notebook is marked removed but remains present")
        except (OSError, ValueError, KeyError, IndexError, SyntaxError, TypeError) as error:
            failures.append({"notebook": record.get("notebook"), "error": str(error)})
    actual_notebooks = {path.relative_to(root).as_posix() for path in (root / "snapshots").rglob("*.ipynb")}
    if actual_notebooks - known:
        failures.append({"error": "Notebook files absent from ledger", "paths": sorted(actual_notebooks - known)})
    if ledger.get("notebook_count") != len(records):
        failures.append({"error": "Notebook count differs from ledger records"})
    if ledger.get("unique_notebook_count") != len({record.get("notebook_sha256") for record in records}):
        failures.append({"error": "Unique Notebook count differs from records"})
    converter = Path(__file__).with_name("convert-preview-notebooks.py")
    check = subprocess.run([sys.executable, str(converter), "--preview-root", str(root), "--check"],
                           capture_output=True, text=True, check=False)
    if check.returncode:
        failures.append({"error": "deterministic conversion tool check failed", "output": check.stdout + check.stderr})
    errors.extend("Notebook ledger: " + failure["error"] for failure in failures)
    return {"ok": not failures, "ledger_sha256": sha256(ledger_path.read_bytes()), "notebook_count": len(records),
            "unique_notebook_count": ledger.get("unique_notebook_count"), "python_asset_count": ledger.get("python_asset_count"),
            "python_hash_count": len(python_hashes), "mapped_lines_checked": lines_checked,
            "converter_check": {"exit_code": check.returncode, "output": check.stdout.strip()}, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-root", type=Path, default=PROJECT / "studio/public/preview")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/evidence/preview-sources-20261014/source-availability.json")
    parser.add_argument("--baseline", type=Path, default=Path("/tmp/preview-source-audit.json"))
    parser.add_argument("--architectures-output", type=Path, default=Path("/tmp/archcanvas-catalog-formal-architectures.json"),
                        help="Save successful formal AST projections for independent mapping checks")
    parser.add_argument("--expected-cases", type=int, default=230)
    parser.add_argument("--skip-authoring", action="store_true", help="Check files and entries without the formal static parser")
    parser.add_argument("--require-authoring", action="store_true", help="Fail if any current source case cannot enter authoring")
    args = parser.parse_args()
    root = args.preview_root.resolve()
    sys.path.insert(0, str(PROJECT / "src"))
    import archcanvas_preview
    from archcanvas_preview import analyze, analyze_for_authoring, capabilities
    if not Path(archcanvas_preview.__file__).resolve().is_relative_to(PROJECT / "src"):
        raise RuntimeError("Analyzer does not resolve to the formal Studio source tree")
    catalog_path, index_path = root / "data/catalog.json", root / "data/catalog-sources.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    descriptors = index["cases"]
    errors, records, cache, architectures, architecture_cache = [], [], {}, {}, {}
    if args.expected_cases and len(catalog["cases"]) != args.expected_cases:
        errors.append(f"Catalog case count differs: {len(catalog['cases'])} != {args.expected_cases}")
    if set(descriptors) != {case["id"] for case in catalog["cases"]}:
        errors.append("Source descriptor IDs do not match the catalog")
    limits = capabilities()["limits"]
    for case in catalog["cases"]:
        cid = case["id"]
        descriptor = descriptors.get(cid, {})
        record = {"id": cid, "title": case["title"], "historical": bool(case.get("historical")),
                  "source_available": bool(descriptor.get("available")), "entry": descriptor.get("entry"), "asset_checks": []}
        files, trees = {}, {}
        case_errors = []
        for item in descriptor.get("files", []):
            try:
                logical = item["path"]
                path = PurePosixPath(logical)
                if path.is_absolute() or ".." in path.parts or path.suffix != ".py" or "\\" in logical:
                    raise ValueError(f"Invalid logical source path: {logical}")
                if logical in files:
                    raise ValueError(f"Duplicate logical source path: {logical}")
                data = asset(root, item["asset"]).read_bytes()
                if sha256(data) != item["sha256"]:
                    raise ValueError(f"Source hash mismatch: {item['asset']}")
                original_check = None
                if item.get("originalAsset"):
                    original_data = asset(root, item["originalAsset"]).read_bytes()
                    if sha256(original_data) != item["sha256"]:
                        raise ValueError(f"Published source differs from retained original: {item['asset']}")
                    original_check = {"original_asset": item["originalAsset"], "original_sha256": sha256(original_data)}
                text = data.decode("utf-8")
                tree = ast.parse(text, filename=logical)
                files[logical], trees[logical] = text, tree
                record["asset_checks"].append({"path": logical, "asset": item["asset"], "sha256": item["sha256"],
                                               "bytes": len(data), "ast": "ok", **(original_check or {})})
            except (OSError, ValueError, SyntaxError, UnicodeDecodeError, KeyError) as error:
                case_errors.append(str(error))
        if descriptor.get("evidence"):
            try:
                evidence_path = asset(root, descriptor["evidence"])
                json.loads(evidence_path.read_text(encoding="utf-8"))
                record["evidence_sha256"] = sha256(evidence_path.read_bytes())
            except (OSError, ValueError) as error:
                case_errors.append("Source evidence: " + str(error))
        if descriptor.get("available"):
            try:
                if not files:
                    raise ValueError("Source is marked available without files")
                record["entry_check"] = entry_check(descriptor.get("entry"), trees)
                size = sum(len(text.encode()) for text in files.values())
                record["corpus_budget"] = {"files": len(files), "source_bytes": size,
                                           "ok": len(files) <= limits["files"] and size <= limits["sourceBytes"]}
                if not record["corpus_budget"]["ok"]:
                    raise ValueError("Source corpus exceeds preview source limits")
            except ValueError as error:
                case_errors.append(str(error))
        record["unprovided_relative_imports"] = import_audit(trees)
        if not case.get("historical") and descriptor.get("available") and not args.skip_authoring:
            if case_errors:
                record["authoring"] = {"status": "blocked-by-invalid-assets"}
            else:
                entry = record["entry_check"]["normalized"]
                key = sha256(json.dumps({"files": files, "entry": entry}, sort_keys=True).encode())
                if key not in cache:
                    result = {}
                    try:
                        bundle = analyze(files, entry)
                        result["preview_adapter"] = {"status": "ok", "entry": bundle["entry"], "nodes": len(bundle["ir"]["nodes"]),
                                                     "edges": len(bundle["ir"]["edges"]), "diagnostics": bundle["diagnostics"],
                                                     "model_executed": bundle["ir"]["modelExecuted"]}
                    except Exception as error:
                        result["preview_adapter"] = {"status": "unsupported", "category": error_category(error), "error": str(error)}
                    try:
                        architecture = analyze_for_authoring(files, entry)
                        architecture_cache[key] = architecture
                        result["authoring"] = {"status": "ok", "entry": architecture["entry"], "nodes": len(architecture["nodes"]),
                                               "edges": len(architecture["edges"]), "sources": len(architecture["sources"]),
                                               "diagnostics": architecture.get("diagnostics", [])}
                    except Exception as error:
                        result["authoring"] = {"status": "unsupported", "category": error_category(error), "error": str(error)}
                    cache[key] = result
                record.update(cache[key])
                if key in architecture_cache:
                    architectures[cid] = architecture_cache[key]
        record["errors"] = case_errors
        errors.extend(f"{cid}: {error}" for error in case_errors)
        records.append(record)
    notebooks = notebook_audit(root, errors)
    authoring_counts = Counter(record.get("authoring", {}).get("status") for record in records if record.get("authoring"))
    adapter_counts = Counter(record.get("preview_adapter", {}).get("status") for record in records if record.get("preview_adapter"))
    baseline = None
    if args.baseline.is_file():
        baseline_data = json.loads(args.baseline.read_text(encoding="utf-8"))
        old = baseline_data if isinstance(baseline_data, list) else baseline_data.get("cases", [])
        baseline = {"path": str(args.baseline), "sha256": sha256(args.baseline.read_bytes()),
                    "cases": len(old), "statuses": dict(Counter(record.get("status") for record in old)),
                    "previously_failed_now_pass": [record["id"] for record in records if record.get("authoring", {}).get("status") == "ok"
                                                   and any(item.get("id") == record["id"] and item.get("status") != "ok" for item in old)],
                    "previously_passed_now_fail": [record["id"] for record in records if record.get("authoring", {}).get("status") != "ok"
                                                   and any(item.get("id") == record["id"] and item.get("status") == "ok" for item in old)]}
    report = {"schema": "archcanvas-preview-source-validation/1", "generated_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Catalog assets, legal entry symbols, independent Notebook line mappings and static authoring availability; no model import or execution",
              "preview_root": str(root), "analyzer": str(Path(archcanvas_preview.__file__).resolve()), "model_executed": False,
              "catalog_sha256": sha256(catalog_path.read_bytes()), "source_index_sha256": sha256(index_path.read_bytes()),
              "ok": not errors, "limits": limits, "summary": {"cases": len(records), "current_cases": sum(not item["historical"] for item in records),
              "source_available": sum(item["source_available"] for item in records), "current_source_available": sum(item["source_available"] and not item["historical"] for item in records),
              "source_asset_references": sum(len(item["asset_checks"]) for item in records), "unique_source_assets": len({item["asset"] for record in records for item in record["asset_checks"]}),
              "authoring": dict(authoring_counts), "preview_adapter": dict(adapter_counts)}, "baseline": baseline,
              "notebooks": notebooks, "errors": errors, "cases": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.skip_authoring:
        args.architectures_output.parent.mkdir(parents=True, exist_ok=True)
        args.architectures_output.write_text(json.dumps(architectures, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "summary": report["summary"], "notebooks_ok": notebooks["ok"],
                      "errors": errors, "report": str(args.output)}, ensure_ascii=False))
    return 1 if errors or (args.require_authoring and authoring_counts.get("unsupported", 0)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
