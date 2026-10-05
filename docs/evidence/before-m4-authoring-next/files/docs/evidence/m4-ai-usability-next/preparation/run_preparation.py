#!/usr/bin/env python3
"""Prepare new routing-build evidence after an explicit matching freeze signal.

Only static analysis/core rendering and empty trial preparation run. No model,
service, package installation, browser capture, participant assignment or old
evidence mutation is performed. This evidence runner refuses output reuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
RESEARCH = Path('.archcanvas/m4-research-trial-routing-next')
GOLDS = Path('docs/evidence/visual-golds-routing-next')
MATRIX = Path('.archcanvas/browser-visual-matrix-routing-next')


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write('\n')


def snapshot():
    paths = {*(ROOT / 'src').rglob('*.py'),
             *(p for p in (ROOT / 'studio/src').rglob('*') if p.suffix in ('.ts', '.tsx', '.css')),
             *(p for p in (ROOT / 'studio/dist').rglob('*') if p.is_file())}
    paths.update(ROOT / 'scripts' / name for name in ('research_trial.py', 'research_trial_core.mjs',
                 'export_canvas.mjs', 'summarize_research_tasks.py', 'check_visual_golds.py',
                 'browser_visual_matrix.py', 'browser_visual_core.mjs'))
    return [{'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'bytes': path.stat().st_size}
            for path in sorted(paths)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-receipt', type=Path, required=True,
                        help='Root-reviewed JSON with expectedFiles path→SHA256 from final build signal.')
    args = parser.parse_args()
    expected = json.loads(args.freeze_receipt.read_bytes())
    if expected.get('freezeApprovedForPreparation') is not True:
        parser.error('Explicit final build freeze approval is required.')
    for name, value in expected['expectedFiles'].items():
        path = ROOT / name
        if not path.is_file() or sha(path) != value:
            parser.error(f'Final build signal no longer matches {name}; do not prepare stale evidence.')
    for directory in (RESEARCH, GOLDS, MATRIX):
        if (ROOT / directory).exists():
            parser.error(f'Output already exists; preserve it and choose a fresh scope: {directory}')
    python = str(ROOT / '.venv/bin/python')
    commands = [
        ('research-prepare', [python, 'scripts/research_trial.py', 'prepare', '--output', str(RESEARCH), '--slots', '5', '--first-port', '8921'], 0),
        ('research-verify', [python, 'scripts/research_trial.py', 'verify', '--package', str(RESEARCH)], 0),
        ('research-pristine-audit', [python, 'docs/evidence/m4-research-readiness-work/audit_readiness.py', '--project', '.', '--package', str(RESEARCH), '--output', str(WORK.relative_to(ROOT) / 'research-readiness-report.json')], 0),
        ('visual-core', [python, 'scripts/check_visual_golds.py', '--project', '.', '--python', str(ROOT / '.venv/bin/python'), '--output', str(GOLDS)], 0),
        ('matrix-prepare', [python, 'scripts/browser_visual_matrix.py', 'prepare', '--core-dir', str(GOLDS), '--output', str(MATRIX)], 0),
        ('matrix-verify', [python, 'scripts/browser_visual_matrix.py', 'verify', '--matrix', str(MATRIX)], 0),
        ('old-research-current-build-verify', [python, 'scripts/research_trial.py', 'verify', '--package', '.archcanvas/m4-research-trial-boundary-final'], 1),
    ]
    before = snapshot()
    write_new(WORK / 'freeze-before.json', {'generatedAt': now(), 'files': before})
    process = {'schemaVersion': 1, 'audit': 'new-routing-static-and-research-preparation/1',
               'startedAt': now(), 'freezeReceipt': str(args.freeze_receipt.resolve()),
               'freezeReceiptSha256': sha(args.freeze_receipt), 'commands': [],
               'sourceBuildChangedDuringPreparation': None, 'status': 'running',
               'browserCaptures': 0, 'realResearchers': 0, 'humanSuccessCertified': False,
               'researchGate': 'not_run', 'modelExecuted': False, 'serviceStarted': False,
               'coverageInheritedFromOldBuild': False}
    try:
        for name, command, expected_code in commands:
            started = now()
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            logs = {}
            for stream, payload in (('stdout', result.stdout), ('stderr', result.stderr)):
                path = WORK / f'{name}.{stream}.txt'
                with path.open('x', encoding='utf-8') as handle:
                    handle.write(payload)
                logs[stream] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'bytes': path.stat().st_size}
            process['commands'].append({'name': name, 'command': command, 'cwd': str(ROOT),
                'startedAt': started, 'finishedAt': now(), 'exitCode': result.returncode,
                'expectedExitCode': expected_code, 'logs': logs})
            print(f'{name}: exit {result.returncode}', flush=True)
            if result.returncode != expected_code:
                raise ValueError(f'{name}: expected exit {expected_code}, observed {result.returncode}')
        after = snapshot()
        write_new(WORK / 'freeze-after.json', {'generatedAt': now(), 'files': after})
        process['sourceBuildChangedDuringPreparation'] = before != after
        if before != after:
            raise ValueError('Source/build/tools changed during preparation; this scope is stale.')
        research = json.loads((ROOT / RESEARCH / 'manifest.json').read_bytes())
        golds = json.loads((ROOT / GOLDS / 'visual-gold-report.json').read_bytes())
        matrix = json.loads((ROOT / MATRIX / 'spec.json').read_bytes())
        readiness = json.loads((WORK / 'research-readiness-report.json').read_bytes())
        process['research'] = {'path': str(RESEARCH), 'manifestSha256': sha(ROOT / RESEARCH / 'manifest.json'),
            'implementationBindings': len(research['implementationFiles']), 'baselineBindings': len(research['baseline']['files']),
            'slots': len(research['slots']), 'ports': [slot['port'] for slot in research['slots']],
            'pristineSlots': readiness['pristineSlotCount'], 'mechanicalReadinessPassed': readiness['mechanicalSlotReadinessPassed'],
            'assigned': len(list((ROOT / RESEARCH).glob('slots/*/assignment.json'))),
            'collected': len(list((ROOT / RESEARCH).glob('slots/*/collected'))), 'researchers': 0, 'researchGate': 'not_run'}
        process['visualCore'] = {'path': str(GOLDS), 'reportSha256': sha(ROOT / GOLDS / 'visual-gold-report.json'),
            'variants': len(golds['variants']), 'geometryPassed': golds['geometryPassed'], 'spatialCorePassed': golds['spatialCorePassed'],
            'visualAcceptance': golds['visualAcceptance'], 'areBrowserScreenshots': False}
        process['matrix'] = {'path': str(MATRIX), 'specSha256': sha(ROOT / MATRIX / 'spec.json'),
            'variants': len(matrix['variants']), 'frontiers': len(matrix['frontiers']),
            'coreBindings': len(matrix['coreFiles']), 'implementationBindings': len(matrix['implementationFiles']),
            'buildBindings': len(matrix['buildFiles']), 'capturedBaselines': 0, 'capturedEditedCases': 0,
            'visualAcceptance': matrix['visualAcceptance'], 'humanAcceptanceCertified': False}
        process['status'] = 'prepared-verified-pristine-no-browser-or-human-acceptance'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        process['status'] = 'failed-or-stale-preserve-artifacts'
        process['error'] = str(error)
    finally:
        process['finishedAt'] = now()
        write_new(WORK / 'process.json', process)
    return 0 if process['status'] == 'prepared-verified-pristine-no-browser-or-human-acceptance' else 1


if __name__ == '__main__':
    sys.exit(main())
