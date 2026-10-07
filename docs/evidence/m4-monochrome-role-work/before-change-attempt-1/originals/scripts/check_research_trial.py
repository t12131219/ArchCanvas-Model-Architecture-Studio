#!/usr/bin/env python3
"""Run artifact-binding counterexamples in an independent formal source copy."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    release = Path(tempfile.mkdtemp(prefix='archcanvas-research-independent-')) / 'release'
    release.mkdir()
    for name in ('src', 'fixtures/transformer', 'studio/src', 'studio/dist'):
        shutil.copytree(project / name, release / name, ignore=shutil.ignore_patterns('__pycache__'))
    (release / 'scripts').mkdir()
    for name in ('research_trial.py', 'research_trial_core.mjs', 'summarize_research_tasks.py', 'export_canvas.mjs'):
        shutil.copyfile(project / 'scripts' / name, release / 'scripts' / name)
    (release / 'tests').mkdir()
    shutil.copyfile(project / 'tests/test_research_trial.py', release / 'tests/test_research_trial.py')
    args.output.mkdir(parents=True, exist_ok=True)
    bootstrap = (
        'import pathlib,sys,unittest; '
        f'sys.path.insert(0,{str(release / "tests")!r}); '
        'import test_research_trial; '
        f'assert pathlib.Path(test_research_trial.module.__file__).resolve().is_relative_to(pathlib.Path({str(release)!r})); '
        f'assert pathlib.Path(sys.modules["archcanvas_python"].__file__).resolve().is_relative_to(pathlib.Path({str(release)!r})); '
        f'assert pathlib.Path(sys.modules["archcanvas_publication"].__file__).resolve().is_relative_to(pathlib.Path({str(release)!r})); '
        'suite=unittest.defaultTestLoader.loadTestsFromModule(test_research_trial); '
        'result=unittest.TextTestRunner(verbosity=2).run(suite); '
        'sys.exit(not result.wasSuccessful())'
    )
    completed = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', bootstrap], cwd=release,
                               capture_output=True, text=True, timeout=120)
    (args.output / 'independent-suite.txt').write_text(completed.stdout + completed.stderr, encoding='utf-8')
    if completed.returncode:
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    files = ('scripts/research_trial.py', 'scripts/research_trial_core.mjs', 'tests/test_research_trial.py')
    report = {'schemaVersion': 1, 'audit': 'm4-research-trial-artifact-binding',
        'testStatus': 'passed', 'testCount': 12, 'independentRelease': str(release),
        'isolatedPython': ['-I', '-S', '-B'], 'formalModulesVerified': ['research_trial', 'archcanvas_python', 'archcanvas_publication'],
        'files': [{'path': name, 'sha256': hashlib.sha256((release / name).read_bytes()).hexdigest()} for name in files],
        'researcherCount': 0, 'researchGate': 'not_run', 'humanSuccessCertified': False,
        'limitations': ['Automated negative tests verify file binding, not human figure editing.',
            'Test image is a labelled automation fixture, not an actual Studio screenshot.',
            'Prepared slots must be run by real researchers and independently reviewed.']}
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
