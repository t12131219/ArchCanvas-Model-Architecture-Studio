#!/usr/bin/env python3
"""Read-only audit of actual edited browser journals; never supplies observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
SVG = '{http://www.w3.org/2000/svg}'
STEPS = ('before', 'committed', 'undo', 'redo', 'saved', 'reopened')
CASES = {
    'residual_cnn': {'names': ['residual_cnn-round2-' + s for s in STEPS],
                     'variant': 'residual_cnn-level0-paper-180',
                     'revisions': [36, 37, 38, 39, 39, 39],
                     'text': 'Residual blocks preserve skip paths.'},
    'mlp': {'names': ['mlp-before-text'] + ['mlp-' + s for s in STEPS[1:]],
            'variant': 'mlp-level1-paper-180',
            'revisions': [20, 21, 22, 23, 23, 23],
            'text': 'Sequential modules preserve source order.'},
    'transformer': {'names': ['transformer-before-text'] + ['transformer-' + s for s in STEPS[1:]],
                    'variant': 'transformer-level0-paper-180', 'revisions': None,
                    'text': None},
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             allow_nan=False, separators=(',', ':')).encode())


def audit(fixtures, require_packaged):
    bound = {}

    def readbytes(path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        entry = {'path': key, 'sha256': digest(raw), 'bytes': len(raw)}
        if key in bound:
            assert bound[key] == entry, f'Input changed during audit: {key}'
        bound[key] = entry
        return raw

    def readjson(path):
        return json.loads(readbytes(path))

    def xml_value(raw, remove_revision=False):
        if isinstance(raw, str):
            raw = raw.encode()
        assert not re.search(rb'<!\s*(?:DOCTYPE|ENTITY)|<\?', raw, re.I)
        tree = ET.fromstring(raw)
        assert tree.tag == SVG + 'svg'
        if remove_revision:
            assert re.fullmatch(r'\d+', tree.attrib['data-revision'])
            tree.set('data-revision', '0')
            metadata = tree.findall(SVG + 'metadata')
            assert len(metadata) == 1
            text = metadata[0].text
            value = json.loads(text)
            assert type(value['revision']) is int
            # Replace this one numeric token; preserve all other metadata text.
            text, count = re.subn(r'("revision"\s*:\s*)\d+(?=\s*[,}])', r'\g<1>0', text)
            assert count == 1, 'Only one root metadata revision may be excluded.'
            metadata[0].text = text

        def element(node):
            return [node.tag, sorted(node.attrib.items()), node.text or '',
                    node.tail or '', [element(child) for child in node]]
        return element(tree)

    def metadata(raw):
        tree = ET.fromstring(raw)
        nodes = tree.findall(SVG + 'metadata')
        assert len(nodes) == 1
        return tree, json.loads(nodes[0].text)

    readbytes(__file__)
    readbytes(ROOT / 'AGENTS.md')
    readbytes(ROOT / 'skills/archcanvas/SKILL.md')
    spec = readjson(ROOT / '.archcanvas/browser-visual-matrix-boundary-final/spec.json')
    expected = {v['variantId']: v for v in spec['variants']}
    readbytes(ROOT / 'scripts/browser_visual_core.mjs')
    results = []
    for fixture in fixtures:
        case = CASES[fixture]
        journal_paths = [WORK / 'edited-journal' / (name + '.json') for name in case['names']]
        journals = [readjson(path) for path in journal_paths]
        xml = [xml_value(j['svg']) for j in journals]
        xml_without_revision = [xml_value(j['svg'], True) for j in journals]
        revisions = [j['documentBinding']['revision'] for j in journals]
        if case['revisions']:
            assert revisions == case['revisions'], (fixture, revisions)
        else:
            assert revisions == [revisions[0], revisions[0] + 1, revisions[0] + 2,
                                 revisions[0] + 3, revisions[0] + 3, revisions[0] + 3]
        assert xml_without_revision[0] != xml_without_revision[1], 'Committed edit must change full scene.'
        assert xml_without_revision[0] == xml_without_revision[2], 'Undo differs from before beyond revision.'
        assert xml_without_revision[1] == xml_without_revision[3], 'Redo differs from committed beyond revision.'
        assert xml[3] == xml[4] == xml[5], 'Redo/save/reopen complete XML including revision differs.'
        assert journals[3]['svg'] == journals[4]['svg'] == journals[5]['svg'], 'Actual serialized DOM bytes differ.'

        variant = expected[case['variant']]
        baseline = readjson(variant['canvasFile'])
        source_meta = None
        annotation_states = []
        for journal in journals:
            tree, meta = metadata(journal['svg'])
            binding = journal['documentBinding']
            assert tree.attrib['data-document-id'] == binding['documentId'] == baseline['id']
            assert tree.attrib['data-revision'] == str(binding['revision'])
            assert meta['documentId'] == binding['documentId']
            assert meta['revision'] == binding['revision']
            assert meta['sourceDigest'] == binding['sourceDigest'] == variant['sourceDigest']
            assert meta['irDigest'] == binding['irDigest'] == variant['irDigest']
            assert sorted(journal['expandedIds']) == sorted(variant['expandedIds'])
            assert journal['pageSpec'] == {'widthMm': 180, 'preset': 'paper'}
            facts = {key: meta[key] for key in ('sourceDigest', 'irDigest', 'sourceFactScope',
                                               'sourceFacts', 'renderedNodes', 'renderedBindings')}
            if source_meta is None:
                source_meta = facts
            assert facts == source_meta, 'Source/IR facts or rendered bindings changed during visual text edit.'
            annotation_states.append([
                {'id': node.attrib['data-annotation-id'],
                 'text': ''.join(node.itertext())}
                for node in tree.iter() if 'data-annotation-id' in node.attrib])
        assert len(annotation_states[-1]) == 1
        if case['text']:
            assert annotation_states[-1][0]['text'] == case['text']
        assert annotation_states[0] == annotation_states[2]
        assert annotation_states[1] == annotation_states[3] == annotation_states[4] == annotation_states[5]

        raw_dir = WORK / 'raw' / (fixture + '-edited-paper-180')
        observation = readjson(raw_dir / 'dom-observation.json')
        stored_raw = readbytes(raw_dir / 'actual-document-store.json')
        envelope = json.loads(stored_raw)
        document = envelope['document']
        snapshot = observation['actualStoredEnvelope']
        assert snapshot['sha256'] == digest(stored_raw) and snapshot['bytes'] == len(stored_raw)
        assert envelope['revision'] >= 0  # Store revision is distinct from visual revision.
        assert document['revision'] == revisions[-1]
        assert document['architecture'] == baseline['architecture']
        assert sorted(document['expandedIds']) == sorted(variant['expandedIds'])
        assert document['pageSpec'] == baseline['pageSpec']
        assert observation['documentBinding'] == journals[-1]['documentBinding']
        assert observation['state'] == 'edited' and observation['variantId'] == variant['variantId']
        raw_svg = readbytes(raw_dir / 'browser-scene.svg')
        assert xml_value(raw_svg) == xml[-1], 'Final raw scene differs from reopened complete journal scene.'
        assert raw_svg == journals[-1]['svg'].encode(), 'Final raw scene serialized bytes differ from reopen.'
        for source in document['architecture']['sources']:
            actual = readbytes(ROOT / 'fixtures' / fixture / source['path'])
            assert actual == source['content'].encode()
            assert digest(actual) == source['digest']

        # Derive expected markup from the whole actual saved document, not its
        # selected subset or a handcrafted replacement. No browser/model run.
        with tempfile.TemporaryDirectory(prefix='archcanvas-journal-audit-') as temp:
            temp = Path(temp)
            inp = temp / 'input.json'
            out = temp / 'expected'
            inp.write_text(json.dumps([{'document': document}], ensure_ascii=False))
            proc = subprocess.run(['node', str(ROOT / 'scripts/browser_visual_core.mjs'),
                                   str(inp), str(out)], cwd=ROOT, capture_output=True, text=True, timeout=60)
            assert proc.returncode == 0, proc.stderr
            core_raw = (out / '0.interactive.svg').read_bytes()
            assert xml_value(core_raw) == xml_value(raw_svg), 'Whole saved Canvas does not reconstruct actual DOM.'
            facts = json.loads((out / 'facts.json').read_bytes())[0]
        case_canvas = WORK / 'cases' / (fixture + '-edited-paper-180') / 'canvas.json'
        packaged = case_canvas.exists()
        assert packaged or not require_packaged, 'Packaged export Canvas is required for final audit.'
        if packaged:
            canvas = readjson(case_canvas)
            assert canvas == document, 'Complete export Canvas differs from actual store snapshot.'
        results.append({'fixture': fixture, 'variantId': variant['variantId'],
            'journalPaths': [str(path.relative_to(ROOT)) for path in journal_paths],
            'visualRevisions': revisions, 'undoFullXmlExceptTwoRevisionValues': True,
            'redoFullXmlExceptTwoRevisionValues': True,
            'redoSaveReopenFullXmlIncludingRevision': True,
            'redoSaveReopenSerializedDomBytes': True,
            'sourceAndIrFactsUnchangedThroughout': True,
            'completeFrontierMatchesRequirement': True,
            'currentFixtureBytesMatchEmbeddedSource': True,
            'wholeActualStoreCanvasReconstructsFinalDom': True,
            'wholeExportCanvasEqualsActualStoreSnapshot': packaged,
            'canvasCanonicalDigest': canonical(document),
            'fullXmlDigests': [canonical(value) for value in xml],
            'excludingRevisionXmlDigests': [canonical(value) for value in xml_without_revision],
            'annotationStates': annotation_states, 'coreFacts': facts})

    excluded = []
    for path in sorted((WORK / 'edited-journal').glob('residual_cnn-*.json')):
        if path.stem in CASES['residual_cnn']['names']:
            continue
        data = readjson(path)
        excluded.append({'path': str(path.relative_to(ROOT)),
                         'visualRevision': data['documentBinding']['revision'],
                         'scope': 'Preserved early/add/precommit attempt; not counted as the clean committed-edit sequence.'})
    # Every source/evidence file is re-read; reject concurrent modifications.
    for key, value in list(bound.items()):
        path = ROOT / key if not Path(key).is_absolute() else Path(key)
        raw = path.read_bytes()
        assert {'path': key, 'sha256': digest(raw), 'bytes': len(raw)} == value
    return {'schemaVersion': 1, 'protocol': 'archcanvas-independent-edited-journal-audit/1',
        'auditedAt': datetime.now(timezone.utc).isoformat(), 'auditCompleted': True,
        'fixturesAudited': fixtures, 'cases': results, 'preservedExcludedJournals': excluded,
        'bindings': sorted(bound.values(), key=lambda value: value['path']),
        'humanAcceptanceCertified': False,
        'scope': 'Independent read-only artifact inspection and formal core reconstruction of actual saved Canvas.',
        'limitations': [
            'The actual browser actions and capture provenance are operator observations; this script does not recreate them.',
            'All XML tag/attribute/text/tail/child-order content is compared; undo/redo exclude only root data-revision and root metadata revision numeric values.',
            'Journals contain full SVG DOM, not intermediate whole Canvas envelopes; the final saved envelope/export Canvas are checked in full.',
            'Precommit input drafts and a disabled Undo attempt do not demonstrate committed text edit history.',
            'Rendered source evidence and current fixture bytes establish recorded artifact consistency, not continuous monitoring of source files.',
            'No model is executed; XML equality does not establish pixels, physical publication readability, sustained painted frames or real researcher acceptance.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', nargs='+', choices=CASES, default=list(CASES))
    parser.add_argument('--require-packaged', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert len(args.fixtures) == len(set(args.fixtures))
    output = args.output.resolve()
    assert output.is_relative_to(WORK) and not output.exists(), 'Use a new exclusive file in this work directory.'
    result = audit(args.fixtures, args.require_packaged)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'sha256': digest(output.read_bytes()),
                      'fixturesAudited': result['fixturesAudited'], 'bindings': len(result['bindings'])}))


if __name__ == '__main__':
    main()
