#!/usr/bin/env python3
"""Publish static Notebook code as source-addressable Python assets.

Only JSON, text, tokens and the Python AST are read. Model code is never imported,
compiled for execution, or executed. Existing equivalent Python source is copied
byte-for-byte so source-evidence line numbers remain stable.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import io
import json
import keyword
import re
import tokenize
from collections import defaultdict
from pathlib import Path

SCHEMA = "archcanvas-preview-notebook-conversions/1"
MAGIC = re.compile(r"^\s*(?:%{1,2}[A-Za-z_]\w*\b|![A-Za-z_])")
PYTHON_CELL_MAGICS = {"time", "timeit", "capture", "prun", "python", "python3"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identifier(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not value or value[0].isdigit():
        value = "_" + value
    # Keywords are not valid import path segments either.
    return value + "_" if keyword.iskeyword(value) else value


def logical_path(notebook: Path, snapshots: Path) -> Path:
    parts = notebook.relative_to(snapshots).parts
    source_positions = [i for i, part in enumerate(parts) if part == "sources"]
    if source_positions:
        parts = parts[source_positions[-1] + 1:]
    path = Path(*parts)
    return Path(*(identifier(part) for part in path.parts[:-1]), identifier(path.stem) + ".py")


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list) and all(isinstance(line, str) for line in source):
        return "".join(source)
    if isinstance(source, str):
        return source
    raise ValueError("Notebook cell source must be text or a list of text lines")


def extract(notebook: dict, safe: bool = False) -> tuple[str, list[dict], list[dict]]:
    """Keep the prototype extraction format; repair non-Python cells if needed."""
    lines: list[str] = []
    mapping: list[dict] = []
    diagnostics: list[dict] = []
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise ValueError("Notebook must contain a cells list")
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise ValueError("Notebook cells must be objects")
        if cell.get("cell_type") != "code":
            continue
        source_lines = cell_source(cell).splitlines()
        first = next((line.strip() for line in source_lines if line.strip()), "")
        cell_magic = re.match(r"^%%([A-Za-z_]\w*)", first)
        whole_comment = bool(safe and cell_magic and cell_magic[1] not in PYTHON_CELL_MAGICS)
        prepared = []
        transforms = []
        for line in source_lines:
            comment = whole_comment or bool(MAGIC.match(line))
            # '?' introspection and shell commands are IPython, never Python.
            if safe and (line.lstrip().startswith(("!", "?")) or line.rstrip().endswith("?")):
                comment = True
            prepared.append(("# NOTEBOOK_MAGIC " + line if comment else line) + "\n")
            transforms.append("commented-magic" if comment else "identity")
        if safe and not whole_comment:
            try:
                ast.parse("".join(prepared))
            except SyntaxError as error:
                whole_comment = True
                diagnostics.append({"cell_index": index, "reason": "non-python-cell", "detail": error.msg})
        if whole_comment:
            prepared = ["# NOTEBOOK_CELL " + line + "\n" for line in source_lines]
            transforms = ["commented-non-python-cell"] * len(source_lines)
            if cell_magic:
                diagnostics.append({"cell_index": index, "reason": "non-python-cell-magic", "magic": cell_magic[1]})
        lines.append(f"# %% Notebook cell {index}\n")
        for cell_line, (line, transform) in enumerate(zip(prepared, transforms), 1):
            mapping.append({"derived_line": len(lines) + 1, "cell_index": index,
                            "cell_line": cell_line, "transform": transform})
            lines.append(line)
        lines.append("\n")
    return "".join(lines), mapping, diagnostics


def ast_signature(source: str) -> str | None:
    try:
        return ast.dump(ast.parse(source), include_attributes=False)
    except SyntaxError:
        return None


def remap_lines(expected: str, actual: str, mapping: list[dict]) -> list[dict]:
    """Map equivalent existing source without changing its byte or line identity."""
    corresponding: dict[int, set[int]] = defaultdict(set)
    for block in difflib.SequenceMatcher(None, expected.splitlines(), actual.splitlines(), autojunk=False).get_matching_blocks():
        for offset in range(block.size):
            corresponding[block.a + offset + 1].add(block.b + offset + 1)
    ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.COMMENT, tokenize.NL,
               tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}
    def tokens(text: str):
        return [item for item in tokenize.generate_tokens(io.StringIO(text).readline) if item.type not in ignored]
    try:
        old_tokens, new_tokens = tokens(expected), tokens(actual)
        if [(item.type, item.string) for item in old_tokens] == [(item.type, item.string) for item in new_tokens]:
            for old, new in zip(old_tokens, new_tokens):
                corresponding[old.start[0]].add(new.start[0])
    except (tokenize.TokenError, IndentationError):
        pass
    result = []
    for item in mapping:
        matches = sorted(corresponding.get(item["derived_line"], set()))
        for derived_line in matches or [None]:
            result.append({**item, "derived_line": derived_line})
    return result


def convert(notebook_bytes: bytes, existing_bytes: bytes | None) -> tuple[bytes, str, list[dict], list[dict]]:
    notebook = json.loads(notebook_bytes.decode("utf-8-sig"))
    expected, mapping, diagnostics = extract(notebook)
    signature = ast_signature(expected)
    if signature is None:
        expected, mapping, diagnostics = extract(notebook, safe=True)
        signature = ast_signature(expected)
        if signature is None:
            raise ValueError("Notebook cannot be represented as valid static Python")
    if existing_bytes is not None:
        try:
            existing = existing_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            existing = None
        if existing is not None and ast_signature(existing) == signature:
            strategy = "reuse-exact-python" if existing == expected else "reuse-equivalent-python"
            if existing != expected:
                mapping = remap_lines(expected, existing, mapping)
            return existing_bytes, strategy, mapping, diagnostics
    strategy = "extract-static-python" if not diagnostics else "extract-static-python-with-commented-cells"
    return expected.encode("utf-8"), strategy, mapping, diagnostics


def build_plan(preview: Path, remove_notebooks: bool = False) -> tuple[dict, dict[str, bytes]]:
    snapshots = preview / "snapshots"
    records = []
    outputs: dict[str, bytes] = {}
    conversions = {}
    candidates = []
    for notebook in sorted(snapshots.rglob("*.ipynb")):
        original = notebook.with_suffix(".py")
        notebook_bytes = notebook.read_bytes()
        python_bytes, strategy, mapping, diagnostics = convert(
            notebook_bytes, original.read_bytes() if original.is_file() else None)
        candidates.append((notebook, original, notebook_bytes, python_bytes, strategy, mapping, diagnostics,
                           (Path("sources/notebooks") / logical_path(notebook, snapshots)).as_posix()))
    path_hashes: dict[str, set[str]] = defaultdict(set)
    for item in candidates:
        path_hashes[item[-1]].add(sha256(item[3]))
    for notebook, original, notebook_bytes, python_bytes, strategy, mapping, diagnostics, canonical in candidates:
        python_hash = sha256(python_bytes)
        if len(path_hashes[canonical]) > 1:
            base = Path(canonical)
            canonical = (base.parent / (base.stem + "_" + python_hash[:12] + ".py")).as_posix()
        if canonical in outputs and outputs[canonical] != python_bytes:
            raise ValueError(f"Canonical source collision: {canonical}")
        outputs[canonical] = python_bytes
        notebook_hash = sha256(notebook_bytes)
        conversion_id = sha256((notebook_hash + ":" + python_hash + ":" + canonical).encode())[:24]
        conversions[conversion_id] = {"canonical_python": canonical, "python_sha256": python_hash,
                                      "line_map": mapping, "line_mapping_complete": all(
                                          item["derived_line"] is not None for item in mapping),
                                      "diagnostics": diagnostics}
        records.append({"notebook": notebook.relative_to(preview).as_posix(),
                        "notebook_sha256": notebook_hash,
                        "original_python": original.relative_to(preview).as_posix(),
                        "original_python_sha256": sha256(original.read_bytes()) if original.is_file() else None,
                        "canonical_python": canonical, "python_sha256": python_hash,
                        "strategy": strategy, "conversion_id": conversion_id,
                        "notebook_retained": not remove_notebooks})
    report = {"schema": SCHEMA, "notebook_count": len(records),
              "unique_notebook_count": len({record["notebook_sha256"] for record in records}),
              "python_asset_count": len(outputs), "notebooks": records,
              "conversions": dict(sorted(conversions.items()))}
    return report, outputs


def ledger_bytes(report: dict) -> bytes:
    return (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def check_removed_records(preview: Path, report: dict) -> list[str]:
    """Verify a completed optional removal using the retained conversion ledger."""
    errors = []
    if report.get("schema") != SCHEMA:
        return ["Unknown Notebook conversion ledger schema"]
    known = set()
    for record in report.get("notebooks", []):
        notebook = preview / record["notebook"]
        known.add(record["notebook"])
        if record.get("notebook_retained", True):
            if not notebook.is_file() or sha256(notebook.read_bytes()) != record["notebook_sha256"]:
                errors.append(f"Notebook missing or changed: {record['notebook']}")
        elif notebook.exists():
            errors.append(f"Notebook removal incomplete: {record['notebook']}")
        target = preview / record["canonical_python"]
        if not target.is_file() or sha256(target.read_bytes()) != record["python_sha256"]:
            errors.append(f"Python asset missing or changed: {record['canonical_python']}")
        elif ast_signature(target.read_text(encoding="utf-8-sig")) is None:
            errors.append(f"Python asset is not valid Python: {record['canonical_python']}")
    for notebook in (preview / "snapshots").rglob("*.ipynb"):
        if notebook.relative_to(preview).as_posix() not in known:
            errors.append(f"Notebook absent from ledger: {notebook.relative_to(preview)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-root", type=Path, default=Path(__file__).resolve().parents[1] / "public/preview")
    parser.add_argument("--check", action="store_true", help="Check assets and deterministic ledger without writing")
    parser.add_argument("--remove-notebooks", action="store_true", help="Remove Notebook originals after publishing Python and the conversion ledger")
    args = parser.parse_args(argv)
    preview = args.preview_root.resolve()
    if not (preview / "snapshots").is_dir():
        parser.error("preview root must contain a snapshots directory")
    ledger = preview / "data/notebook-conversions.json"
    if ledger.is_file():
        existing_report = json.loads(ledger.read_bytes())
        if any(not record.get("notebook_retained", True) for record in existing_report.get("notebooks", [])):
            errors = check_removed_records(preview, existing_report)
            if not args.check:
                if errors:
                    parser.error("Removed Notebook provenance must pass --check before republishing")
                # Optional removal is already complete. Preserve its source ledger.
            print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
            return 1 if errors else 0
    report, outputs = build_plan(preview, args.remove_notebooks)
    errors = []
    if args.check:
        for relative, data in outputs.items():
            target = preview / relative
            if not target.is_file() or target.read_bytes() != data:
                errors.append(f"Python asset missing or changed: {relative}")
        if not ledger.is_file() or ledger.read_bytes() != ledger_bytes(report):
            errors.append("Notebook conversion ledger missing or changed: data/notebook-conversions.json")
    else:
        for relative, data in outputs.items():
            target = preview / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(ledger_bytes(report))
        if args.remove_notebooks:
            for record in report["notebooks"]:
                (preview / record["notebook"]).unlink()
    print(json.dumps({"ok": not errors, "notebook_count": report["notebook_count"],
                      "unique_notebook_count": report["unique_notebook_count"],
                      "python_asset_count": report["python_asset_count"], "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
