#!/usr/bin/env python3
"""Independent first M3 fragment from a formal copy and handwritten /tmp model.

All successful approval/commit actions concern this check's own source project.
The registered symbolic compatibility profile does not execute user models.
This is not the full M3 runtime-profile completion check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from check_independence import clean_environment
from check_stage2 import check as check_stage2, command, python_args


def check(project: Path, interpreter: Path, build: bool) -> Path:
    stage2_path = check_stage2(project, interpreter, build)
    stage2 = json.loads(stage2_path.read_text(encoding='utf-8'))
    release = Path(stage2['sourceCopy'])
    temporary = release.parent
    environment = clean_environment(temporary)
    artifacts = temporary / 'stage3-artifacts'
    artifacts.mkdir()
    suite_code = (
        'import unittest; '
        f"suite=unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_stage3_invariants.py'); "
        'result=unittest.TextTestRunner(verbosity=2).run(suite); '
        'sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun > 0 else 1)'
    )
    command(python_args(interpreter, release, suite_code), release, environment)
    source_project = artifacts / 'project'
    source_project.mkdir()
    receipt_code = (
        'import importlib.util,json; from pathlib import Path; '
        f"spec=importlib.util.spec_from_file_location('oracle',{str(release / 'tests/test_stage3_invariants.py')!r}); "
        'oracle=importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle); '
        'from archcanvas_python import analyze_project; from archcanvas_python.rebind import inspect_rebind; '
        'from archcanvas_transactions import TransactionManager; '
        f'root=Path({str(source_project)!r}); root.joinpath("model.py").write_bytes(oracle.SOURCE.encode()); '
        'before=analyze_project(root,"model:Model"); '
        'target=next(n for n in before["nodes"] if n.get("instanceId","").endswith(".sink")); '
        'producer=next(n for n in before["nodes"] if n.get("instanceId","").endswith(".branch")); '
        'evidence=inspect_rebind(root,"model:Model",target["id"]); assert evidence["status"]=="supported"; '
        f'manager=TransactionManager(Path({str(artifacts / "transactions")!r})); '
        'review=manager.prepare_rebind(root=root,entry="model:Model",nodeId=target["id"],'
        'portId=next(p["id"] for p in target["ports"] if p["name"]=="input"),'
        'producerNodeId=producer["id"],producerPortId=next(p["id"] for p in producer["ports"] if p["direction"]=="out"),'
        'baseSourceDigest=before["sourceDigest"]); assert review["status"]=="ReviewReady"; '
        'approved=manager.approve(review["id"],review["reviewDigest"]); '
        'committed=manager.commit(review["id"],approved["approvalId"]); assert committed["status"]=="Committed"; '
        'assert root.joinpath("model.py").read_bytes()==oracle.handwritten_expected(); '
        f'Path({str(artifacts / "original-model.py")!r}).write_bytes(oracle.SOURCE.encode()); '
        f'Path({str(artifacts / "rebind-evidence.json")!r}).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8"); '
        f'Path({str(artifacts / "review.json")!r}).write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8"); '
        f'Path({str(artifacts / "commit.json")!r}).write_text(json.dumps(committed,ensure_ascii=False,indent=2),encoding="utf-8"); '
        f'Path({str(artifacts / "architecture-pair.json")!r}).write_text(json.dumps({{"before":before,"after":committed["committedArchitecture"]}},ensure_ascii=False),encoding="utf-8")'
    )
    command(python_args(interpreter, release, receipt_code), release, environment)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node 24+ is required for the formal Scene renderer')
    visual_check = artifacts / 'check-rebind-scene.mjs'
    visual_check.write_text(
        "import {readFile,writeFile} from 'node:fs/promises'; import assert from 'node:assert/strict';\n"
        f"import {{createDocument,applyVisualBatch,reconcileDocument,buildScene,renderSvg,createHistory}} from {json.dumps((release / 'studio/src/core/index.ts').as_uri())};\n"
        f"const root={json.dumps(str(artifacts))};const pair=JSON.parse(await readFile(root+'/architecture-pair.json','utf8'));\n"
        "const sink=pair.before.nodes.find(n=>n.instanceId?.endsWith('.sink'));"
        "const first=pair.before.nodes.find(n=>n.instanceId?.endsWith('.first'));"
        "const unaffected=pair.before.edges.find(e=>e.target.nodeId===first.id);"
        "let old=applyVisualBatch(createDocument(pair.before),["
        "{type:'alias',id:sink.id,label:'Reviewed connection / 已审核连接'},"
        "{type:'nodeStyle',id:sink.id,style:{fill:'#ece3f4'}},"
        "{type:'edgeStyle',id:unaffected.id,style:{stroke:'#637d71',width:2,dashed:true}},"
        "{type:'legend',items:[{id:'m3-legend',label:'Same input symbolic signature',color:'#ece3f4',glyph:'operator'}]},"
        "{type:'move',ids:[sink.id],dx:13,dy:7},{type:'pin',ids:[sink.id],pinned:true}]);\n"
        "const bounds=buildScene(old).bounds;old=applyVisualBatch(old,[{type:'annotation',annotation:{"
        "id:'m3-note',text:'Static contract only / 未执行模型',x:bounds.x,y:bounds.y+bounds.height+32,width:350}}]);"
        "const result=reconcileDocument(old,pair.after);const next=result.document;"
        "for(const key of ['displayAliases','nodeStyleOverrides','edgeStyleOverrides','legendItems','annotations','pinnedObjects','expandedIds','layout','layoutByFrontier','pageSpec']) assert.deepEqual(next[key],old[key],key);"
        "assert.equal(createHistory(next).past.length,0);assert.equal(next.revision,old.revision+1);"
        "const a=buildScene(old),b=buildScene(next);"
        "assert.equal(a.nodes.find(n=>n.id===sink.id).x,b.nodes.find(n=>n.id===sink.id).x);"
        "assert.equal(a.nodes.find(n=>n.id===sink.id).y,b.nodes.find(n=>n.id===sink.id).y);"
        "await writeFile(root+'/before-document.json',JSON.stringify(old));await writeFile(root+'/after-document.json',JSON.stringify(next));"
        "await writeFile(root+'/before.svg',renderSvg(a));await writeFile(root+'/after.svg',renderSvg(b));"
        "await writeFile(root+'/scene-receipt.json',JSON.stringify({documentId:next.id,revision:next.revision,preservedNodeIds:result.preservedNodeIds,preservedEdgeIds:result.preservedEdgeIds,removedEdgeIds:result.removedEdgeIds,history:'new source-bound empty visual history'}));\n",
        encoding='utf-8',
    )
    command([node, str(visual_check)], release, environment)
    report = {
        'schemaVersion': 1, 'passed': True,
        'scope': 'M3 first fragment: entry-forward straight-line same-base unary RebindInput; no runtime verification',
        'sourceCopy': str(release), 'stage2Report': str(stage2_path),
        'checks': [
            {'name': 'independent-rebind-black-box-suite', 'passed': True,
             'source': str(release / 'tests/test_stage3_invariants.py'), 'scope': 'all successful writes under /tmp'},
            {'name': 'handwritten-one-name-one-binding-commit', 'passed': True,
             'beforeSource': str(artifacts / 'original-model.py'), 'afterSource': str(source_project / 'model.py'),
             'evidence': str(artifacts / 'rebind-evidence.json'), 'review': str(artifacts / 'review.json'),
             'commit': str(artifacts / 'commit.json')},
            {'name': 'rebind-reanalysis-preserves-visual-document', 'passed': True,
             'receipt': str(artifacts / 'scene-receipt.json'), 'beforeSvg': str(artifacts / 'before.svg'),
             'afterSvg': str(artifacts / 'after.svg'), 'document': str(artifacts / 'after-document.json')},
        ],
    }
    report_path = temporary / 'stage3-report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--python', type=Path)
    parser.add_argument('--build', action='store_true')
    options = parser.parse_args()
    interpreter = options.python or options.project / '.venv/bin/python'
    if not interpreter.is_file():
        print(json.dumps({'passed': False, 'error': f'Formal Python is unavailable: {interpreter}'}), file=sys.stderr)
        return 1
    try:
        path = check(options.project.resolve(), interpreter, options.build)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'passed': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({'passed': True, 'report': str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
