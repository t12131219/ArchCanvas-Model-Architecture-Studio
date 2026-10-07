"""Bind final docs and explicitly resolve the preserved intermediate seal."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import re
import urllib.parse

ROOT = Path(__file__).resolve().parents[4]
WORK = Path('docs/evidence/m4-draft-merge-routing-work')
CORRECTION = WORK / 'final-consistency-correction-attempt-1'


def binding(path):
    path = Path(path)
    data = (ROOT / path).read_bytes()
    return {'path': path.as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def write(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def exact(record, path=None):
    actual = binding(path or record['path'])
    return actual['bytes'] == record['bytes'] and actual['sha256'] == record['sha256']


def main():
    before = json.loads((ROOT / CORRECTION / 'before-manifest.json').read_text())
    assert all(exact(r, r['archive']) for r in before['records'])
    docs = ['docs/m4-completion.md', 'docs/m4-draft-merge-routing.md']
    status_path = 'docs/evidence/m4-human-review-handoff-status-followup.json'
    status = json.loads((ROOT / status_path).read_text())
    assert status['schemaVersion'] == 14
    assert status['tests']['studio']['passed'] == 275
    assert status['tests']['focusedSeparateRun']['passed'] == 39
    assert status['productionBuild'] == 'index-BSA5RjBV.js'
    assert status['humanResearch']['researchers'] == 0
    assert status['nextPhaseStarted'] is False
    assert status['aiReview']['rolesAreHumanParticipants'] is False
    assert all(exact(r) for r in status['evidenceRefs'])

    links = []
    for doc in docs:
        text = (ROOT / doc).read_text()
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.strip().strip('<>')
            url = urllib.parse.urlsplit(target)
            if url.scheme or not url.path:
                continue
            path = (ROOT / doc).parent / urllib.parse.unquote(url.path)
            links.append({'doc': doc, 'target': target, 'exists': path.exists()})
    assert all(r['exists'] for r in links), [r for r in links if not r['exists']]
    diff = []
    for doc in docs:
        archived = next(r['archive'] for r in before['records'] if r['path'] == doc)
        diff.extend(difflib.unified_diff((ROOT / archived).read_text().splitlines(True),
                                        (ROOT / doc).read_text().splitlines(True),
                                        fromfile=archived, tofile=doc))
    (ROOT / CORRECTION / 'diff.txt').write_text(''.join(diff))

    old_seal_path = 'docs/evidence/m4-draft-merge-routing-verification-sealed.json'
    old_seal = json.loads((ROOT / old_seal_path).read_text())
    archived_seal = next(r for r in before['records'] if r['path'] == old_seal_path)
    assert exact(archived_seal), 'Preserved intermediate seal was changed'
    archive_map = {(r['path'], r['bytes'], r['sha256']): r['archive']
                   for r in before['records']}
    resolutions = []
    for r in old_seal['records']:
        if (ROOT / r['path']).exists() and exact(r):
            resolved = r['path']
        else:
            resolved = archive_map[(r['path'], r['bytes'], r['sha256'])]
            assert exact(r, resolved)
        resolutions.append({**r, 'resolvedPath': resolved})

    receipt = {
        'protocol': 'archcanvas-merge-routing-final-consistency-correction/1',
        'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Current narrative/status repair only; no product changes or test/build rerun.',
        'beforeManifest': binding(CORRECTION / 'before-manifest.json'),
        'priorToRoutingDocument': before['records'][-1],
        'currentDocuments': [binding(d) for d in docs],
        'currentStatus': binding(status_path),
        'changes': [
            'current lead and table now bind BSA5/39 focused/275 full, not ye/28/264',
            'schema14 is standalone current state; shallow inherited schema13 is archived',
            'all current evidenceRefs have exact path/bytes/sha256 records',
            'old preset/managed/export actions stay at their ye-stage evidence scope',
            'merge source is static only; no matching managed model or export claimed',
            '100-percent raster mismatch cannot count as certified local zoom',
            'five AI reviewer roles do not count as human participants',
        ],
        'preservedIntermediateClaims': [
            'doc-correction-attempt-1 and attempt-2 currentDocument claims describe intermediate bytes, not final current docs',
            'doc-correction-attempt-2 initially held incorrect preceding archive then was corrected to30409B; final archive here is independently exact',
            'seal1 is preserved unchanged; its mutable docs/status bindings resolve to explicit before archives',
            'schema13 mixed current build with older nested checks/geometry and mixed evidenceRef types; it is not the final status',
            'first patch application for this correction failed to match a line and made no product change',
        ],
        'localLinkCount': len(links), 'allLocalLinksExist': True, 'links': links,
        'currentEvidenceBindingsExact': len(status['evidenceRefs']),
        'priorSeal': binding(old_seal_path),
        'priorSealBindingsResolved': len(resolutions),
        'priorSealArchiveResolution': [r for r in resolutions if r['path'] != r['resolvedPath']],
        'M4': 'partial', 'M5': 'not_started', 'humanParticipants': 0,
        'notCertified': ['whole-document semantic approval', 'arbitrary layout aesthetics',
                         'presentation performance', 'physical publication', 'human novice usability'],
    }
    receipt_path = CORRECTION / 'receipt.json'
    assert not (ROOT / receipt_path).exists(), 'Final receipt must not be silently replaced'
    write(receipt_path, receipt)

    current = [
        *docs, status_path, old_seal_path,
        'studio/src/draftRouting.ts', 'studio/src/authoring.ts',
        'studio/tests/draft-merge-routing-independent.test.ts',
        'studio/dist/index.html', 'studio/dist/assets/index-BSA5RjBV.js',
        'studio/dist/assets/index-C769d2rm.css',
    ]
    paths = {p.relative_to(ROOT).as_posix()
             for p in (ROOT / WORK).rglob('*') if p.is_file()}
    paths.update(current)
    new_seal_path = 'docs/evidence/m4-draft-merge-routing-verification-sealed-attempt-2.json'
    assert not (ROOT / new_seal_path).exists(), 'New seal must not replace an earlier attempt'
    seal = {
        'protocol': 'archcanvas-draft-merge-routing-bounded-followup-seal/2',
        'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Final current docs/status14 plus bounded product/native/AI evidence. Exact bytes do not certify every intermediate narrative.',
        'currentBuild': 'index-BSA5RjBV.js',
        'records': [binding(p) for p in sorted(paths)],
        'boundFileCount': len(paths),
        'M4': 'partial', 'M5': 'not_started', 'humanParticipants': 0,
        'checks': {'focused': '39/39', 'suite': '275/275', 'strictTypeScriptVite': 'exit0',
                   'independentContract': '11 final; baseline7pass4fail',
                   'sourceReview': '9/9', 'checkReadback': '6/6'},
        'aiOnlyAdditionalChecks': {'savedPublicGeometry': '11/11', 'noviceReadOnlyChecks': '15/15',
                                  'countsCombinedWithStudioTests': False},
        'browser': status['browser'],
        'limits': status['openItems'],
        'preservedIntermediateSeal': binding(old_seal_path),
        'priorSealBindingsResolved': len(resolutions),
        'priorSealArchiveResolution': receipt['priorSealArchiveResolution'],
        'finalConsistencyReceipt': binding(receipt_path),
        'currentStatus': binding(status_path),
        'priorProductStageSeal': 'docs/evidence/m4-authoring-interaction-verification-sealed.json',
        'priorMutableMap': str(WORK / 'before-implementation-attempt-1/manifest.json'),
        'intermediateFailureScope': receipt['preservedIntermediateClaims'],
    }
    write(new_seal_path, seal)
    print(json.dumps({'receipt': binding(receipt_path), 'seal': binding(new_seal_path),
                      'localLinks': len(links), 'oldSealResolved': len(resolutions),
                      'newBindings': len(paths)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
