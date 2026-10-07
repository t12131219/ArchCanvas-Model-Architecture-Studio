#!/usr/bin/env python3
"""Independent M2 check: tmp source copy, black-box intents and scene derivatives.

This checks real parameter commits only inside handwritten /tmp test projects.
PDF/PNG use an explicit formal Python environment; its converter paths are kept
in the report rather than hidden as bundled stdlib functionality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

from check_independence import clean_environment, verify


def command(args: list[str], cwd: Path, environment: dict[str, str], input_data: bytes | None = None) -> bytes:
    result = subprocess.run(args, cwd=cwd, env=environment, input=input_data, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {args!r}\n"
            f"{result.stdout.decode(errors='replace')}\n{result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def python_args(interpreter: Path, release: Path, code: str, *, allow_site: bool = False) -> list[str]:
    # Keep the supplied .venv executable spelling: resolving its symlink would
    # silently switch to base Python and lose the project's publication extra.
    return [str(interpreter.absolute()), "-I", *([] if allow_site else ["-S"]), "-B", "-c",
            f"import sys; sys.path.insert(0, {str(release / 'src')!r}); " + code]


def check(project: Path, interpreter: Path, build: bool) -> Path:
    independence_path, independence = verify(project, build)
    release = Path(independence["standaloneCopy"])
    temporary = release.parent
    environment = clean_environment(temporary)
    environment["NO_PROXY"] = environment["no_proxy"] = "127.0.0.1,localhost"
    report: dict[str, object] = {
        "schemaVersion": 1, "scope": "M2 explicit dropout literals and same-scene SVG/PDF/PNG",
        "independenceReport": str(independence_path), "sourceCopy": str(release),
        "publicationPython": str(interpreter.absolute()), "checks": [],
    }
    checks: list[dict[str, object]] = report["checks"]  # type: ignore[assignment]
    suite_code = (
        "import unittest; "
        f"suite=unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_stage2_invariants.py'); "
        "result=unittest.TextTestRunner(verbosity=2).run(suite); "
        "sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun > 0 else 1)"
    )
    command(python_args(interpreter, release, suite_code), release, environment)
    checks.append({"name": "independent-parameter-intent-and-rejection-suite", "passed": True,
                   "source": str(release / "tests" / "test_stage2_invariants.py"), "scope": "all originals under /tmp"})

    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node 24+ is required for the formal Scene renderer")
    artifacts = temporary / "stage2-artifacts"
    artifacts.mkdir()
    # Generate a document from actual copied source, then add independent visual
    # edits through the copied formal core. No standalone competing renderer.
    architecture = artifacts / "mlp.json"
    analysis_code = (
        "import json; from pathlib import Path; from archcanvas_python import analyze_project; "
        f"Path({str(architecture)!r}).write_text(json.dumps(analyze_project({str(release / 'fixtures' / 'mlp')!r}, 'model:MLP')), encoding='utf-8')"
    )
    command(python_args(interpreter, release, analysis_code), release, environment)
    creator = artifacts / "make-documents.mjs"
    creator.write_text(
        "import {readFile,writeFile} from 'node:fs/promises';\n"
        f"import {{createDocument,applyVisualBatch,buildScene,renderSvg,reconcileDocument,validateDocument,createHistory}} from {json.dumps((release / 'studio/src/core/index.ts').as_uri())};\n"
        f"const root={json.dumps(str(artifacts))};\n"
        "const a=JSON.parse(await readFile(root+'/mlp.json','utf8'));\n"
        "let d=createDocument(a); const selected=a.nodes.find(n=>n.kind==='Dropout');\n"
        "d=applyVisualBatch(d,[{type:'expand',id:selected.parentId,expanded:true},"
        "{type:'alias',id:selected.id,label:'Reviewed dropout / 已审核丢弃层'},"
        "{type:'nodeStyle',id:selected.id,style:{fill:'#dfeaf2'}},"
        "{type:'legend',items:[{id:'oracle-legend',label:'Independent legend',color:'#dfeaf2',glyph:'operator'}]},"
        "{type:'pin',ids:[selected.id],pinned:true}]);\n"
        "const bounds=buildScene(d).bounds; d=applyVisualBatch(d,["
        "{type:'annotation',annotation:{id:'oracle-note',text:'Current scene only / 当前画布',"
        "x:bounds.x,y:bounds.y+bounds.height+32,width:340}}]);\n"
        "for(const widthMm of [85,180]) { const current=applyVisualBatch(d,[{type:'page',page:{widthMm}}]);"
        "await writeFile(root+'/figure-'+widthMm+'.json',JSON.stringify(current));"
        "await writeFile(root+'/figure-'+widthMm+'.scene.svg',renderSvg(buildScene(current))); }\n",
        encoding="utf-8",
    )
    command([node, str(creator)], release, environment)
    for width in (85, 180):
        outputs: dict[str, dict[str, object]] = {}
        scene_svg = (artifacts / f"figure-{width}.scene.svg").read_bytes()
        scene_digest = hashlib.sha256(scene_svg).hexdigest()
        current_document = json.loads((artifacts / f"figure-{width}.json").read_text(encoding="utf-8"))
        for kind in ("svg", "pdf", "png"):
            output = artifacts / f"figure-{width}.{kind}"
            command([
                node, str(release / "scripts" / "export_canvas.mjs"), "--document", str(artifacts / f"figure-{width}.json"),
                "--output", str(output), "--format", kind, "--dpi", "300", "--python", str(interpreter.absolute()),
            ], release, environment)
            receipt_path = Path(str(output) + ".receipt.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"Export did not create {output}")
            if (
                receipt.get("sceneSvgDigest") != scene_digest or receipt.get("inputSvgDigest") != scene_digest
                or receipt.get("documentId") != current_document["id"]
                or receipt.get("revision") != current_document["revision"]
                or receipt.get("sourceDigest") != current_document["architecture"]["sourceDigest"]
                or receipt.get("irDigest") != current_document["architecture"]["irDigest"]
                or receipt.get("outputDigest") != hashlib.sha256(output.read_bytes()).hexdigest()
                or not Path(receipt.get("publicationOrigin", "")).resolve().is_relative_to(release / "src")
            ):
                raise RuntimeError(f"Publication receipt is not bound to copied formal current scene: {kind}")
            outputs[kind] = {"path": str(output), "receipt": receipt,
                             "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
        svg = (artifacts / f"figure-{width}.svg").read_bytes()
        xml = ET.fromstring(svg)
        viewbox = [float(item) for item in xml.attrib["viewBox"].split()]
        expected_height = width * viewbox[3] / viewbox[2]
        if float(xml.attrib["width"].removesuffix("mm")) != width:
            raise RuntimeError("Formal SVG has wrong physical width")
        text = svg.decode()
        for marker in ("Independent legend", "Current scene only", "Reviewed dropout", "#dfeaf2"):
            if marker not in text:
                raise RuntimeError(f"Export lost edited current-scene field {marker}")
        if "data-expand-id" in text:
            raise RuntimeError("Editor controls entered publication output")
        pdf = (artifacts / f"figure-{width}.pdf").read_bytes()
        match = re.search(rb"/MediaBox\s*\[\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]", pdf)
        if not match:
            raise RuntimeError("No PDF MediaBox found for independent physical-size check")
        box = [float(number) for number in match.groups()]
        expected_pt = [width / 25.4 * 72, expected_height / 25.4 * 72]
        actual_pt = [box[2] - box[0], box[3] - box[1]]
        if any(abs(a - b) > 0.05 for a, b in zip(actual_pt, expected_pt)):
            raise RuntimeError("PDF MediaBox disagrees with independently computed SVG page size")
        png = (artifacts / f"figure-{width}.png").read_bytes()
        expected_px = (round(width / 25.4 * 300), round(expected_height / 25.4 * 300))
        if png[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", png[16:24]) != expected_px:
            raise RuntimeError("PNG pixels disagree with SVG physical size and selected DPI")
        offset, density = 8, None
        while offset < len(png):
            size = struct.unpack(">I", png[offset:offset + 4])[0]
            if png[offset + 4:offset + 8] == b"pHYs":
                density = struct.unpack(">IIB", png[offset + 8:offset + 8 + size])
            offset += size + 12
        if density != (round(300 / 0.0254), round(300 / 0.0254), 1):
            raise RuntimeError("PNG physical density does not preserve the selected 300 DPI")
        checks.append({"name": f"current-scene-exports-{width}mm", "passed": True,
                       "pdfPagePt": actual_pt, "pngPixels": list(expected_px), "outputs": outputs,
                       "scope": "geometric and current-scene fields; host fonts not publication-certified"})

    # A real commit from independent handwritten source supplies the new facts.
    # The expected visual fields come from the original user operations, not
    # from reconcileDocument's output or a copied reanalysis implementation.
    source_project = artifacts / "parameter-project"
    source_project.mkdir()
    oracle_module = release / "tests" / "test_stage2_invariants.py"
    parameter_code = (
        "import importlib.util,json; from pathlib import Path; "
        f"spec=importlib.util.spec_from_file_location('independent_oracle',{str(oracle_module)!r}); "
        "oracle=importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle); "
        "from archcanvas_python import analyze_project; from archcanvas_transactions import TransactionManager; "
        f"root=Path({str(source_project)!r}); root.joinpath('model.py').write_text(oracle.SOURCE,encoding='utf-8'); "
        "root.joinpath('helper.py').write_text('NOTE = 1\\n',encoding='utf-8'); "
        "before=analyze_project(root,'model:Model'); node=next(n for n in before['nodes'] if n.get('instanceId','').endswith('.left')); "
        f"manager=TransactionManager(Path({str(artifacts / 'parameter-transactions')!r})); "
        "receipt=manager.prepare(root=root,entry='model:Model',nodeId=node['id'],parameter='p',value=0.2,baseSourceDigest=before['sourceDigest']); "
        "approved=manager.approve(receipt['id'],receipt['reviewDigest']); committed=manager.commit(receipt['id'],approved['approvalId']); "
        "assert committed['status']=='Committed'; assert root.joinpath('model.py').read_bytes()==oracle.handwritten_expected('p'); "
        f"Path({str(artifacts / 'reanalysis.json')!r}).write_text(json.dumps({{'before':before,'after':committed['committedArchitecture'],'transaction':committed}}),encoding='utf-8')"
    )
    command(python_args(interpreter, release, parameter_code), release, environment)
    reanalysis_check = artifacts / "check-reconciliation.mjs"
    reanalysis_check.write_text(
        "import {readFile,writeFile} from 'node:fs/promises'; import assert from 'node:assert/strict';\n"
        f"import {{createDocument,applyVisualBatch,buildScene,reconcileDocument,validateDocument,createHistory}} from {json.dumps((release / 'studio/src/core/index.ts').as_uri())};\n"
        f"const root={json.dumps(str(artifacts))}; const x=JSON.parse(await readFile(root+'/reanalysis.json','utf8'));\n"
        "const selected=x.before.nodes.find(n=>n.instanceId?.endsWith('.left'));"
        "const edge=x.before.edges.find(e=>e.target.nodeId===selected.id);\n"
        "let old=createDocument(x.before); old=applyVisualBatch(old,["
        "{type:'alias',id:selected.id,label:'Keep this alias'},"
        "{type:'nodeStyle',id:selected.id,style:{fill:'#123456',glyph:'operator'}},"
        "{type:'edgeStyle',id:edge.id,style:{stroke:'#654321',width:2.5,dashed:true}},"
        "{type:'legend',items:[{id:'manual-kept',label:'Keep manual legend',color:'#123456',glyph:'operator'}]},"
        "{type:'annotation',annotation:{id:'note-kept',text:'Keep manual note',x:31,y:617,width:250}},"
        "{type:'move',ids:[selected.id],dx:31,dy:13},{type:'pin',ids:[selected.id],pinned:true}]);\n"
        "const result=reconcileDocument(old,x.after); const next=result.document;"
        "for(const key of ['displayAliases','nodeStyleOverrides','edgeStyleOverrides','legendItems','annotations','pinnedObjects','expandedIds','layout','layoutByFrontier','pageSpec']) assert.deepEqual(next[key],old[key],key+' survives source reanalysis');\n"
        "assert.notEqual(next.sourceBindingDigest,old.sourceBindingDigest);assert.notEqual(next.id,old.id);"
        "assert.equal(next.architecture.nodes.find(n=>n.id===selected.id).parameters.p,0.2);"
        "assert.equal(next.revision,old.revision+1);assert.equal(result.removedNodeIds.length,0);"
        "const fresh=createHistory(next);assert.equal(fresh.past.length,0);assert.equal(fresh.future.length,0);"
        "const reopened=validateDocument(JSON.parse(JSON.stringify(next)));assert.deepEqual(reopened,next);"
        "const a=buildScene(old).nodes.find(n=>n.id===selected.id),b=buildScene(next).nodes.find(n=>n.id===selected.id);assert.equal(a.x,b.x);assert.equal(a.y,b.y);"
        "await writeFile(root+'/reconciled-document.json',JSON.stringify(next));"
        "await writeFile(root+'/reconciliation-receipt.json',JSON.stringify({documentId:next.id,revision:next.revision,preservedNodeIds:result.preservedNodeIds,preservedEdgeIds:result.preservedEdgeIds,preservedFields:['alias','nodeStyle','edgeStyle','legend','annotation','pin','frontier','layout','page'],history:'new source-bound empty visual history'}));\n",
        encoding="utf-8",
    )
    command([node, str(reanalysis_check)], release, environment)
    persistence_code = (
        "import json; from pathlib import Path; from archcanvas_cli.server import DocumentStore; "
        f"document=json.loads(Path({str(artifacts / 'reconciled-document.json')!r}).read_text()); "
        f"directory=Path({str(artifacts / 'reconciled-storage')!r}); store=DocumentStore(directory); "
        "saved=store.put(document['id'],document,0); reopened=DocumentStore(directory).get(document['id']); "
        "assert reopened['document']==document; assert reopened['revision']==1; assert reopened['document']['revision']==document['revision']"
    )
    command(python_args(interpreter, release, persistence_code), release, environment)
    checks.append({"name": "committed-source-reanalysis-preserves-visual-document", "passed": True,
                   "receipt": str(artifacts / "reconciliation-receipt.json"),
                   "document": str(artifacts / "reconciled-document.json"),
                   "storage": str(artifacts / "reconciled-storage"),
                   "scope": "independent same-call-identity parameter intent only; CAS save/reopen exact document; new source binding starts empty visual history"})
    report["passed"] = True
    report_path = temporary / "stage2-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", type=Path, help="explicit formal publication Python, defaults to project .venv/bin/python")
    parser.add_argument("--build", action="store_true")
    options = parser.parse_args()
    interpreter = options.python or options.project / ".venv" / "bin" / "python"
    if not interpreter.is_file():
        print(json.dumps({"passed": False, "error": f"Formal publication Python is unavailable: {interpreter}"}), file=sys.stderr)
        return 1
    try:
        path = check(options.project.resolve(), interpreter, options.build)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, "report": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
