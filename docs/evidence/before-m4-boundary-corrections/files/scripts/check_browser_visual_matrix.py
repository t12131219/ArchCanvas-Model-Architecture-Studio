#!/usr/bin/env python3
"""Independently check matrix artifact contracts with labelled automation fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    release = Path(tempfile.mkdtemp(prefix='archcanvas-matrix-independent-')) / 'release'
    release.mkdir()
    for name in ('src', 'fixtures/transformer', 'fixtures/mlp', 'fixtures/residual_cnn', 'studio/src/core', 'studio/dist'):
        shutil.copytree(root / name, release / name, ignore=shutil.ignore_patterns('__pycache__'))
    (release / 'scripts').mkdir()
    for name in ('browser_visual_matrix.py', 'browser_visual_core.mjs', 'check_visual_golds.py', 'check_independence.py', 'check_stage2.py'):
        shutil.copyfile(root / 'scripts' / name, release / 'scripts' / name)
    (release / 'tests').mkdir()
    shutil.copyfile(root / 'tests/test_browser_visual_matrix.py', release / 'tests/test_browser_visual_matrix.py')
    code = ('import pathlib,sys,unittest; '
            f'sys.path.insert(0,{str(release / "tests")!r}); '
            'import test_browser_visual_matrix as t; '
            f'assert pathlib.Path(t.module.__file__).resolve().is_relative_to(pathlib.Path({str(release)!r})); '
            f'assert pathlib.Path(sys.modules["archcanvas_publication"].__file__).resolve().is_relative_to(pathlib.Path({str(release)!r})); '
            'suite=unittest.defaultTestLoader.loadTestsFromModule(t); '
            'result=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())')
    run = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], cwd=release, capture_output=True, text=True, timeout=60)
    options.output.mkdir(parents=True, exist_ok=True)
    (options.output / 'independent-suite.txt').write_text(run.stdout + run.stderr)
    if run.returncode:
        print(run.stderr, file=sys.stderr)
        return run.returncode
    files = ('scripts/browser_visual_matrix.py', 'scripts/browser_visual_core.mjs', 'tests/test_browser_visual_matrix.py')
    report = {'schemaVersion': 1, 'audit': 'browser-visual-matrix-artifact-contracts', 'testStatus': 'passed', 'testCount': 8,
        'independentRelease': str(release), 'pythonIsolation': ['-I', '-S', '-B'],
        'files': [{'path': name, 'sha256': hashlib.sha256((release / name).read_bytes()).hexdigest()} for name in files],
        'realBrowserCaptureCount': 0, 'humanAcceptanceCertified': False, 'visualAcceptance': 'not_evaluated',
        'limitations': ['Eight automation counterexamples verify file/source/DOM/export/build/snapshot contracts only.',
            'The tiny test image and fabricated browser observations are explicitly automation fixtures, not real screenshots.',
            'Real browser captures and independent human review must be collected separately.']}
    (options.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
