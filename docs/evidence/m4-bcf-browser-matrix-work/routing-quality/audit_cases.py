"""Audit actual matrix SVG + Canvas using an independent XML parser and oracle.

Read-only inputs. Refuses output overwrite. New output must remain inside this
audit directory. Does not rebuild product scenes, import models or use browser.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

# Importing the existing frozen parser must not write __pycache__ beside it.
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INDEPENDENT = ROOT / "docs/evidence/m4-routing-refinement/independent"


def binding(path):
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path):
    return json.loads(path.read_text())


def parse_module():
    path = INDEPENDENT / "parse_browser_svg.py"
    spec = importlib.util.spec_from_file_location("archcanvas_independent_public_svg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def analyze(scene_path, node):
    process = subprocess.run([node, "--experimental-strip-types", str(HERE / "analyze_scene.ts"), str(scene_path)],
                             text=True, capture_output=True)
    return process, json.loads(process.stdout) if process.returncode == 0 else None


def route_projection(scene):
    return [{key: edge[key] for key in ("id", "sourceId", "targetId", "source", "target", "canonicalEdgeIds", "tensorId", "role", "path")}
            for edge in scene["edges"]]


def check_canonical_projection(scene, document):
    """Bind pair filters to saved canonical facts, not SVG's self-description."""
    architecture = document["architecture"]
    canonical = {node["id"]: node for node in architecture["nodes"]}
    relations = {edge["id"]: edge for edge in architecture["edges"]}
    visible = {node["id"] for node in scene["nodes"]}
    seen_edges = set()

    def representative(identity):
        seen = set()
        while identity not in visible:
            if identity in seen or identity not in canonical:
                raise ValueError("Missing/cyclic canonical endpoint representative")
            seen.add(identity)
            identity = canonical[identity].get("parentId")
        return identity

    for route in scene["edges"]:
        ids = route["canonicalEdgeIds"]
        if not ids or len(set(ids)) != len(ids) or seen_edges.intersection(ids):
            raise ValueError("Missing/duplicated canonical route ownership")
        seen_edges.update(ids)
        matching_representative_binding = False
        for identity in ids:
            edge = relations[identity]
            if edge["tensorId"] != route["tensorId"] or edge["role"] != route["role"]:
                raise ValueError("Rendered tensor/role disagrees with canonical relation")
            for endpoint, direction in (("source", "out"), ("target", "in")):
                binding = edge[endpoint]
                if representative(binding["nodeId"]) != route[endpoint + "Id"]:
                    raise ValueError("Projected endpoint owner disagrees with canonical relation")
                ports = canonical[binding["nodeId"]]["ports"]
                if not any(port["id"] == binding["portId"] and port["direction"] == direction for port in ports):
                    raise ValueError("Missing canonical endpoint port/direction")
            matching_representative_binding |= edge["source"] == route["source"] and edge["target"] == route["target"]
        if not matching_representative_binding:
            raise ValueError("Rendered canonical endpoint binding is not a grouped relation")
    return {"passed": True, "canonicalEdgesRepresented": len(seen_edges),
            "renderedRoutes": len(scene["edges"]), "scope": "Exact saved canonical tensor/role/endpoint projection per rendered route"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--captures", type=Path, help="Actual matrix captures JSON, paths relative to its parent")
    inputs.add_argument("--case-dir", type=Path, help="One actual case: canvas.json, browser-scene.svg, figure.svg")
    parser.add_argument("--out", type=Path, required=True, help="Fresh directory inside routing-quality")
    parser.add_argument("--node", default="node", help="Already available Node supporting type stripping; no installs")
    args = parser.parse_args()
    destination = args.out.resolve()
    if HERE not in destination.parents:
        parser.error("Output must be a new child directory of routing-quality")
    if destination.exists():
        parser.error("Output already exists; preserve previous report")
    if args.captures:
        source = args.captures.resolve()
        listing = read_json(source)
        if listing.get("protocol") != "archcanvas-browser-visual-matrix/1" or not isinstance(listing.get("captures"), list):
            parser.error("Unsupported captures list")
        records = [{"caseId": row["caseId"], "state": row["state"], "variantId": row["variantId"],
                    "canvas": source.parent / row["canvas"], "browser": source.parent / row["browserScene"],
                    "publication": source.parent / row["svg"]} for row in listing["captures"]]
    else:
        directory = args.case_dir.resolve()
        source = None
        records = [{"caseId": directory.name, "state": "not-declared-by-captures-list", "variantId": None,
                    "canvas": directory / "canvas.json", "browser": directory / "browser-scene.svg",
                    "publication": directory / "figure.svg"}]
    identities = [row["caseId"] for row in records]
    if len(set(identities)) != len(identities) or any(not value or Path(value).name != value or value in (".", "..") for value in identities):
        parser.error("Duplicate or unsafe case identity")
    # Bind inputs before reading the parser; all current input mutations are
    # checked again at the end. Output scenes are independently XML-derived.
    input_bindings = [binding(row[key]) for row in records for key in ("canvas", "browser", "publication")]
    sources = [HERE / "audit_cases.py", HERE / "analyze_scene.ts", INDEPENDENT / "parse_browser_svg.py",
               INDEPENDENT / "oracle.ts", INDEPENDENT / "controls.ts", INDEPENDENT / "fixtures.ts"]
    source_bindings = [binding(path) for path in sources]
    capture_binding = binding(source) if source else None
    xml = parse_module()
    destination.mkdir(parents=True)
    controls = subprocess.run([args.node, "--experimental-strip-types", str(HERE / "analyze_scene.ts"), "--controls"],
                              text=True, capture_output=True)
    save_json(destination / "oracle-controls.json", {"exitCode": controls.returncode,
              "stdout": controls.stdout, "stderr": controls.stderr})
    results = []
    for row in records:
        directory = destination / row["caseId"]
        directory.mkdir()
        result = {"caseId": row["caseId"], "variantId": row["variantId"], "state": row["state"], "errors": []}
        scenes = {}
        for kind in ("browser", "publication"):
            try:
                scene, facts = xml.parse(row[kind], row["canvas"], standalone=True)
                # Existing parser covers full document SVG grammar, not detail
                # boundary proxies. Fail rather than silently extending scope.
                if facts["metadata"].get("exportScope", {"kind": "document"}).get("kind") != "document":
                    raise ValueError("Only full-document SVG is supported by this adapter")
                canonical_check = check_canonical_projection(scene, facts["canonicalDocument"])
                scene_path = directory / f"{kind}.scene.json"
                save_json(scene_path, scene)
                process, metrics = analyze(scene_path, args.node)
                save_json(directory / f"{kind}.oracle-execution.json", {"exitCode": process.returncode,
                          "stdout": process.stdout, "stderr": process.stderr})
                if metrics is None:
                    raise ValueError(f"Independent oracle exited {process.returncode}: {process.stderr}")
                save_json(directory / f"{kind}.metrics.json", metrics)
                scenes[kind] = scene
                result[kind] = {"nodes": metrics["visibleNodes"], "routes": metrics["renderedRoutes"],
                    "canonicalProjectionCheck": canonical_check,
                    "distinctTensor": metrics["distinctTensor"], "disjointOwners": metrics["disjointOwners"],
                    "sameTensor": metrics["sameTensor"], "totalBends": metrics["totalBends"],
                    "totalReversals": metrics["totalReversals"], "totalLength": metrics["totalLength"],
                    "bodyHeaderIntrusions": len(metrics["bodyHeaderIntrusions"]),
                    "endpointAndViewBoxCheck": metrics["endpointAndViewBoxCheck"],
                    "inputs": [binding(row[kind]), binding(row["canvas"])],
                    "report": str((directory / f"{kind}.metrics.json").relative_to(destination))}
            except Exception as error:
                result["errors"].append({"artifact": kind, "error": f"{type(error).__name__}: {error}"})
        if len(scenes) == 2:
            result["browserPublicationRouteProjectionEqual"] = route_projection(scenes["browser"]) == route_projection(scenes["publication"])
            # Body geometry excludes interactivity-only controls/text markup.
            result["browserPublicationBodyGeometryEqual"] = [
                {key: node[key] for key in ("id", "x", "y", "width", "height", "headerHeight")}
                for node in scenes["browser"]["nodes"]] == [
                {key: node[key] for key in ("id", "x", "y", "width", "height", "headerHeight")}
                for node in scenes["publication"]["nodes"]]
        results.append(result)
    bindings = [*input_bindings, *source_bindings, *([capture_binding] if capture_binding else [])]
    changed = [item["path"] for item in bindings if binding(Path(item["path"])) != item]
    report = {"schema": "archcanvas-matrix-routing-geometry-audit/1", "createdAtUTC": datetime.now(timezone.utc).isoformat(),
              "scope": "Independent standard-XML metrics of actual supplied full-document browser/publication SVG bound to saved Canvas; no product scene rebuilding.",
              "inputBindings": input_bindings, "sourceBindings": source_bindings, "capturesListBinding": capture_binding,
              "inputsStableDuringAudit": not changed, "changedInputs": changed, "oracleControlsExitCode": controls.returncode,
              "casesRequested": len(records), "casesParsedBothArtifacts": sum("browser" in row and "publication" in row for row in results),
              "cases": results, "aestheticCertified": False, "humanCertified": False,
              "publicationCertified": False, "presentedPerformanceCertified": False,
              "limitations": ["Crossings/bends/detours are geometric observations, not proved unnecessary or ugly.",
                 "No raster/font/arrowhead/stroke-width clearance or human review.",
                 "No current browser activity added; these are supplied artifact analyses.",
                 "Direct --case-dir does not bind capture time/build/human/environment; existing matrix receipts must be checked separately.",
                 "No arbitrary SVG/detail-export grammar; unsupported metadata/path syntax fails explicitly."]}
    save_json(destination / "audit.json", report)
    artifacts = [binding(path) for path in sorted(destination.rglob("*")) if path.is_file()]
    save_json(destination / "manifest.json", {"schema": "archcanvas-routing-audit-artifacts/1", "artifacts": artifacts})
    print(json.dumps({"casesRequested": len(records), "casesParsedBothArtifacts": report["casesParsedBothArtifacts"],
                      "oracleControlsExitCode": controls.returncode, "inputsStableDuringAudit": not changed,
                      "errors": sum(len(row["errors"]) for row in results), "output": str(destination)}, ensure_ascii=False))
    if changed or controls.returncode or any(row["errors"] for row in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
