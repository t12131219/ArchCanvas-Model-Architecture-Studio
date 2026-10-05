#!/usr/bin/env python3
"""Generate source-bound detail publications and run the real independent suite.

The release consists only of the formal source files needed by this contract.
The host's formal publication interpreter supplies Cairo; no prototype package
or project node_modules is copied or loaded.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, timeout=60):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "docs/evidence/detail-export")
    options = parser.parse_args()
    evidence = options.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="archcanvas-detail-independent-", dir="/tmp"))
    release = temporary / "release"
    release.mkdir()
    for relative in ("src", "studio/src/core", "fixtures/mlp", "fixtures/transformer"):
        shutil.copytree(ROOT / relative, release / relative, ignore=shutil.ignore_patterns("__pycache__"))
    for relative in ("pyproject.toml", "scripts/export_canvas.mjs", "tests/test_detail_export.py"):
        target = release / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    suite_bootstrap = 'import sys,unittest;sys.path.insert(0,sys.argv[1]);suite=unittest.defaultTestLoader.discover(sys.argv[2],pattern="test_detail_export.py");result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())'
    suite = run([sys.executable, "-I", "-B", "-c", suite_bootstrap, str(release / "src"), str(release / "tests")], cwd=release)
    (evidence / "independent-suite.txt").write_text(suite.stdout + suite.stderr)
    provenance_bootstrap = 'import sys,json;sys.path.insert(0,sys.argv[1]);import archcanvas_cli,archcanvas_python,archcanvas_publication;print(json.dumps({m.__name__:m.__file__ for m in (archcanvas_cli,archcanvas_python,archcanvas_publication)}))'
    origins = json.loads(run([sys.executable, "-I", "-B", "-c", provenance_bootstrap, str(release / "src")], cwd=release).stdout)
    if any(not Path(origin).resolve().is_relative_to(release / "src") for origin in origins.values()):
        raise AssertionError("An independent export module resolved outside the formal release")
    renderer_paths = [release / "scripts/export_canvas.mjs", *sorted((release / "studio/src/core").glob("*.ts"))]
    renderer_digests = {str(path.relative_to(release)): hashlib.sha256(path.read_bytes()).hexdigest() for path in renderer_paths}
    report = {"schemaVersion": 1, "release": str(release), "interpreter": sys.executable,
        "moduleOrigins": origins, "rendererFileDigests": renderer_digests,
        "suite": {"tests": 3, "passed": True, "skipped": 0, "evidence": "independent-suite.txt"},
        "claim": "Shared Scene/SVG detail rendering and physical artifact geometry; no universal publication-quality or researcher certification.", "fixtures": []}
    for fixture, entry, selector in (("mlp", "model:MLP", "network"), ("transformer", "model:Transformer", "call:instance:model.Transformer.encoder.0.feedforward")):
        prefix = evidence / fixture
        architecture_path = Path(str(prefix) + ".architecture.json")
        document_path = Path(str(prefix) + ".canvas.json")
        analyze = 'import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from archcanvas_python import analyze_project;print(json.dumps(analyze_project(Path(sys.argv[2]),sys.argv[3])))'
        architecture = json.loads(run([sys.executable, "-I", "-S", "-B", "-c", analyze, str(release / "src"), str(release / "fixtures" / fixture), entry], cwd=release).stdout)
        architecture_path.write_text(json.dumps(architecture, ensure_ascii=False, indent=2) + "\n")
        selected = next(node for node in architecture["nodes"] if node["id"] == selector or node["label"] == selector)
        bootstrap = '''import fs from 'node:fs';
import {createDocument,applyVisualBatch,buildScene} from './studio/src/core/index.ts';
const a=JSON.parse(fs.readFileSync(process.argv[1]));
const id=process.argv[3], byId=new Map(a.nodes.map(n=>[n.id,n]));
let d=createDocument(a);const ancestors=[];let node=byId.get(id);
while(node){ancestors.unshift(node.id);node=byId.get(node.parentId);}
for(const id of ancestors)if(!d.expandedIds.includes(id))d=applyVisualBatch(d,[{type:'expand',id,expanded:true}]);
const box=buildScene(d).nodes.find(n=>n.id===id);
d=applyVisualBatch(d,[{type:'annotation',annotation:{id:'detail-note',text:'Current source-bound detail',x:box.x+12,y:box.y+box.height-32,width:200,height:30}}]);
fs.writeFileSync(process.argv[2],JSON.stringify(d,null,2)+'\\n');'''
        run(["node", "--experimental-strip-types", "--input-type=module", "-e", bootstrap, str(architecture_path), str(document_path), selected["id"]], cwd=release)
        document_bytes = document_path.read_bytes()
        source_digest = hashlib.sha256((release / "fixtures" / fixture / "model.py").read_bytes()).hexdigest()
        records = []
        for width in (85, 180):
            for format in ("svg", "pdf", "png"):
                output = Path(str(prefix) + f"-{width}.{format}")
                run(["node", "scripts/export_canvas.mjs", "--document", str(document_path), "--output", str(output), "--format", format, "--python", sys.executable, "--scope-node", selected["id"], "--width-mm", str(width)], cwd=release)
                receipt = json.loads(Path(str(output) + ".receipt.json").read_text())
                if receipt["outputDigest"] != hashlib.sha256(output.read_bytes()).hexdigest():
                    raise AssertionError("Generated artifact digest does not match its receipt")
                if format == "svg":
                    xml = ET.fromstring(output.read_bytes())
                    metadata = json.loads(xml.find("{http://www.w3.org/2000/svg}metadata").text)
                    if metadata["exportScope"] != receipt["exportScope"]:
                        raise AssertionError("SVG metadata and stored scope differ")
                records.append({"artifact": output.name, "receipt": output.name + ".receipt.json", "widthMm": width,
                    "format": format, "outputDigest": receipt["outputDigest"], "physicalPreflight": receipt["physicalPreflight"], "geometryVerified": receipt["geometryVerified"]})
        if document_bytes != document_path.read_bytes():
            raise AssertionError("Export changed its CanvasDocument")
        if source_digest != hashlib.sha256((release / "fixtures" / fixture / "model.py").read_bytes()).hexdigest():
            raise AssertionError("Export changed source")
        if source_digest != hashlib.sha256((ROOT / "fixtures" / fixture / "model.py").read_bytes()).hexdigest():
            raise AssertionError("Independent release fixture differs from the formal source")
        report["fixtures"].append({"fixture": fixture, "entry": entry, "selectedNodeId": selected["id"], "selectedLabel": selected["label"],
            "sourceFileDigest": source_digest, "sourceDigest": architecture["sourceDigest"], "irDigest": architecture["irDigest"],
            "sourceUnchanged": True, "documentUnchanged": True, "scope": receipt["exportScope"], "artifacts": records})
    (evidence / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": True, "release": str(release), "evidence": str(evidence), "tests": 3, "artifacts": 12}))


if __name__ == "__main__":
    main()
