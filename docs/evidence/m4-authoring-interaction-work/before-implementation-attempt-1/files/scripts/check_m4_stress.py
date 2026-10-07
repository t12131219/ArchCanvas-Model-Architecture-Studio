#!/usr/bin/env python3
"""Check the source-backed 300-layer scenario using copied analyzer and core."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from check_independence import clean_environment, verify
from check_stage2 import command, python_args


def check(project: Path) -> Path:
    independence_path, independence = verify(project.resolve(), build=False)
    release = Path(independence["standaloneCopy"])
    temporary = release.parent
    environment = clean_environment(temporary)
    artifacts = temporary / "m4-stress-artifacts"
    artifacts.mkdir()
    suite_code = (
        "import unittest; "
        f"suite=unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m4_stress.py'); "
        "result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun == 1 else 1)"
    )
    output = command(python_args(Path(sys.executable), release, suite_code), release, environment)
    (artifacts / "source-suite.txt").write_bytes(output)
    analysis_path = artifacts / "architecture.json"
    code = (
        "import json; from pathlib import Path; from archcanvas_python import analyze_project; "
        f"Path({str(analysis_path)!r}).write_text(json.dumps(analyze_project({str(release / 'fixtures' / 'stress_300')!r},'model:DenseStress300'),ensure_ascii=False,indent=2),encoding='utf-8')"
    )
    command(python_args(Path(sys.executable), release, code), release, environment)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node 24+ is required for the formal core check")
    probe = artifacts / "check-scene.mjs"
    probe.write_text(
        "import {readFile,writeFile} from 'node:fs/promises'; import assert from 'node:assert/strict';\n"
        f"import {{createDocument,applyVisualBatch,buildScene}} from {json.dumps((release / 'studio/src/core/index.ts').as_uri())};\n"
        f"const root={json.dumps(str(artifacts))};\n"
        "const architecture=JSON.parse(await readFile(root+'/architecture.json','utf8'));"
        "const d=createDocument(architecture); const canonicalRoot=architecture.nodes.find(n=>!n.parentId);"
        "assert.deepEqual(d.expandedIds,[canonicalRoot.id]);"
        "const containers=architecture.nodes.filter(n=>n.parentId&&n.children.length);assert.equal(containers.length,1);"
        "const target=containers[0];assert.equal(target.label,'network');assert.equal(target.children.length,300);"
        "const before=buildScene(d);assert.equal(before.nodes.length,4);assert.equal(before.edges.length,2);"
        "const expandedDocument=applyVisualBatch(d,[{type:'expand',id:target.id,expanded:true}]);"
        "const expanded=buildScene(expandedDocument);assert.equal(expanded.nodes.length,304);assert.equal(expanded.edges.length,302);"
        "const canonical=new Set(architecture.nodes.map(n=>n.id));assert.ok(expanded.nodes.every(n=>canonical.has(n.id)));"
        "assert.equal(expanded.nodes.filter(n=>['Linear','ReLU'].includes(n.kind)).length,300);"
        "const collapsed=buildScene(applyVisualBatch(expandedDocument,[{type:'expand',id:target.id,expanded:false}]));"
        "assert.deepEqual(collapsed.nodes.map(n=>n.id),before.nodes.map(n=>n.id));"
        "const stats=scene=>({nodeCount:scene.nodes.length,edgeCount:scene.edges.length,canonicalLayerCount:scene.nodes.filter(n=>['Linear','ReLU'].includes(n.kind)).length});"
        "await writeFile(root+'/scene-receipt.json',JSON.stringify({schemaVersion:1,passed:true,entry:architecture.entry,sourceDigest:architecture.sourceDigest,irDigest:architecture.irDigest,target:{canonicalNodeId:target.id,label:target.label,depth:1},before:stats(before),expanded:stats(expanded),after:stats(collapsed),source:'formal analyzer; source explicitly declares 300 layers; no injected architecture',scope:'core scene counts only; no browser performance claim'},null,2));\n",
        encoding="utf-8",
    )
    command([node, str(probe)], release, environment)
    scene = json.loads((artifacts / "scene-receipt.json").read_text(encoding="utf-8"))
    report = {
        "schemaVersion": 1, "passed": True,
        "scope": "source-backed static 300-layer Sequential and canonical core scene scenario",
        "sourceCopy": str(release), "independenceReport": str(independence_path),
        "sourceSuite": str(artifacts / "source-suite.txt"),
        "architecture": str(analysis_path), "sceneReceipt": str(artifacts / "scene-receipt.json"),
        "scenario": scene,
        "artifactDigests": {"architecture": hashlib.sha256(analysis_path.read_bytes()).hexdigest()},
        "limitations": ["No fixture import/forward execution or model correctness claim.", "This count receipt is not a browser latency/FPS measurement or publication quality certification."],
    }
    report_path = temporary / "m4-stress-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    options = parser.parse_args()
    try:
        path = check(options.project)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, "report": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
