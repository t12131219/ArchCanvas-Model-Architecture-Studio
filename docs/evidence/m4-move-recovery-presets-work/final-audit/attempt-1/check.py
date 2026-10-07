#!/usr/bin/env python3
"""Independent read-only audit of the final ChS0wIgb evidence and byte seal.

No product tests, model execution, services or browser actions. --preview does
not write; --seal requires the existing final receipt and writes a new report
exclusively. The report is outside the seal chain to avoid a hash cycle.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[5]
WORK = ROOT / 'docs/evidence/m4-move-recovery-presets-work'
BROWSER = ROOT / 'docs/evidence/m4-move-recovery-presets-browser/final-ChS0wIgb'
ARCHIVE = ROOT / 'docs/evidence/before-m4-move-recovery-presets'
OUTPUT = Path(__file__).with_name('report.json')
OLD_SHA = '170be658b4b76e2217bb0d58397f586fc1f8fdccd66278961d657116952a5551'
JS_SHA = '05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9'


def path(value):
    result = Path(value)
    result = result if result.is_absolute() else ROOT / result
    assert result.is_relative_to(ROOT), str(result)
    assert result.is_file() and not result.is_symlink(), str(result)
    return result


def raw(value):
    return path(value).read_bytes()


def sha(value):
    return hashlib.sha256(raw(value)).hexdigest()


def load(value):
    return json.loads(raw(value))


def check_binding(item, base=ROOT):
    p = base / item['path']
    assert sha(p) == item['sha256'], str(p)
    if 'bytes' in item:
        assert len(raw(p)) == item['bytes'], str(p)


def archive():
    manifest = load(ARCHIVE / 'manifest.json')
    previous = load(ARCHIVE / 'previous-seal.json')
    assert manifest['previousSealSha256'] == OLD_SHA
    assert sha(ARCHIVE / 'previous-seal.json') == sha(manifest['previousSeal']) == OLD_SHA
    assert manifest['bindingCount'] == previous['bindingCount'] == len(manifest['bindings']) == len(previous['bindings']) == 2894
    old = {item['path']: (item['sha256'], item['bytes']) for item in previous['bindings']}
    assert len(old) == 2894 and set(old) == {row['path'] for row in manifest['bindings']}
    for item in manifest['bindings']:
        copied = raw(item['archivePath'])
        assert (hashlib.sha256(copied).hexdigest(), len(copied)) == old[item['path']] == (item['sha256'], item['bytes'])
    return {'oldBindings': 2894, 'oldSealSha256': OLD_SHA, 'allArchivedBytesExact': True,
            'newProductComparedToOldSeal': False}


def product():
    final = load(WORK / 'root/final-product-validation.json')
    assert final['studio']['passed'] == 152 and final['studio']['failed'] == final['studio']['skipped'] == final['studio']['exit'] == 0
    assert final['strictBuild']['exit'] == 0
    for key, value in final['sourceBindings'].items():
        assert sha(key) == value, key
    for row in final['assets']:
        check_binding(row)
    assert sha('studio/dist/assets/index-ChS0wIgb.js') == JS_SHA
    log = raw(WORK / 'root/studio-full-final.log').decode()
    for expected in ['tests 152', 'pass 152', 'fail 0', 'skipped 0']:
        assert expected in log, expected
    build = raw(WORK / 'root/studio-build-final.log').decode()
    assert 'tsc --noEmit && vite build' in build and 'index-ChS0wIgb.js' in build and 'built in' in build
    independence = load(WORK / 'root/final-independence-report.json')
    assert independence['passed'] and len(independence['checks']) == 9
    assert all(row['passed'] for row in independence['checks'])
    copied = {item['path']: item['sha256'] for item in independence['sourceManifest']}
    assert all(copied[key] == value for key, value in final['sourceBindings'].items())
    origins = independence['checks'][0]['origins']
    assert all(value.startswith(independence['standaloneCopy'] + '/src/') for value in origins.values())
    recovery = raw('studio/src/core/layoutRecovery.ts').decode()
    assert 'let length = 0' in recovery and 'length +=' in recovery and 'return length' in recovery
    assert 'severity(scene, diagnostic) > existing.get(signature(diagnostic))! + 1e-6' in recovery
    return {'sourceBindings': len(final['sourceBindings']), 'buildAssets': len(final['assets']),
            'studioPass': 152, 'studioFail': 0, 'studioSkip': 0, 'independenceChecks': 9,
            'routeSeverity': 'sum of orthogonal route lengths inside each named blocker rectangle; ancestors use header rectangle',
            'suiteRerunByThisAudit': False}


def jpeg_dimensions(data):
    assert data[:2] == b'\xff\xd8', 'Expected real JPEG magic despite .png suffix'
    offset = 2
    while offset < len(data):
        while offset < len(data) and data[offset] == 255:
            offset += 1
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        size = struct.unpack('>H', data[offset:offset + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height, width = struct.unpack('>HH', data[offset + 3:offset + 7])
            return width, height
        offset += size
    raise AssertionError('JPEG missing frame dimensions')


def xml_tree(value, remove_revision=False):
    node = ET.fromstring(value)
    if remove_revision:
        del node.attrib['data-revision']
        meta = node.find('{http://www.w3.org/2000/svg}metadata')
        metadata = json.loads(meta.text)
        del metadata['revision']
        meta.text = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
    def visit(n):
        return [n.tag, sorted(n.attrib.items()), n.text or '', n.tail or '', [visit(c) for c in n]]
    return visit(node)


def browser():
    publics = sorted(BROWSER.glob('*.public.json'))
    assert len(publics) == 23
    screenshots = sorted(BROWSER.glob('*.png'))
    assert len(screenshots) == 46
    dimensions = {}
    for p in publics:
        stem = p.name.removesuffix('.public.json')
        state = load(p)
        assert state['scripts'] == ['/assets/index-ChS0wIgb.js'], stem
        assert raw(BROWSER / (stem + '.before.dom.txt')) == raw(BROWSER / (stem + '.after.dom.txt')), stem
        image = raw(BROWSER / (stem + '.png'))
        primer = raw(BROWSER / (stem + '.primer.png'))
        dimensions[stem] = list(jpeg_dimensions(image))
        jpeg_dimensions(primer)
    def public(stem):
        return load(BROWSER / (stem + '.public.json'))
    saved = public('movement-final-saved')
    reopened = public('movement-final-reopened')
    refused = public('pinned-move-refused-final')
    assert saved['svg'] == reopened['svg'] and len(saved['svg']) == 20687
    assert int(saved['committedRevision']) == int(reopened['committedRevision']) == 17
    assert int(refused['committedRevision']) == 18 and refused['sceneKind'] == 'committed'
    assert '已固定' in refused['footer']
    assert xml_tree(saved['svg'], True) == xml_tree(refused['svg'], True)
    document = load(BROWSER / 'movement-final-envelope.json')['document']
    exported = load(BROWSER / 'movement-final-export/document.json')
    assert document == exported and document['revision'] == 17
    assert document['pinnedObjects'] == ['call:instance:model.MLP.network.0']
    receipt = load(BROWSER / 'movement-final-export/figure.svg.receipt.json')
    assert receipt['revision'] == 17 and receipt['outputDigest'] == sha(BROWSER / 'movement-final-export/figure.svg')
    for first, second in [('move-left-final', 'move-left-undo-final'), ('move-left-applied-final', 'move-left-redo-final')]:
        assert xml_tree(public(first)['svg'], True) == xml_tree(public(second)['svg'], True)
    assert public('move-left-preview-final')['sceneKind'] == 'recovery-preview'
    assert int(public('move-left-preview-final')['committedRevision']) == int(public('move-left-final')['committedRevision'])
    assert xml_tree(public('move-left-final')['svg'], True) == xml_tree(public('move-left-cancel-final')['svg'], True)
    reconstruction = load(Path(__file__).with_name('export-input-reconstruction.json'))
    assert sha(Path(__file__).with_name('reconstructed-export-input.svg')) == reconstruction['candidateSvgSha256'] == receipt['inputSvgDigest'] == receipt['sceneSvgDigest']
    assert reconstruction['candidateEqualsPublicBytes'] is False
    renderer = raw('studio/src/core/svg.ts').decode()
    assert 'node.width - (interactive ? 47 : 17)' in renderer
    return {'publicStems': 23, 'screenshots': 46, 'actualEncoding': 'JPEG; preserved .png suffix',
            'pairedDomExact': True, 'dimensions': dimensions, 'savedAndExportedRevision': 17,
            'pinRefusalRevision': 18, 'pinRefusalWholeXmlUnchangedExceptRevision': True,
            'savedReopenedFullSvgExact': True, 'savedPinCount': 1,
            'humanResearchers': 0, 'browserActionsByThisAuditor': 0,
            'exportInputReconstructionMatchesReceipt': True,
            'exportInputSvgSha256': reconstruction['candidateSvgSha256'],
            'publicAndExportWholeSvgEqual': False,
            'repeatLabelPositionDifference': '30 SVG units by explicit interactive ? 47 : 17 renderer placement; no whole text geometry equality claim',
            'note': 'Read stored DOM/SVG/image headers; this is not a new actual-pixel or capture-provenance certification.'}


def documents():
    overview = raw('docs/m4-move-recovery-presets.md').decode()
    assert '152/152' in overview and 'partial' in overview
    assert '长度' in overview and ('severity' in overview or '侵入' in overview), 'Explain actual route-length severity'
    assert '18' in overview and '17' in overview and '固定' in overview, 'Separate pin refusal18 from saved/export17'
    assert 'AI' in overview and '真人' in overview
    status = load('docs/evidence/m4-human-review-handoff-status.json')
    assert status['productionBuild'] == 'index-ChS0wIgb.js'
    assert status['productionJsSha256'] == JS_SHA
    assert status['phaseStatus'] == 'partial' and status['currentMatrix']['humanCertified'] is False
    assert status['research']['researcherCount'] == status['research']['assignedParticipants'] == status['research']['collectedParticipants'] == 0
    current = ['README.md', 'docs/m4-move-recovery-presets.md', 'docs/m4-completion.md',
               'docs/m4-exit-audit.md', 'docs/m4-human-review-handoff.md', 'docs/m4-authoring-feedback.md',
               'docs/capability-matrix.md', 'docs/acceptance.md', 'docs/evidence/README.md',
               'docs/evidence/m4-move-recovery-presets-work/README.md']
    count = 0
    for name in current:
        p = path(name)
        text = raw(p).decode()
        for destination in re.findall(r'\]\((<[^>]+>|[^\s\)]+)(?:\s+[^\)]*)?\)', text):
            target = destination.strip('<>')
            if target.startswith('#') or urlsplit(target).scheme:
                continue
            target = unquote(target.split('#', 1)[0].split('?', 1)[0])
            if not target:
                continue
            resolved = Path(target) if target.startswith('/') else p.parent / target
            assert resolved.exists(), f'{name} -> {target}'
            count += 1
    return {'currentMarkdownFiles': len(current), 'localLinksExist': count,
            'severityAndPinRevisionScopeExplicit': True, 'm4Status': 'partial', 'humanAcceptanceCertified': False}


def independent_reports():
    manifest = load(WORK / 'browser-independent/evidence-manifest.json')
    assert manifest['status'] == 'passed' and manifest['modelExecution'] == 'not_run'
    assert manifest['humanAcceptanceCertified'] is False
    assert manifest['totals'] == {'cases': 4, 'draftNodes': 27, 'draftEdges': 24,
                                  'negativeASTControls': 29, 'irNodes': 31,
                                  'irEdges': 28, 'exactPorts': 51}
    for value, expected in manifest['inputBindings'].items():
        assert sha(value) == expected, value
    for item in manifest['bindings']:
        check_binding(item)
    case_summary = load(WORK / 'browser-independent/attempt-1/audit-summary.json')
    assert len(case_summary['cases']) == 4 and all(row['status'] == 'passed' for row in case_summary['cases'])
    assert case_summary['totals'] == manifest['totals']
    pixels = load(ROOT / 'docs/evidence/m4-move-recovery-presets-browser/work/final-ChS0wIgb-independent/final-audit-summary.json')
    counts = pixels['summary']
    assert counts['scopeStemCount'] == 23 and counts['actualOriginalImageCount'] == 46
    assert counts['encodedFormatCounts'] == {'JPEG': 46}
    assert counts['allCapturedPublicSvgRouteInstances'] == 140
    assert counts['postRefusalRevision'] == 18 and counts['postRefusalFullPinArrayCertified'] is False
    assert counts['publicAndExportWholeSvgBytesExact'] is False
    assert counts['receiptInputDigestMatchesCapturedPublicSvg'] is False
    assert counts['visibleExportRepeatTextXDifference'] == {'text': '4× · independent', 'public': 339, 'export': 369}
    assert counts['humanReviewCount'] == 0 and counts['humanAcceptanceCertified'] is False
    for collection in ['detailedReportBindings', 'auditHelperBindings', 'rawAndSourceInputBindings']:
        for item in pixels[collection]:
            check_binding(item)
    assert pixels['finalRecheck']['errors'] == []
    return {'staticCases': manifest['totals'], 'staticBindings': len(manifest['bindings']),
            'staticInputBindings': len(manifest['inputBindings']),
            'pixelAuditorRecordedActualImages': 46, 'pixelAuditorRecordedStems': 23,
            'pixelSourceRouteInstances': 140, 'pixelSourceReportBindings': 146,
            'wholePublicAndExportEqualityCertified': False, 'humanReviewCount': 0,
            'scope': 'Recorded independent AI audits read and byte-checked; no original human review or runtime result supplied by this auditor.'}


def seal(value):
    receipt = load(value)
    bindings = receipt['bindings']
    assert receipt['bindingCount'] == len(bindings)
    if isinstance(bindings, dict):
        rows = [{'path': p, 'sha256': h} if isinstance(h, str) else {'path': p, **h} for p, h in bindings.items()]
    else:
        rows = bindings
    assert len({row['path'] for row in rows}) == len(rows)
    for row in rows:
        check_binding(row)
    bound = {row['path'] for row in rows}
    required = ['studio/src/core/layoutRecovery.ts', 'studio/src/authoringPresets.ts',
                'studio/dist/assets/index-ChS0wIgb.js', 'docs/m4-move-recovery-presets.md',
                'docs/evidence/m4-human-review-handoff-status.json',
                'docs/evidence/m4-move-recovery-presets-work/root/final-product-validation.json']
    assert all(p in bound for p in required), 'Missing final product or docs binding'
    return {'receipt': str(path(value).relative_to(ROOT)), 'bindingCount': len(rows),
            'sha256': sha(value), 'allDeclaredBindingsExact': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--seal', type=Path)
    args = parser.parse_args()
    assert args.preview or args.seal is not None, 'Wait for explicit final seal path'
    if not args.preview:
        path(args.seal)
        assert not OUTPUT.exists(), 'Never replace an audit report'
    checks = [('archive', archive), ('product', product), ('browser', browser),
              ('documents', documents), ('independentReports', independent_reports)]
    if args.seal:
        checks.append(('seal', lambda: seal(args.seal)))
    results, issues = {}, []
    for name, operation in checks:
        try:
            results[name] = operation()
        except Exception as error:
            issues.append({'check': name, 'type': type(error).__name__, 'message': str(error)})
    report = {'schemaVersion': 1, 'at': datetime.now(timezone.utc).isoformat(),
              'state': 'preview-unsealed' if args.preview else 'passed-read-only-audit' if not issues else 'issues-found',
              'passed': not issues, 'results': results, 'issues': issues,
              'limits': ['Stored byte/DOM/SVG checks do not establish human publication aesthetics or presented performance.',
                         'AI operators/auditors count as zero human researchers; M4 remains partial.',
                         'No source/build/old-raw changes, product suite reruns, model execution, participant assignment, browser or service actions.']}
    if not args.preview:
        with OUTPUT.open('x') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
