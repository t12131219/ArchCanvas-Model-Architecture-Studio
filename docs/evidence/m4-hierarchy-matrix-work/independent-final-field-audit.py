#!/usr/bin/env python3
"""Independent frozen-byte audit of 39 actual hierarchy-build capture inputs.

No browser operations, hash stamping, formal collection, or input modifications.
The sole reconstruction is a fresh formal-core call in a temporary directory.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
MATRIX = ROOT / 'docs/evidence/browser-visual-matrix-hierarchy-final'
SPEC_DIR = ROOT / '.archcanvas/browser-visual-matrix-hierarchy-final'
STORE = ROOT / '.archcanvas/m4-hierarchy-matrix/documents'
sys.path.insert(0, str(ROOT / 'src'))
from archcanvas_python import analyze_project
from archcanvas_publication import export_svg
from PIL import Image

FIELDS = ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems',
          'annotations', 'layout', 'pinnedObjects', 'title', 'pageSpec')
FILE_NAMES = {'canvas': 'canvas.json', 'svg': 'figure.svg', 'exportReceipt': 'export-receipt.json',
              'screenshot': 'screenshot.jpg', 'browserScene': 'browser-scene.svg', 'screenReceipt': 'screen-receipt.json'}
REVISION_FIELDS = ('data-revision', 'metadata.revision')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())


def xml_tree(raw: bytes, *, ignore_revision: bool = False):
    if len(raw) > 8_000_000 or re.search(rb'<!\s*(?:DOCTYPE|ENTITY)|<\?', raw, re.I):
        raise ValueError('Unsafe/oversized SVG XML.')
    root = ET.fromstring(raw)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Actual SVG root required.')
    metadata = root.find('{http://www.w3.org/2000/svg}metadata')
    if ignore_revision:
        assert metadata is not None and 'data-revision' in root.attrib
        values = json.loads(metadata.text)
        assert root.attrib['data-revision'] == str(values['revision'])
        root.attrib['data-revision'] = '__ACTUAL_REVISION__'
        values['revision'] = '__ACTUAL_REVISION__'
        metadata.text = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    def element(node):
        return [node.tag, sorted(node.attrib.items()), node.text or '', node.tail or '', [element(child) for child in node]]
    return element(root)


def semantic(raw: bytes) -> str:
    return canonical(xml_tree(raw))


def scene_metadata(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    return json.loads(root.find('{http://www.w3.org/2000/svg}metadata').text)


class Frozen:
    def __init__(self):
        self.bytes = {}

    def read(self, path: Path) -> bytes:
        path = path.absolute()
        if path not in self.bytes:
            current = path
            while current != current.parent:
                if current.is_symlink():
                    raise ValueError(f'Symlink evidence input: {path}')
                current = current.parent
            if not path.is_file():
                raise ValueError(f'Missing audit input: {path}')
            self.bytes[path] = path.read_bytes()
        return self.bytes[path]

    def json(self, path: Path):
        return json.loads(self.read(path))

    def binding(self, path: Path) -> dict:
        path = path.absolute()
        raw = self.read(path)
        return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                'sha256': sha(raw), 'bytes': len(raw)}

    def recheck(self):
        changed = []
        for path, raw in self.bytes.items():
            if not path.is_file() or path.read_bytes() != raw:
                changed.append(str(path))
        return changed


def audit() -> dict:
    frozen = Frozen()
    frozen.read(Path(__file__))
    spec_raw = frozen.read(SPEC_DIR / 'spec.json')
    spec = json.loads(spec_raw)
    manifest_raw = frozen.read(MATRIX / 'manifest.json')
    manifest = json.loads(manifest_raw)
    captures = frozen.json(WORK / 'captures.json')['captures']
    failures, checks = [], {}
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            failures.append(name)

    check('matrix_count_and_pending_acceptance', manifest['capturedBaselineCount'] == 36
          and len(manifest['captures']) == 39 and len(captures) == 39
          and manifest['missingBaselineVariants'] == [] and manifest['editedAfterModelsMissing'] == []
          and manifest['humanAcceptanceCertified'] is False
          and manifest['visualAcceptance'] == 'pending-human-review')
    check('spec_exact', manifest['specDigest'] == sha(spec_raw))
    # Freeze both all declared input bytes and evidence of unselected/error attempts.
    for directory in ('raw', 'cases', 'excluded', 'edited-journal', 'helper-cli-results', 'stamp-cli-results'):
        for path in sorted((WORK / directory).rglob('*')):
            if path.is_file():
                frozen.read(path)
    for name in ('copy-unprepared.py', 'visibility-attempt.json', 'first-pdf-observation.json',
                 'service-raw.txt', 'matrix-collect-process.json', 'matrix-collect.stderr.txt', 'matrix-collect.stdout.txt'):
        if (WORK / name).exists():
            frozen.read(WORK / name)
    check('collect_process_exit0', frozen.json(WORK / 'matrix-collect-process.json')['exitCode'] == 0)
    check('collect_receipt_exact', frozen.json(WORK / 'matrix-collect.stdout.txt') == manifest
          and frozen.read(WORK / 'matrix-collect.stderr.txt') == b'')
    for field, parent in (('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'),
                          ('coreFiles', Path(spec['coreDirectory']))):
        check('frozen_' + field, all(frozen.binding(parent / item['path'])['sha256'] == item['sha256']
              and len(frozen.read(parent / item['path'])) == item['bytes'] for item in spec[field]))
    check('core_report_exact', sha(frozen.read(Path(spec['coreDirectory']) / 'visual-gold-report.json')) == spec['coreReportDigest'])
    for path in (ROOT / 'studio/src/core').glob('*.ts'):
        frozen.read(path)
    for package in ('archcanvas_python', 'archcanvas_publication'):
        for path in (ROOT / 'src' / package).glob('*.py'):
            frozen.read(path)
    for path in (ROOT / 'scripts/browser_visual_core.mjs', ROOT / 'scripts/browser_visual_matrix.py',
                 ROOT / 'scripts/prepare_hierarchy_matrix_capture.py'):
        frozen.read(path)
    variants = {item['variantId']: item for item in spec['variants']}
    stored_architectures = {}
    for fixture in ('mlp', 'residual_cnn', 'transformer'):
        expected = frozen.json(Path(spec['coreDirectory']) / (fixture + '.architecture.json'))
        for source in expected['sources']:
            source_bytes = frozen.read(ROOT / 'fixtures' / fixture / source['path'])
            check('source_bytes_' + fixture + '_' + source['path'], sha(source_bytes) == source['digest']
                  and source_bytes.decode('utf-8-sig') == source['content'])
        actual = analyze_project(ROOT / 'fixtures' / fixture, expected['entry'])
        check('fresh_source_analysis_' + fixture, actual == expected)
        stored_architectures[fixture] = actual

    case_results, documents, sealed_count = [], [], 0
    baselines_seen, edits_seen, cases_seen, historical_live_bindings = set(), set(), set(), []
    sealed_by_case = {item['caseId']: item for item in manifest['captures']}
    for record in captures:
        case_id, variant_id, state = record['caseId'], record['variantId'], record['state']
        case_dir, raw_dir = WORK / 'cases' / case_id, WORK / 'raw' / case_id
        variant = variants[variant_id]
        helper = frozen.json(case_dir / 'case-helper.json')
        raw = frozen.json(case_dir / 'dom-observation.json')
        screen = frozen.json(case_dir / 'screen-receipt.json')
        unstamped = frozen.json(case_dir / 'screen-receipt-unstamped.json')
        document = frozen.json(case_dir / 'canvas.json')
        stored = frozen.json(case_dir / 'actual-document-store.json')
        receipt = frozen.json(case_dir / 'export-receipt.json')
        scene_bytes, figure_bytes = frozen.read(case_dir / 'browser-scene.svg'), frozen.read(case_dir / 'figure.svg')
        shot_bytes = frozen.read(case_dir / 'screenshot.jpg')
        sealed = sealed_by_case[case_id]
        scoped = {}
        def case_check(name, value):
            scoped[name] = bool(value)
            check(case_id + ':' + name, value)

        case_check('unique_case_and_variant', case_id not in cases_seen and variant_id in variants
                   and (state != 'baseline' or variant_id not in baselines_seen))
        cases_seen.add(case_id)
        if state == 'baseline':
            baselines_seen.add(variant_id)
        else:
            edits_seen.add(variant['fixture'])
        case_check('helper_case_mapping', (helper['caseId'], helper['variantId'], helper['state']) == (case_id, variant_id, state)
                   and helper['matrixSpecDigest'] == sha(spec_raw) and helper['replacementExportSearch'] == 'not-attempted')
        case_check('copied_input_bindings', all(frozen.binding(case_dir / item['path'])['sha256'] == item['sha256']
                   and len(frozen.read(case_dir / item['path'])) == item['bytes'] for item in helper['copiedFiles']))
        all_bindings, live_bindings = True, []
        for item in helper['inputBindings']:
            path = Path(item['path'])
            if path.parent == STORE:
                # The original live store slot is deliberately overwritten by later captures.
                # The copy still binds the capture-time bytes and their full envelope.
                live_bindings.append(item)
                historical_live_bindings.append({'caseId': case_id, **item,
                    'retainedCaptureSnapshot': str((case_dir / 'actual-document-store.json').relative_to(ROOT)),
                    'retainedBytesMatch': sha(frozen.read(case_dir / 'actual-document-store.json')) == item['sha256']})
                all_bindings = all_bindings and sha(frozen.read(case_dir / 'actual-document-store.json')) == item['sha256']
            else:
                value = frozen.read(path)
                all_bindings = all_bindings and sha(value) == item['sha256'] and len(value) == item['bytes']
        case_check('all_helper_input_byte_bindings', all_bindings)
        case_check('raw_copy_exact', frozen.read(raw_dir / 'dom-observation.json') == frozen.read(case_dir / 'dom-observation.json')
                   and frozen.read(raw_dir / 'browser-scene.svg') == scene_bytes and frozen.read(raw_dir / 'screenshot.jpg') == shot_bytes)
        case_check('full_store_export_canvas_equality', stored['document'] == document and type(stored['revision']) is int and stored['revision'] >= 1)
        source_binding = {'documentId': document['id'], 'revision': document['revision'],
                          'sourceDigest': document['architecture']['sourceDigest'], 'irDigest': document['architecture']['irDigest']}
        case_check('source_spec_and_DOM_metadata', document['architecture'] == stored_architectures[variant['fixture']]
                   and source_binding == raw['documentBinding'] == screen['documentBinding'] == sealed['documentBinding']
                   and scene_metadata(scene_bytes)['revision'] == document['revision']
                   and scene_metadata(scene_bytes)['sourceDigest'] == variant['sourceDigest']
                   and scene_metadata(scene_bytes)['irDigest'] == variant['irDigest'])
        expected_page = {'widthMm': variant['widthMm'], 'preset': variant['preset']}
        case_check('complete_page_frontier', screen['pageSpec'] == raw['pageSpec'] == sealed['pageSpec'] == expected_page
                   and sorted(document['expandedIds']) == sorted(raw['expandedIds']) == sorted(screen['expandedIds'])
                   == sorted(variant['expandedIds']) == sorted(sealed['expandedIds']))
        baseline = frozen.json(Path(variant['canvasFile']))
        changed = [field for field in FIELDS if document.get(field) != baseline.get(field)]
        case_check('baseline_or_edited_classification', changed == helper['changedVisualFields'] == sealed['changedVisualFields']
                   and ((state == 'baseline' and all(field == 'layout' for field in changed)) or (state == 'edited' and bool(changed))))
        parsed_export = urlsplit(raw['actualExport']['observedUrl'])
        identity = re.fullmatch(r'/api/exports/([a-f0-9]{32})/figure\.svg', parsed_export.path).group(1)
        original_dir = STORE.parent / 'exports' / identity
        case_check('exact_observed_export_id', identity == helper['exactExportArtifactId'] == screen['actualExport']['serviceArtifactId']
                   and screen['actualExport']['observedUrl'] == raw['actualExport']['observedUrl'])
        case_check('original_export_bytes', frozen.read(original_dir / 'document.json') == frozen.read(case_dir / 'canvas.json')
                   and frozen.read(original_dir / 'figure.svg') == figure_bytes
                   and frozen.read(original_dir / 'figure.svg.receipt.json') == frozen.read(case_dir / 'export-receipt.json'))
        snapshot_mode = helper.get('savedEnvelopeObservation', {}).get('kind') == 'operator-document-store-snapshot'
        if snapshot_mode:
            observed_copy = raw['actualStoredEnvelope']
            receipt_bytes = frozen.read(case_dir / 'actual-document-store-snapshot-receipt.json')
            snapshot_bytes = frozen.read(Path(observed_copy['snapshotPath']))
            case_check('operator_snapshot_paths_time_bytes', observed_copy == json.loads(receipt_bytes)
                       == frozen.json(Path(observed_copy['snapshotPath'] + '.receipt.json'))
                       and Path(observed_copy['observedSourcePath']).resolve() == (STORE / (document['id'] + '.json')).resolve()
                       and snapshot_bytes == frozen.read(case_dir / 'actual-document-store.json')
                       and sha(snapshot_bytes) == observed_copy['sha256'] and len(snapshot_bytes) == observed_copy['bytes']
                       and datetime.fromisoformat(observed_copy['copiedAt'].replace('Z', '+00:00')).utcoffset() is not None)
        else:
            case_check('live_capture_retained_byte_binding', len(live_bindings) == 1)
        changed_screen = [key for key in set(screen) | set(unstamped) if screen.get(key) != unstamped.get(key)]
        case_check('stamp_only_two_hash_fields', sorted(changed_screen) == ['browserSceneDigest', 'screenshotDigest']
                   and unstamped['screenshotDigest'] is None and unstamped['browserSceneDigest'] is None
                   and screen['screenshotDigest'] == sha(shot_bytes) and screen['browserSceneDigest'] == semantic(scene_bytes))
        provenance = raw['environmentProvenance']
        previous_raw = frozen.read(Path(provenance['path']))
        previous = json.loads(previous_raw)
        case_check('prior_UA_DPR_explicit_exact', sha(previous_raw) == provenance['sha256']
                   and screen['environment']['userAgent'] == raw['environment']['userAgent'] == previous['environment']['userAgent']
                   and screen['environment']['devicePixelRatio'] == raw['environment']['devicePixelRatio'] == previous['environment']['viewport']['devicePixelRatio']
                   and any(provenance['sha256'] in text and 'not current DOM' in text for text in screen['limitations']))
        case_check('current_environment_facts_unchanged', screen['environment'] == raw['environment']
                   and screen['camera'] == raw['camera'] and screen['capturedAt'] == raw['capturedAt']
                   and screen['environment']['hardware'] is None and screen['environment']['fontEvidence'] == [])
        image = Image.open(io.BytesIO(shot_bytes))
        # This is merely JPEG decoding and dimensions, not native provenance or fine-pixel review.
        image_size = {'width': image.width, 'height': image.height}
        expected_assets = {item['path']: item['sha256'] for item in spec['buildFiles'] if item['path'].endswith(('.js', '.css'))}
        case_check('observed_loaded_assets_bound', {item['path']: item['sha256'] for item in screen['loadedBuildAssets']} == expected_assets
                   and [{'path': item['path'], 'url': item['url']} for item in screen['loadedBuildAssets']] == raw['loadedBuildAssets'])
        case_check('actual_svg_receipt_binding', all(receipt.get(key) == value for key, value in source_binding.items())
                   and receipt['outputDigest'] == sha(figure_bytes) and receipt['bytes'] == len(figure_bytes)
                   and receipt['widthMm'] == variant['widthMm'] and receipt['exportScope'] == {'kind': 'document'})
        six_equal = True
        for field, name in FILE_NAMES.items():
            sealed_entry = sealed['files'][field]
            sealed_bytes = frozen.read(MATRIX / sealed_entry['path'])
            six_equal = six_equal and sealed_bytes == frozen.read(case_dir / name)
            six_equal = six_equal and sha(sealed_bytes) == sealed_entry['sha256'] and len(sealed_bytes) == sealed_entry['bytes']
            six_equal = six_equal and (WORK / record[field]).resolve() == (case_dir / name).resolve()
            sealed_count += 1
        case_check('six_collected_files_exact_with_work', six_equal)
        documents.append({'document': document})
        case_results.append({'caseId': case_id, 'variantId': variant_id, 'state': state, 'fixture': variant['fixture'],
            'documentRevision': document['revision'], 'storageRevision': stored['revision'],
            'savedEnvelopeMode': 'operator snapshot' if snapshot_mode else 'retained original live-store copy',
            'originalArtifactId': identity, 'changedVisualFields': changed, 'checks': scoped,
            'screenshotPixels': image_size, 'observedViewport': screen['environment']['viewport'],
            'imageDimensionsAreNativeGeometryProof': False})
    check('all36_unique_baselines_and_three_edits', len(baselines_seen) == 36
          and len(edits_seen) == 3 and set(sealed_by_case) == cases_seen and sealed_count == 234)

    with tempfile.TemporaryDirectory(prefix='archcanvas-final-matrix-independent-') as directory:
        directory = Path(directory)
        (directory / 'input.json').write_text(json.dumps(documents, ensure_ascii=False, allow_nan=False))
        completed = subprocess.run(['node', str(ROOT / 'scripts/browser_visual_core.mjs'),
                                   str(directory / 'input.json'), str(directory / 'expected')],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120)
        check('fresh39_core_reconstruction_exit0', completed.returncode == 0)
        if completed.returncode:
            raise ValueError('Fresh formal-core reconstruction failed: ' + completed.stderr)
        core_facts = json.loads((directory / 'expected/facts.json').read_bytes())
        for index, item in enumerate(case_results):
            case = WORK / 'cases' / item['caseId']
            expected_dom = (directory / 'expected' / f'{index}.interactive.svg').read_bytes()
            expected_publication = (directory / 'expected' / f'{index}.publication.svg').read_bytes()
            receipt = frozen.json(case / 'export-receipt.json')
            normalized = export_svg(expected_publication.decode(), format='svg',
                                    width_mm=core_facts[index]['pageSpec']['widthMm'], dpi=receipt['dpi'])['data']
            scoped = {'fresh_full_DOM_equal': semantic(expected_dom) == semantic(frozen.read(case / 'browser-scene.svg')),
                'fresh_complete_scene_input_equal': sha(expected_publication) == receipt['sceneSvgDigest'] == receipt['inputSvgDigest'],
                'fresh_publication_bytes_equal': normalized == frozen.read(case / 'figure.svg') and sha(normalized) == receipt['svgDigest']}
            for name, value in scoped.items():
                check(item['caseId'] + ':' + name, value)
            item['freshCoreChecks'] = scoped
            item['freshCoreFacts'] = core_facts[index]

    journals = {path.stem: frozen.json(path) for path in sorted((WORK / 'edited-journal').glob('*.json'))}
    journal_results = []
    def compare_journal(first, second, ignore_revision=False):
        left, right = journals[first]['svg'].encode(), journals[second]['svg'].encode()
        return {'first': first, 'second': second,
                'firstRevision': journals[first]['metadata']['revision'], 'secondRevision': journals[second]['metadata']['revision'],
                'scope': 'complete XML, only actual root data-revision and metadata.revision normalized' if ignore_revision else 'complete SVG bytes, including revision',
                'exact': xml_tree(left, ignore_revision=True) == xml_tree(right, ignore_revision=True) if ignore_revision else left == right}
    for fixture in ('mlp', 'transformer', 'residual_cnn'):
        checks_for_model = [compare_journal(fixture + '-added', fixture + '-undo', True),
                            compare_journal(fixture + '-text-edited', fixture + '-redo', True)]
        if fixture == 'residual_cnn':
            checks_for_model.extend([compare_journal('residual_cnn-reposition-before', 'residual_cnn-reposition-undo', True),
                                     compare_journal('residual_cnn-reposition-after', 'residual_cnn-reposition-redo', True),
                                     compare_journal('residual_cnn-saved-repositioned', 'residual_cnn-reopened-repositioned')])
            final_stage = 'residual_cnn-reopened-repositioned'
        else:
            checks_for_model.append(compare_journal(fixture + '-saved', fixture + '-reopened'))
            final_stage = fixture + '-reopened'
        for comparison in checks_for_model:
            check('journal:' + comparison['first'] + ':' + comparison['second'], comparison['exact'])
        final_case = next(item for item in case_results if item['fixture'] == fixture and item['state'] == 'edited')
        final_svg = frozen.read(WORK / 'cases' / final_case['caseId'] / 'browser-scene.svg')
        check('journal:' + fixture + ':final_reopened_equals_collected', journals[final_stage]['svg'].encode() == final_svg)
        expected_fact_list = scene_metadata(final_svg)['sourceFacts']
        source_facts_equal = all(value['metadata']['sourceDigest'] == stored_architectures[fixture]['sourceDigest']
            and value['metadata']['irDigest'] == stored_architectures[fixture]['irDigest']
            and value['metadata']['sourceFacts'] == expected_fact_list
            and scene_metadata(value['svg'].encode()) == value['metadata']
            for name, value in journals.items() if name.startswith(fixture + '-'))
        check('journal:' + fixture + ':all_source_IR_facts_exact', source_facts_equal)
        journal_results.append({'fixture': fixture, 'fullSvgComparisons': checks_for_model,
            'finalStage': final_stage, 'finalCase': final_case['caseId'],
            'allJournalSourceIRFactsExact': source_facts_equal,
            'finalVisualRevision': final_case['documentRevision'], 'finalStorageRevision': final_case['storageRevision'],
            'historyPersisted': 'not claimed; save/reopen verifies SVG and saved envelope, not history persistence'})
    moved = compare_journal('residual_cnn-text-edited', 'residual_cnn-moved')
    check('journal:CNN_rev30_moved_is_exact_same_SVG_no_committed_move', moved['exact'] and moved['firstRevision'] == moved['secondRevision'] == 30)
    prior_saved_reopened = compare_journal('residual_cnn-saved-final', 'residual_cnn-reopened')
    check('journal:CNN_prior_rev40_save_reopen_exact_retained', prior_saved_reopened['exact'])
    before = journals['residual_cnn-reposition-before']['svg'].encode()
    after = journals['residual_cnn-reposition-after']['svg'].encode()
    def annotation_texts(raw):
        return [{'id': group.attrib['data-annotation-id'], 'texts': [{'x': text.attrib.get('x'), 'y': text.attrib.get('y'),
                    'text': ''.join(text.itertext())} for text in group.iter('{http://www.w3.org/2000/svg}text')]}
                for group in ET.fromstring(raw).iter() if 'data-annotation-id' in group.attrib]
    retained_attempts = {'visibilityAttempt': frozen.json(WORK / 'visibility-attempt.json'),
        'firstPdfObservation': frozen.json(WORK / 'first-pdf-observation.json'),
        'CNN_rev30Moved': {**moved, 'claim': 'No committed move proven; name alone does not establish a move.'},
        'CNN_prior_rev34_saved_retained': {'revision': journals['residual_cnn-saved']['metadata']['revision'],
            'expandedIds': journals['residual_cnn-saved']['expandedIds'],
            'annotations': annotation_texts(journals['residual_cnn-saved']['svg'].encode())},
        'CNN_prior_rev40_saved_reopened': prior_saved_reopened,
        'CNN_reposition': {'before': annotation_texts(before), 'after': annotation_texts(after),
            'beforeRevision': 40, 'afterRevision': 41, 'finalSavedReopenedRevision': 45,
            'scope': 'Only observed text coordinates are reported; no inherited success claim for rev30 gesture.'},
        'excludedDirectoryFiles': [frozen.binding(path) for path in sorted((WORK / 'excluded').rglob('*')) if path.is_file()]}
    changed = frozen.recheck()
    check('all_input_bytes_unchanged_after_audit', changed == [])
    bindings = [frozen.binding(path) for path in sorted(frozen.bytes)]
    return {'schemaVersion': 1, 'protocol': 'archcanvas-hierarchy-matrix-independent-field-audit/1',
        'auditedAt': datetime.now(timezone.utc).isoformat(),
        'scope': 'Operator DOM/file consistency and fresh formal-core reconstruction of all39; no CUA/stamp/collect or input changes.',
        'allChecksPassed': not failures, 'checksPassed': sum(checks.values()), 'checksFailed': failures,
        'baselineCount': len(baselines_seen), 'editedCount': len(cases_seen) - len(baselines_seen),
        'collectedFilesExact': sealed_count, 'freshCoreDOMCount': len(case_results), 'freshPublicationCount': len(case_results),
        'matrixManifestDigest': sha(manifest_raw), 'matrixSpecDigest': sha(spec_raw),
        'cases': case_results, 'editedJournals': journal_results, 'retainedAttempts': retained_attempts,
        'historicalLiveStoreBindings': historical_live_bindings,
        'stableInputBindingCount': len(bindings), 'inputBindings': bindings, 'changedInputs': changed,
        'limitations': ['Operator DOM observations and snapshot metadata declarations do not independently certify native provenance.',
            'UA/DPR come from explicitly bound prior same-IAB native raw at8889, not current8896 DOM; viewport is current DOM.',
            '39 image dimensions are decoded, but screenshot pixel content/aesthetics were not independently reviewed by this field audit.',
            'Old live store capture bytes resolve through retained case envelopes; later live store slots legitimately contain newer revisions.',
            'Full figure readability, locked resolved font bytes/hardware, native cancellation and sustained presented performance remain unproven.',
            'Automation is not a human participant or publication acceptance.'],
        'humanAcceptanceCertified': False, 'humanParticipants': 0, 'performanceGateCertified': False,
        'resolvedFontBytesCertified': False, 'matrixVisualAcceptance': 'pending-human-review'}


def main() -> int:
    output = WORK / 'independent-final-field-audit.json'
    markdown = WORK / 'independent-final-field-audit.md'
    if output.exists() or markdown.exists():
        raise SystemExit('Refusing to replace a prior independent final audit.')
    result = audit()
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    lines = ['# Independent hierarchy matrix field audit', '',
        f"All checks passed: **{result['allChecksPassed']}**; {result['checksPassed']} checks. Inputs frozen before parse and rechecked after: {result['stableInputBindingCount']}.", '',
        '36 baseline + 3 edited cases; all 234 collected files equal their work inputs. Each exact observed export directory, saved envelope, raw DOM, receipt, loaded build URL and prior UA/DPR source is checked. Fresh formal core reconstructs all 39 complete DOM and publication outputs.', '',
        '| Edited model | Final visual revision | Storage revision | Final save/reopen evidence |', '|---|---:|---:|---|']
    for item in result['editedJournals']:
        lines.append(f"| {item['fixture']} | {item['finalVisualRevision']} | {item['finalStorageRevision']} | {item['finalStage']} ↔ {item['finalCase']} |")
    lines += ['', 'All three text edit undo/redo comparisons inspect the complete SVG XML and normalize only two actual revision scalars: root `data-revision` and `metadata.revision`. Final save/reopen comparisons require exact SVG bytes, including revision. Source/IR facts remain equal throughout all journals.', '',
        'CNN `moved` at revision30 is byte-identical to `text-edited`: it proves no additional committed move. Initial revision34 save, revision40 save/reopen, latent-frontier history, excluded pre-reposition artifacts and revision41 annotation reposition are retained. Final CNN evidence uses saved/reopened revision45 with annotation text y973 instead of prior y2549.', '',
        'The original first case used the live store. Its capture-time envelope bytes are retained and hash-checked; current live storage may legitimately hold later cases. Other cases use operator-copied snapshots whose source path, copy time, exact byte count/hash and sidecar/raw metadata are checked. These are operator declarations, not independent native provenance certification.', '',
        'UA/DPR explicitly resolve to prior same-IAB native raw at8889. Current viewport facts remain from8896 DOM; hardware and resolved font bytes remain unknown. This audit does not certify human participants, pixel aesthetics, physical print readability, cancellation or sustained presented performance.', '',
        'Machine audit: [independent-final-field-audit.json](independent-final-field-audit.json). Source: [independent-final-field-audit.py](independent-final-field-audit.py).']
    markdown.write_text('\n'.join(lines) + '\n')
    print(json.dumps({key: result[key] for key in ('allChecksPassed', 'checksPassed', 'checksFailed',
        'baselineCount', 'editedCount', 'collectedFilesExact', 'stableInputBindingCount', 'matrixManifestDigest')}, indent=2))
    return 0 if result['allChecksPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
