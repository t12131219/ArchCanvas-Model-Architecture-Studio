#!/usr/bin/env python3
"""Independent full-M3 gates from a formal source copy and /tmp sample projects.

This requires actual Linux isolation and treats skips/unavailable as unmet gates.
Publication and CPU execution dependencies use separately explicit formal envs.
All simulated approvals and successful commits concern this check's own source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from check_independence import clean_environment
from check_stage2 import command, python_args
from check_stage3 import check as check_first_fragment


def check(project: Path, publication_python: Path, runtime_python: Path, build: bool) -> Path:
    fragment_path = check_first_fragment(project, publication_python, build)
    fragment = json.loads(fragment_path.read_text(encoding='utf-8'))
    release = Path(fragment['sourceCopy'])
    temporary = release.parent
    environment = clean_environment(temporary)
    environment['ARCHCANVAS_REQUIRE_RUNTIME'] = '1'
    environment['ARCHCANVAS_RUNTIME_PYTHON'] = str(runtime_python.absolute())
    environment['ARCHCANVAS_RUNTIME_LOCK'] = str(release / 'requirements-runtime.lock')
    report: dict[str, object] = {
        'schemaVersion': 1, 'passed': False, 'scope': 'full M3 runtime and multi-input structural transaction samples',
        'sourceCopy': str(release), 'firstFragmentReport': str(fragment_path),
        'runtimePython': str(runtime_python.absolute()), 'publicationPython': str(publication_python.absolute()),
        'checks': [], 'limitations': [
            'Linux x86-64 CPU worker only; sample modes/inputs do not prove all-program behavior or numerical equivalence.',
            'Explicit installed formal dependencies are used; this is not a clean network install or three-host certification.',
            'All approvals/writes concern independent /tmp projects; no original user model or checkpoint is changed.',
        ],
    }
    checks = report['checks']
    suite_code = (
        'import unittest; suite=unittest.TestSuite(); '
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m3_runtime_invariants.py')); "
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m3_complete_invariants.py')); "
        f"suite.addTests(unittest.defaultTestLoader.discover({str(release / 'tests')!r}, pattern='test_m3_product_invariants.py')); "
        'result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); '
        'sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun > 0 else 1)'
    )
    suite_run = subprocess.run(python_args(publication_python, release, suite_code), cwd=release,
                               env=environment, capture_output=True, timeout=480)
    if suite_run.returncode:
        raise RuntimeError('Independent complete-M3 suite failed:\n' + suite_run.stdout.decode(errors='replace') + suite_run.stderr.decode(errors='replace'))
    output = suite_run.stdout + suite_run.stderr
    artifacts = temporary / 'm3-complete-artifacts'
    artifacts.mkdir()
    (artifacts / 'independent-suite.stdout').write_bytes(output)
    checks.append({'name': 'independent-isolation-runtime-and-mha-transaction-holdouts', 'passed': True,
                   'scope': 'actual worker; no skip; all originals under /tmp'})
    project_copy = artifacts / 'project'
    project_copy.mkdir()
    receipt_code = (
        'import json,importlib.util; from pathlib import Path; '
        f"spec=importlib.util.spec_from_file_location('oracle',{str(release / 'tests/m3_runtime_oracle.py')!r}); "
        'oracle=importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle); '
        'from archcanvas_python import analyze_project; from archcanvas_runtime import verify_structural; '
        'from archcanvas_transactions import TransactionManager; '
        f'root=Path({str(project_copy)!r}); root.joinpath("model.py").write_bytes(oracle.SOURCE.encode()); '
        f'config={{"interpreter":{str(runtime_python.absolute())!r},"dependencyLock":{str(release / "requirements-runtime.lock")!r},"timeoutSeconds":20,"memoryMb":4096,"cpuSeconds":20}}; '
        'before=analyze_project(root,"model:CrossAttention"); original=verify_structural(root,"model:CrossAttention",oracle.input_spec(),config); '
        'assert original["status"]=="passed"; '
        'target=next(n for n in before["nodes"] if n.get("instanceId","").endswith(".attention")); '
        'producer=next(n for n in before["nodes"] if n.get("instanceId","").endswith(".key_activation")); '
        f'manager=TransactionManager(Path({str(artifacts / "transactions")!r})); '
        'review=manager.prepare_rebind(root=root,entry="model:CrossAttention",nodeId=target["id"],'
        'portId=next(p["id"] for p in target["ports"] if p["name"]=="key"),producerNodeId=producer["id"],'
        'producerPortId=next(p["id"] for p in producer["ports"] if p["direction"]=="out"),'
        'baseSourceDigest=before["sourceDigest"],inputSpec=oracle.input_spec(),runtimeConfig=config); '
        'assert review["status"]=="ReviewReady",review["blockers"]; '
        'assert next(g["status"] for g in review["gates"] if g["id"]=="G6")=="passed"; '
        'approved=manager.approve(review["id"],review["reviewDigest"]); '
        'committed=manager.commit(review["id"],approved["approvalId"]); assert committed["status"]=="Committed",committed["blockers"]; '
        'assert root.joinpath("model.py").read_bytes()==oracle.expected_source(); '
        f'out=Path({str(artifacts)!r}); out.joinpath("original-model.py.txt").write_bytes(oracle.SOURCE.encode()); '
        'out.joinpath("original-runtime.json").write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding="utf-8"); '
        'out.joinpath("review.json").write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding="utf-8"); '
        'out.joinpath("commit.json").write_text(json.dumps(committed,ensure_ascii=False,indent=2),encoding="utf-8"); '
        'out.joinpath("input-spec.json").write_text(json.dumps(oracle.input_spec(),ensure_ascii=False,indent=2),encoding="utf-8")'
    )
    command(python_args(publication_python, release, receipt_code), release, environment)
    original = json.loads((artifacts / 'original-runtime.json').read_text(encoding='utf-8'))
    review = json.loads((artifacts / 'review.json').read_text(encoding='utf-8'))
    commit = json.loads((artifacts / 'commit.json').read_text(encoding='utf-8'))
    if original['status'] != 'passed' or original['manifest']['isolation']['available'] is not True:
        raise RuntimeError('Actual full-M3 runtime and kernel isolation did not pass')
    checks.append({'name': 'multi-input-sample-role-shape-backward-replay-and-state', 'passed': True,
                   'receipt': str(artifacts / 'original-runtime.json'),
                   'environment': original['manifest']['environment'], 'isolation': original['manifest']['isolation'],
                   'limits': original['manifest']['limits'], 'inputSpec': str(artifacts / 'input-spec.json')})
    checks.append({'name': 'reviewed-mha-key-only-commit-with-mandatory-G6', 'passed': True,
                   'review': str(artifacts / 'review.json'), 'commit': str(artifacts / 'commit.json'),
                   'beforeSource': str(artifacts / 'original-model.py.txt'), 'afterSource': str(project_copy / 'model.py'),
                   'profile': review['intent']['validationProfile'], 'status': commit['status']})
    report['passed'] = True
    report_path = temporary / 'm3-complete-report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--publication-python', type=Path)
    parser.add_argument('--runtime-python', type=Path)
    parser.add_argument('--build', action='store_true')
    options = parser.parse_args()
    publication = options.publication_python or options.project / '.venv/bin/python'
    runtime = options.runtime_python or options.project / '.venv-runtime/bin/python'
    try:
        if not publication.is_file() or not runtime.is_file():
            raise RuntimeError('Explicit formal publication and CPU runtime interpreters are required')
        path = check(options.project.resolve(), publication, runtime, options.build)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'passed': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({'passed': True, 'report': str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
