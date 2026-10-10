#!/usr/bin/env python3
"""Prepare isolated, unassigned M4 trial slots and bind real local trial artifacts.

This script neither recruits people nor certifies human task success. Collected
records remain self reports pending independent review, including automation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from archcanvas_python import analyze_project
from archcanvas_cli.server import DocumentStore
from archcanvas_publication import export_svg
from summarize_research_tasks import object_value, validate_task

PROTOCOL = 'archcanvas-m4-trial-package/1'
CODE = re.compile(r'[A-Za-z0-9_-]{1,40}\Z')
IDENTITY = re.compile(r'[a-f0-9]{32}\Z')
SHOT = re.compile(r'(?:start|final|step[1-5]|undo-before|undo-after|redo-after|reloaded|export-open)\Z')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')


def read_json(path: Path) -> dict:
    return object_value(json.loads(path.read_bytes()), path.name)


def file_binding(path: Path, relative_to: Path) -> dict:
    raw = path.read_bytes()
    return {'path': str(path.relative_to(relative_to)), 'sha256': sha(raw), 'bytes': len(raw)}


def regular(path: Path) -> Path:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f'Expected a regular non-symlink file: {path}')
    return path


def managed(path: Path, directory: Path) -> Path:
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Artifact escaped its selected slot workspace.')
    current = path
    while current != directory:
        if current.is_symlink():
            raise ValueError('Managed slot artifacts cannot use symlink files/directories.')
        current = current.parent
    return regular(path)


def core(action: str, input_path: Path, output: Path) -> None:
    node = shutil.which('node')
    if not node:
        raise ValueError('The trial package requires Node 24+ and the formal TypeScript core.')
    result = subprocess.run([node, str(ROOT / 'scripts/research_trial_core.mjs'), action, str(input_path), str(output)],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Formal core verification failed: ' + result.stderr[-2000:].strip())


def prepare(output: Path, slots: int = 5, first_port: int = 8871) -> dict:
    if type(slots) is not int or not 3 <= slots <= 5:
        raise ValueError('Prepare 3–5 unassigned slots, not fabricated participants.')
    if type(first_port) is not int or not 1024 <= first_port <= 65535 - slots + 1:
        raise ValueError('Slot ports must be distinct unprivileged local ports.')
    if not (ROOT / 'studio/dist/index.html').is_file():
        raise ValueError('Build the formal Studio first; a trial package must freeze an actual runnable build.')
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Trial output already exists; frozen baselines must not be overwritten.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.research-prepare-', dir=output.parent))
    try:
        baseline = temporary / 'baseline'
        source = baseline / 'source'
        source.mkdir(parents=True)
        fixture = ROOT / 'fixtures/transformer'
        for path in sorted(fixture.rglob('*.py')):
            regular(path)
            target = source / path.relative_to(fixture)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        architecture = analyze_project(source, 'model:Transformer')
        write_json(baseline / 'architecture.json', architecture)
        core('create', baseline / 'architecture.json', baseline / 'canvas.json')
        document = read_json(baseline / 'canvas.json')
        files = [file_binding(path, temporary) for path in sorted(baseline.rglob('*')) if path.is_file()]
        common = {'documentId': document['id'], 'visualRevision': document['revision'],
                  'sourceDigest': architecture['sourceDigest'], 'irDigest': architecture['irDigest'],
                  'canvasCanonicalDigest': canonical(document), 'files': files}
        slot_records = []
        for index in range(slots):
            identity = f'S{index + 1:02d}'
            slot = temporary / 'slots' / identity
            documents = slot / 'workspace/documents'
            slot.mkdir(parents=True)
            envelope = DocumentStore(documents).put(document['id'], document, 0)
            (slot / 'incoming').mkdir()
            (slot / 'workspace/exports').mkdir()
            record = {'slotId': identity, 'participantCode': None, 'assignment': 'unassigned',
                      'port': first_port + index, 'dataDir': f'slots/{identity}/workspace',
                      'baselineEnvelope': file_binding(documents / f"{document['id']}.json", temporary),
                      'baselineStorageRevision': envelope['revision']}
            write_json(slot / 'review-template.json', {'protocol': PROTOCOL, 'slotId': identity,
                'participantCode': None, 'reviewer': None, 'status': 'pending-independent-review',
                'tasks': [{'task': task, 'status': 'pending', 'evidencePaths': [], 'notes': ''} for task in range(1, 6)],
                'sourceUnchanged': 'pending', 'publicationReadability': 'pending', 'overallOutcome': 'pending'})
            slot_records.append(record)
        tools = [ROOT / 'scripts/research_trial.py', ROOT / 'scripts/research_trial_core.mjs',
                 ROOT / 'scripts/export_canvas.mjs', ROOT / 'scripts/atomic_export.mjs', ROOT / 'scripts/summarize_research_tasks.py',
                 *sorted((ROOT / 'src').rglob('*.py')),
                 *sorted(path for path in (ROOT / 'studio/src').rglob('*') if path.suffix in ('.ts', '.tsx', '.css')),
                 *sorted(path for path in (ROOT / 'studio/dist').rglob('*') if path.is_file())]
        node = Path(shutil.which('node')).resolve()
        node_version = subprocess.run([str(node), '--version'], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        write_json(temporary / 'environment-template.json', {'protocol': PROTOCOL,
            'status': 'pending-operator-observation', 'browserName': None, 'browserVersion': None,
            'hardware': None, 'fontResolutionEvidence': [], 'viewport': None, 'devicePixelRatio': None,
            'limitations': ['Do not infer a fixed browser, hardware or font environment from the package runtime.']})
        manifest = {'schemaVersion': 1, 'protocol': PROTOCOL, 'createdAt': now(), 'state': 'prepared-no-participants',
                    'formalRoot': str(ROOT), 'baseline': common, 'slots': slot_records,
                    'implementationFiles': [file_binding(path, ROOT) for path in tools],
                    'preparationRuntime': {'pythonExecutable': str(Path(sys.executable).absolute()),
                        'pythonVersion': platform.python_version(), 'nodeExecutable': str(node), 'nodeVersion': node_version,
                        'platform': platform.platform(), 'machine': platform.machine(),
                        'analyzerOrigin': str(Path(sys.modules[analyze_project.__module__].__file__).resolve())},
                    'researcherCount': 0, 'researchGate': 'not_run',
                    'limitations': ['Slots are unassigned and are not evidence of human participation.',
                        'SHA256 binds bytes, not participant identity or screenshot content.',
                        'No collected bundle can automatically certify human task success.']}
        write_json(temporary / 'manifest.json', manifest)
        (temporary / 'README.md').write_text(
            '# Prepared M4 trial slots\n\nNo participant has run these slots.\n\n'
            'Follow docs/m4-research-protocol.md in the formal project. Each slot owns its workspace. '
            'Use a separate browser session, the slot port and slot data-dir. Never reuse a slot.\n\n'
            'The manifest freezes source, IR, Canvas and implementation file hashes. Review templates remain blank.\n', encoding='utf-8')
        temporary.rename(output)
        return manifest
    except Exception:
        shutil.rmtree(temporary)
        raise


def checked_package(package: Path) -> dict:
    manifest = read_json(regular(package / 'manifest.json'))
    if manifest.get('schemaVersion') != 1 or manifest.get('protocol') != PROTOCOL:
        raise ValueError('Unsupported trial package manifest.')
    for binding in manifest['baseline']['files']:
        path = package / binding['path']
        if not path.resolve().is_relative_to((package / 'baseline').resolve()) or file_binding(regular(path), package) != binding:
            raise ValueError('Frozen baseline file hash mismatch.')
    for binding in manifest['implementationFiles']:
        path = ROOT / binding['path']
        if not path.resolve().is_relative_to(ROOT) or file_binding(regular(path), ROOT) != binding:
            raise ValueError('Formal implementation changed after preparation; prepare a fresh package.')
    # The Studio bundled example reads the formal fixture; verify it still equals
    # the frozen source snapshot rather than silently importing a changed model.
    frozen = package / 'baseline/source'
    fixture = ROOT / 'fixtures/transformer'
    expected = {str(p.relative_to(frozen)): sha(p.read_bytes()) for p in frozen.rglob('*.py')}
    actual = {str(p.relative_to(fixture)): sha(regular(p).read_bytes()) for p in fixture.rglob('*.py')}
    if expected != actual:
        raise ValueError('Formal example source differs from the frozen trial baseline.')
    return manifest


def assign(package: Path, slot_id: str, participant_code: str, kind: str) -> dict:
    """Bind an operator-selected actual code to a pristine slot, without a timer."""
    package = package.resolve()
    manifest = checked_package(package)
    package_manifest_raw = regular(package / 'manifest.json').read_bytes()
    if object_value(json.loads(package_manifest_raw), 'package manifest') != manifest:
        raise ValueError('Package manifest changed during verification.')
    slots = [slot for slot in manifest['slots'] if slot['slotId'] == slot_id]
    if len(slots) != 1 or not CODE.fullmatch(participant_code) or kind not in ('researcher', 'automation'):
        raise ValueError('Assign an existing pristine slot and an exact participant code/type.')
    record = slots[0]
    slot = package / 'slots' / slot_id
    if (slot / 'assignment.json').exists() or (slot / 'collected').exists():
        raise ValueError('Slot is already assigned; each participant needs a fresh slot.')
    for path in (package / 'slots').glob('*/assignment.json'):
        if read_json(path)['participantCode'] == participant_code:
            raise ValueError('Participant code is already assigned to another slot.')
    binding = record['baselineEnvelope']
    path = package / binding['path']
    if file_binding(managed(path, slot / 'workspace'), package) != binding:
        raise ValueError('Slot Canvas is no longer the pristine frozen baseline.')
    for group in ('exports', 'projects', 'transactions'):
        directory = slot / 'workspace' / group
        if directory.exists() and any(directory.iterdir()):
            raise ValueError('Slot workspace already contains prior trial artifacts.')
    result = {'schemaVersion': 1, 'protocol': PROTOCOL, 'slotId': slot_id,
        'participantCode': participant_code, 'participantKind': kind, 'assignedAt': now(),
        'identityVerification': 'operator-supplied-pending-review',
        'packageManifestDigest': sha(package_manifest_raw),
        'pristineBaselineEnvelope': binding, 'taskTimerStarted': False}
    with (slot / 'assignment.json').open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def collect(package: Path, slot_id: str, participant_code: str, study_path: Path,
            export_ids: list[str], screenshots: dict[str, Path]) -> dict:
    package = package.resolve()
    manifest = checked_package(package)
    package_manifest_raw = regular(package / 'manifest.json').read_bytes()
    if object_value(json.loads(package_manifest_raw), 'package manifest') != manifest:
        raise ValueError('Package manifest changed during verification.')
    slots = [slot for slot in manifest['slots'] if slot['slotId'] == slot_id]
    if len(slots) != 1 or not CODE.fullmatch(participant_code):
        raise ValueError('Use an existing unassigned slot and an exact valid participant code.')
    slot_record = slots[0]
    slot = package / 'slots' / slot_id
    assignment_raw = regular(slot / 'assignment.json').read_bytes()
    assignment = object_value(json.loads(assignment_raw), 'assignment')
    if (assignment.get('protocol') != PROTOCOL or assignment.get('slotId') != slot_id
            or assignment.get('participantCode') != participant_code
            or assignment.get('packageManifestDigest') != sha(package_manifest_raw)
            or assignment.get('pristineBaselineEnvelope') != slot_record['baselineEnvelope']):
        raise ValueError('Participant assignment does not bind this slot to its pristine baseline.')
    if (slot / 'collected').exists():
        raise ValueError('Slot already collected; do not overwrite a participant bundle.')
    for previous in (package / 'slots').glob('*/collected/manifest.json'):
        if read_json(previous)['participantCode'] == participant_code:
            raise ValueError('Participant code already collected in another slot.')
    study_raw = regular(study_path).read_bytes()
    study = object_value(json.loads(study_raw), 'study')
    if study.get('schemaVersion') != 1 or study.get('protocol') != 'archcanvas-m4-research-task/1':
        raise ValueError('Unsupported task record.')
    if study.get('participantCode') != participant_code or study.get('participantKind') not in ('researcher', 'automation'):
        raise ValueError('Task participant binding differs from the explicitly selected code/type.')
    if study['participantKind'] != assignment.get('participantKind'):
        raise ValueError('Task participant type differs from the pristine slot assignment.')
    duration = validate_task(study, 'study')
    baseline = manifest['baseline']
    baseline_canvas_raw = regular(package / 'baseline/canvas.json').read_bytes()
    initial = object_value(json.loads(baseline_canvas_raw), 'baseline CanvasDocument')
    if canonical(initial) != baseline['canvasCanonicalDigest']:
        raise ValueError('Baseline Canvas changed during collection.')
    document_path = slot / 'workspace/documents' / f"{baseline['documentId']}.json"
    storage_raw = managed(document_path, slot / 'workspace').read_bytes()
    envelope = object_value(json.loads(storage_raw), 'storage envelope')
    document = object_value(envelope.get('document'), 'stored CanvasDocument')
    if type(envelope.get('revision')) is not int or envelope['revision'] < slot_record['baselineStorageRevision']:
        raise ValueError('Invalid current storage revision.')
    if (document.get('id') != baseline['documentId'] or document.get('sourceBindingDigest') != baseline['sourceDigest']
            or document.get('architecture') != read_json(package / 'baseline/architecture.json')):
        raise ValueError('Final Canvas source/IR/document binding differs from the frozen baseline.')
    if type(document.get('revision')) is not int or document['revision'] < 0:
        raise ValueError('Invalid final Canvas visual revision.')
    for checkpoint in study['checkpoints']:
        observation = checkpoint['observation']
        if (observation.get('documentId') != document['id'] or observation['sourceDigest'] != baseline['sourceDigest']
                or observation['irDigest'] != baseline['irDigest'] or int(observation['visualRevision']) > document['revision']):
            raise ValueError('Checkpoint document/source/IR/revision binding mismatch.')
    if study['checkpoints'] and int(study['checkpoints'][-1]['observation']['visualRevision']) != document['revision']:
        raise ValueError('Last checkpoint revision does not match the final saved Canvas.')
    if 'start' not in screenshots or 'final' not in screenshots or any(not SHOT.fullmatch(label) for label in screenshots):
        raise ValueError('Include actual start/final screenshots and supported evidence labels.')
    if len(export_ids) != len(set(export_ids)) or any(not IDENTITY.fullmatch(identity) for identity in export_ids):
        raise ValueError('Export identities must be distinct registered local artifact ids.')
    if study['outcome'] == 'completed' and not export_ids:
        raise ValueError('Completed self reports require an actual SVG/PDF export from this slot.')
    exports = []
    for identity in export_ids:
        directory = slot / 'workspace/exports' / identity
        export_input_raw = managed(directory / 'document.json', slot / 'workspace').read_bytes()
        saved = object_value(json.loads(export_input_raw), 'export input')
        if canonical(saved) != canonical(document):
            raise ValueError('Export input differs from the exact final saved CanvasDocument.')
        receipts = list(directory.glob('figure.*.receipt.json'))
        if len(receipts) != 1:
            raise ValueError('Expected exactly one actual export receipt.')
        receipt_path = managed(receipts[0], slot / 'workspace')
        receipt_raw = receipt_path.read_bytes()
        receipt = object_value(json.loads(receipt_raw), 'export receipt')
        format = receipt.get('format')
        if format not in ('svg', 'pdf'):
            raise ValueError('Research tasks require an actual SVG or PDF artifact.')
        figure = managed(directory / f'figure.{format}', slot / 'workspace')
        if (receipt.get('documentId') != document['id'] or receipt.get('revision') != document['revision']
                or receipt.get('sourceDigest') != baseline['sourceDigest'] or receipt.get('irDigest') != baseline['irDigest']):
            raise ValueError('Export receipt source/IR/document/revision binding mismatch.')
        raw = figure.read_bytes()
        if receipt.get('outputDigest') != sha(raw) or receipt.get('bytes') != len(raw):
            raise ValueError('Export output hash/size differs from the actual artifact.')
        if (format == 'svg' and b'<svg' not in raw[:1500]) or (format == 'pdf' and not raw.startswith(b'%PDF-')):
            raise ValueError('Actual export does not have its declared SVG/PDF signature.')
        exports.append({'id': identity, 'receipt': receipt, 'files': {
            figure.name: raw, receipt_path.name: receipt_raw, 'document.json': export_input_raw}})
    shot_snapshots = []
    for label, path in screenshots.items():
        raw = regular(path).read_bytes()
        if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff') or (raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')):
            raise ValueError('Screenshot must be an actual PNG, JPEG or WebP file.')
        suffix = '.png' if raw.startswith(b'\x89PNG') else '.jpg' if raw.startswith(b'\xff\xd8') else '.webp'
        shot_snapshots.append((label, suffix, raw))
    environment_path = package / 'environment.json'
    environment_raw = regular(environment_path).read_bytes() if environment_path.exists() else None
    if environment_raw is not None:
        object_value(json.loads(environment_raw), 'operator environment')
    review_template_raw = regular(slot / 'review-template.json').read_bytes()
    temporary = Path(tempfile.mkdtemp(prefix='.research-collect-', dir=slot))
    try:
        verification = temporary / 'verify-input.json'
        write_json(verification, {'document': document, 'receipts': [item['receipt'] for item in exports]})
        core('verify', verification, temporary / 'scene-verification.json')
        verification.unlink()
        scene_verification = read_json(temporary / 'scene-verification.json')
        if len(scene_verification['scenes']) != len(exports):
            raise ValueError('Formal core returned a different export count.')
        for export, expected in zip(exports, scene_verification['scenes']):
            receipt = export['receipt']
            if receipt['format'] == 'svg':
                # The publisher normalizes XML and physical dimensions. Its
                # output bytes differ from renderSvg, so compare the actual
                # authoritative normalization rather than equating two hashes.
                regenerated = export_svg(expected.pop('sceneSvg'), format='svg', width_mm=receipt['widthMm'], dpi=receipt['dpi'])['data']
                if regenerated != export['files']['figure.svg'] or sha(regenerated) != receipt.get('svgDigest'):
                    raise ValueError('Actual SVG differs from independently regenerated published SVG.')
                expected['publishedSvgDigest'] = sha(regenerated)
                expected['publishedSvgBytesIndependentlyMatched'] = True
        write_json(temporary / 'scene-verification.json', scene_verification)
        (temporary / 'task.json').write_bytes(study_raw)
        (temporary / 'final-storage.json').write_bytes(storage_raw)
        (temporary / 'baseline.canvas.json').write_bytes(baseline_canvas_raw)
        (temporary / 'assignment.json').write_bytes(assignment_raw)
        if environment_raw is not None:
            (temporary / 'environment.json').write_bytes(environment_raw)
        write_json(temporary / 'final.canvas.json', document)
        artifact_records = []
        for export in exports:
            identity, receipt = export['id'], export['receipt']
            target = temporary / 'exports' / identity
            target.mkdir(parents=True)
            for name, raw in export['files'].items():
                (target / name).write_bytes(raw)
            artifact_records.append({'artifactId': identity, 'format': receipt['format'],
                'documentId': document['id'], 'visualRevision': document['revision'],
                'inputCanvasCanonicalDigest': canonical(document),
                'files': [file_binding(path, temporary) for path in sorted(target.iterdir())]})
        shot_records = []
        (temporary / 'screenshots').mkdir()
        for label, suffix, raw in shot_snapshots:
            target = temporary / 'screenshots' / f'{label}{suffix}'
            target.write_bytes(raw)
            shot_records.append({'label': label, 'contentReview': 'pending', **file_binding(target, temporary)})
        fields = ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems', 'annotations', 'layout', 'pinnedObjects', 'expandedIds', 'pageSpec')
        result = {'schemaVersion': 1, 'protocol': PROTOCOL, 'collectedAt': now(), 'slotId': slot_id,
            'participantCode': participant_code, 'participantKind': study['participantKind'],
            'reviewStatus': 'self-report-pending-independent-review', 'researchGate': 'awaiting-independent-review' if study['participantKind'] == 'researcher' else 'not_run',
            'includedInSelfReportedResearcherDenominator': study['participantKind'] == 'researcher', 'humanSuccessCertified': False,
            'packageManifestDigest': sha(package_manifest_raw),
            'assignment': file_binding(temporary / 'assignment.json', temporary),
            'baseline': {key: baseline[key] for key in ('documentId', 'sourceDigest', 'irDigest', 'canvasCanonicalDigest')},
            'final': {'documentId': document['id'], 'visualRevision': document['revision'], 'storageRevision': envelope['revision'],
                      'canvasCanonicalDigest': canonical(document)},
            'selfReportedOutcome': study['outcome'], 'durationMs': duration,
            'changedVisualFields': [field for field in fields if initial[field] != document[field]],
            'taskFile': file_binding(temporary / 'task.json', temporary),
            'canvasFiles': [file_binding(temporary / name, temporary) for name in ('baseline.canvas.json', 'final.canvas.json', 'final-storage.json')],
            'sceneVerification': file_binding(temporary / 'scene-verification.json', temporary),
            'operatorEnvironment': file_binding(temporary / 'environment.json', temporary) if environment_raw is not None else None,
            'exports': artifact_records, 'screenshots': shot_records, 'reviewer': None,
            'limitations': ['Participant type/identity and completion remain operator-supplied self reports.',
                'Screenshot hashes do not prove capture time or content; independently inspect each image.',
                'PDF bytes are checked against a local editable receipt, not independently reconverted.',
                'Changed visual fields do not establish undo/redo, saved reload or publication readability.',
                'Automation never certifies the real researcher gate.']}
        write_json(temporary / 'manifest.json', result)
        (temporary / 'review-template.json').write_bytes(review_template_raw)
        temporary.rename(slot / 'collected')
        return result
    except Exception:
        shutil.rmtree(temporary)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preparation = commands.add_parser('prepare')
    preparation.add_argument('--output', required=True, type=Path)
    preparation.add_argument('--slots', type=int, default=5)
    preparation.add_argument('--first-port', type=int, default=8871)
    verification = commands.add_parser('verify')
    verification.add_argument('--package', required=True, type=Path)
    assignment = commands.add_parser('assign')
    assignment.add_argument('--package', required=True, type=Path)
    assignment.add_argument('--slot', required=True)
    assignment.add_argument('--participant-code', required=True)
    assignment.add_argument('--kind', choices=('researcher', 'automation'), required=True)
    collection = commands.add_parser('collect')
    collection.add_argument('--package', required=True, type=Path)
    collection.add_argument('--slot', required=True)
    collection.add_argument('--participant-code', required=True)
    collection.add_argument('--study', required=True, type=Path)
    collection.add_argument('--export-id', action='append', default=[])
    collection.add_argument('--screenshot', action='append', default=[], metavar='LABEL=PATH')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.output, args.slots, args.first_port)
        elif args.command == 'verify':
            manifest = checked_package(args.package.resolve())
            result = {'protocol': PROTOCOL, 'baselineAndImplementationUnchanged': True,
                      'preparationState': manifest['state'],
                      'verificationScope': 'frozen-baseline-and-implementation-only', 'researchGate': 'not_evaluated'}
        elif args.command == 'assign':
            result = assign(args.package, args.slot, args.participant_code, args.kind)
        else:
            screenshots = {}
            for value in args.screenshot:
                label, separator, path = value.partition('=')
                if not separator or not path or label in screenshots:
                    raise ValueError('Screenshots require distinct LABEL=PATH arguments.')
                screenshots[label] = Path(path)
            result = collect(args.package, args.slot, args.participant_code, args.study, args.export_id, screenshots)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
