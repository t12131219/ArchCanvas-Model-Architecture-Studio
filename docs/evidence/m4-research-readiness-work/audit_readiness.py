#!/usr/bin/env python3
"""Readonly preassignment audit; empty slots never certify human participation.

This supplementary evidence tool checks the whole slot state, which is outside
research_trial.py verify's deliberately narrower frozen-implementation scope.
It does not assign people, start a service, analyze/execute a model, or accept a
researcher task. Run it only before a new trial begins; used slots must be kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(',', ':')).encode())


def audit(project: Path, package: Path) -> dict:
    project, package = project.resolve(), package.resolve()
    checks, bindings = [], []

    def check(name: str, passed: bool, detail: object = None) -> None:
        checks.append({'check': name, 'passed': bool(passed), 'detail': detail})

    def read(path: Path, base: Path, group: str) -> bytes:
        if not path.resolve().is_relative_to(base.resolve()):
            raise ValueError(f'{group}: path escaped its authority root: {path}')
        current = path
        while current != base:
            if current.is_symlink():
                raise ValueError(f'{group}: symlink is not an independent artifact: {path}')
            current = current.parent
        if not path.is_file():
            raise ValueError(f'{group}: expected regular file: {path}')
        raw = path.read_bytes()
        bindings.append({'authority': group, 'path': str(path.relative_to(base)),
                         'sha256': digest(raw), 'bytes': len(raw)})
        return raw

    manifest_raw = read(package / 'manifest.json', package, 'package')
    manifest = json.loads(manifest_raw)
    check('protocol', manifest.get('schemaVersion') == 1
          and manifest.get('protocol') == 'archcanvas-m4-trial-package/1')
    check('preassignment-manifest', manifest.get('state') == 'prepared-no-participants'
          and manifest.get('researcherCount') == 0 and manifest.get('researchGate') == 'not_run')
    baseline = manifest['baseline']
    for item in baseline['files']:
        raw = read(package / item['path'], package, 'package')
        check('frozen-baseline:' + item['path'], digest(raw) == item['sha256'] and len(raw) == item['bytes'])
    for item in manifest['implementationFiles']:
        raw = read(project / item['path'], project, 'formal-implementation')
        check('frozen-implementation:' + item['path'], digest(raw) == item['sha256'] and len(raw) == item['bytes'])
    canvas = json.loads((package / 'baseline/canvas.json').read_bytes())
    check('baseline-canvas-contract', canvas['id'] == baseline['documentId']
          and canvas['revision'] == baseline['visualRevision'] == 0
          and canonical(canvas) == baseline['canvasCanonicalDigest']
          and canvas['sourceBindingDigest'] == baseline['sourceDigest']
          and canvas['architecture']['sourceDigest'] == baseline['sourceDigest']
          and canvas['architecture']['irDigest'] == baseline['irDigest'])
    check('baseline-unedited', not any(canvas[key] for key in
          ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'annotations', 'pinnedObjects', 'layoutByFrontier')))
    frozen_source = package / 'baseline/source'
    frozen = {str(p.relative_to(frozen_source)): digest(p.read_bytes()) for p in frozen_source.rglob('*.py')}
    fixture = project / 'fixtures/transformer'
    actual = {str(p.relative_to(fixture)): digest(read(p, project, 'formal-example')) for p in fixture.rglob('*.py')}
    check('formal-example-equals-frozen-source', frozen == actual)
    slots = manifest['slots']
    slot_ids, data_dirs, ports, envelope_digests, records = [], [], [], [], []
    for item in slots:
        slot_id = item['slotId']
        slot = package / 'slots' / slot_id
        slot_ids.append(slot_id)
        data_dir = (package / item['dataDir']).resolve()
        data_dirs.append(str(data_dir))
        ports.append(item['port'])
        check(slot_id + ':unassigned-manifest', item.get('participantCode') is None and item.get('assignment') == 'unassigned')
        check(slot_id + ':independent-data-dir', data_dir == (slot / 'workspace/documents').resolve())
        check(slot_id + ':no-assignment-or-collected', not (slot / 'assignment.json').exists() and not (slot / 'collected').exists())
        binding = item['baselineEnvelope']
        raw = read(package / binding['path'], package, 'package')
        envelope_digests.append(digest(raw))
        check(slot_id + ':exact-pristine-envelope', digest(raw) == binding['sha256'] and len(raw) == binding['bytes'])
        envelope = json.loads(raw)
        check(slot_id + ':same-canvas-storage-contract', envelope.get('document') == canvas
              and envelope.get('revision') == item['baselineStorageRevision'] == 1)
        expected_document = data_dir / (baseline['documentId'] + '.json')
        check(slot_id + ':single-baseline-document', list(data_dir.iterdir()) == [expected_document])
        nonempty = {group: [str(p.relative_to(slot)) for p in (slot / group).rglob('*') if p.is_file()]
                    for group in ('incoming', 'workspace/exports', 'workspace/projects', 'workspace/transactions')}
        check(slot_id + ':no-prior-artifacts', all(not paths for paths in nonempty.values()), nonempty)
        review = json.loads(read(slot / 'review-template.json', package, 'package'))
        check(slot_id + ':blank-independent-review', review.get('slotId') == slot_id
              and review.get('participantCode') is None and review.get('reviewer') is None
              and review.get('status') == 'pending-independent-review'
              and [task.get('task') for task in review.get('tasks', [])] == [1, 2, 3, 4, 5]
              and all(task.get('status') == 'pending' and task.get('evidencePaths') == [] and task.get('notes') == ''
                      for task in review.get('tasks', []))
              and all(review.get(key) == 'pending' for key in ('sourceUnchanged', 'publicationReadability', 'overallOutcome')))
        records.append({'slotId': slot_id, 'port': item['port'], 'dataDir': str(data_dir),
                        'baselineEnvelopeSha256': digest(raw), 'pristine': all(c['passed'] for c in checks if c['check'].startswith(slot_id + ':'))})
    check('three-to-five-independent-slots', 3 <= len(slots) <= 5 and len(set(slot_ids)) == len(slots)
          and len(set(data_dirs)) == len(slots) and len(set(ports)) == len(slots))
    check('matching-slot-envelope-bytes', len(set(envelope_digests)) == 1)
    check('unprivileged-local-port-values', all(type(port) is int and 1024 <= port <= 65535 for port in ports))
    environment = json.loads(read(package / 'environment-template.json', package, 'package'))
    check('blank-environment-template', environment.get('status') == 'pending-operator-observation'
          and all(environment.get(key) is None for key in ('browserName', 'browserVersion', 'hardware', 'viewport', 'devicePixelRatio'))
          and environment.get('fontResolutionEvidence') == [])
    check('no-claimed-observed-environment', not (package / 'environment.json').exists())
    symlinks = [str(path.relative_to(package)) for path in package.rglob('*') if path.is_symlink()]
    check('no-symlink-artifacts', not symlinks, symlinks)
    read(package / 'README.md', package, 'package')
    assignments = sorted(str(path.relative_to(package)) for path in package.glob('slots/*/assignment.json'))
    collected = sorted(str(path.relative_to(package)) for path in package.glob('slots/*/collected'))
    return {'schemaVersion': 1, 'audit': 'archcanvas-m4-research-preassignment-readiness/1',
            'generatedAt': datetime.now(timezone.utc).isoformat(), 'formalRoot': str(project), 'package': str(package),
            'packageManifestSha256': digest(manifest_raw), 'mechanicalSlotReadinessPassed': all(c['passed'] for c in checks),
            'verificationScope': 'preassignment frozen bytes, complete slot state and blank templates; no participation or human acceptance',
            'implementationBindings': len(manifest['implementationFiles']), 'baselineBindings': len(baseline['files']),
            'pristineSlotCount': sum(item['pristine'] for item in records), 'slots': records,
            'assignmentPathsObserved': assignments, 'collectedPathsObserved': collected,
            'collectedSlotRecordsObserved': len(collected),
            'actualResearcherRecordsObserved': 0 if not assignments and not collected else None, 'humanSuccessCertified': False,
            'researchGate': 'not_run' if not assignments and not collected else 'not_evaluated',
            'fixedBrowserHardwareFontsCertified': False, 'presentedPaintCertified': False,
            'checks': checks, 'bindings': bindings,
            'limitations': ['Empty seats do not prove human participation.',
                'Hashes and JSON consistency do not prove screenshots, operation timing, identity or publication readability.',
                'No service was started and no port-availability or live-browser claim is made.',
                'This preassignment audit must stop being used after actual assignment; preserve used slots and their results.',
                '3–5 real model-figure users and independent human artifact review remain required.']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.project, args.package)
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as handle:
                handle.write(payload)
        else:
            print(payload, end='')
        return 0 if result['mechanicalSlotReadinessPassed'] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Preassignment audit failed: {error}\n')


if __name__ == '__main__':
    sys.exit(main())
