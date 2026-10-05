#!/usr/bin/env python3
"""Independent frozen-byte audit of the actual browser hierarchy React probe.

No browser or model execution. Inputs are parsed from exactly the bytes hashed
on first read, and those bytes are re-read for an end-of-audit stability check.
The independent model recomputes property reads and visible tree facts; the raw
receipt does not contain full DOM strings, so their hashes cannot be recomputed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
CACHE: dict[str, bytes] = {}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load_bytes(path: str | Path) -> bytes:
    target = path if isinstance(path, Path) else ROOT / path
    key = relative(target)
    if key not in CACHE:
        CACHE[key] = target.read_bytes()
    return CACHE[key]


def load_json(path: str | Path):
    return json.loads(load_bytes(path))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_binding(item, path: str | Path | None = None):
    data = load_bytes(path or item['path'])
    require(len(data) == item['bytes'], f"Size differs for {path or item['path']}")
    require(sha(data) == item['sha256'], f"SHA256 differs for {path or item['path']}")


def visible_tree(document):
    architecture = document['architecture']
    by_id = {node['id']: node for node in architecture['nodes']}
    items = []

    def visit(node, depth):
        items.append((node, depth))
        if node['id'] in document['expandedIds']:
            for child_id in node['children']:
                if child_id in by_id:
                    visit(by_id[child_id], depth + 1)

    for node in architecture['nodes']:
        if not node.get('parentId'):
            visit(node, 0)
    return items


def tree_facts(document, selected, targets):
    items = visible_tree(document)
    by_id = {node['id']: (node, depth) for node, depth in items}
    target_facts = []
    for node_id in targets:
        if node_id not in by_id:
            target_facts.append({'id': node_id, 'visible': False, 'depth': None, 'expanded': None,
                                 'selected': None, 'label': None, 'repeat': None,
                                 'pinIcon': False, 'toggleLabel': None})
            continue
        node, depth = by_id[node_id]
        expanded = node_id in document['expandedIds']
        label = document['displayAliases'].get(node_id)
        if label is None:
            label = node['label']
        target_facts.append({
            'id': node_id, 'visible': True, 'depth': str(depth),
            'expanded': str(expanded).lower() if node['children'] else None,
            'selected': str(node_id in selected).lower(), 'label': label,
            'repeat': f"×{node['repeat']['count']}" if node.get('repeat') else None,
            'pinIcon': node_id in document['pinnedObjects'],
            'toggleLabel': f"{'收起' if expanded else '展开'} {node['label']}",
        })
    return {'visibleNodeCount': len(items), 'visibleIds': [node['id'] for node, _ in items],
            'targets': target_facts}


def read_counts(document, architecture_changed):
    """Count expressions in source, independently of receipt's count/check fields.

    Old node: 6 id reads, 2 children reads plus expanded map, one aria
    label read and one nullish-alias fallback. Root key costs one id.
    Every old child lookup reads candidate ids until the first matching id.
    New node: 5 id reads (one selected Set lookup is reused), same labels
    and children. A changed architecture builds the Map with N id reads.
    """
    nodes = document['architecture']['nodes']
    items = visible_tree(document)
    roots = sum(not node.get('parentId') for node in nodes)
    n = len(items)
    children = 2 * n + sum(node['id'] in document['expandedIds'] for node, _ in items)
    labels = n + sum(document['displayAliases'].get(node['id']) is None for node, _ in items)
    old_lookup_reads = 0
    for node, _ in items:
        if node['id'] in document['expandedIds']:
            for child_id in node['children']:
                old_lookup_reads += next((i + 1 for i, candidate in enumerate(nodes)
                                          if candidate['id'] == child_id), len(nodes))
    old_id = 6 * n + roots + old_lookup_reads
    new_id = 5 * n + roots + (len(nodes) if architecture_changed else 0)
    return {
        'old': {'id': old_id, 'label': labels, 'children': children,
                'total': old_id + labels + children},
        'new': {'id': new_id, 'label': labels, 'children': children,
                'total': new_id + labels + children},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-base', default='react-probe-independent-audit')
    args = parser.parse_args()
    require(bool(re.fullmatch(r'[a-z0-9][a-z0-9-]*', args.output_base)), 'Unsafe output name')
    json_output = EVIDENCE / f'{args.output_base}.json'
    md_output = EVIDENCE / f'{args.output_base}.md'
    require(not json_output.exists() and not md_output.exists(), 'Preserve previous audits; choose another output name')
    load_bytes(Path(__file__))
    raw_path = EVIDENCE / 'react-probe-browser-raw.json'
    raw = load_json(raw_path)
    preparation = load_json(EVIDENCE / 'react-probe-prepare.json')
    duplicate = load_bytes(EVIDENCE / 'react-probe-dist-prepare.json')
    require(duplicate == load_bytes(EVIDENCE / 'react-probe-prepare.json'), 'Preparation copies differ')
    require(preparation['status'] == 'compiled-not-browser-executed', 'Preparation status differs')
    require(preparation['typecheck']['diagnosticsCount'] == 0 and preparation['typecheck']['exitCode'] == 0,
            'Strict TypeScript did not pass')
    require(all(preparation['checks'].values()), 'Preparation has failed checks')
    require(load_bytes(preparation['typecheck']['log']) == b'', 'Successful typecheck log is not empty')
    load_json(EVIDENCE / 'react-probe-dist-vite-log.json')
    snapshot = ROOT / preparation['preservedInputsDirectory']
    snapshot_manifest = load_json(snapshot / 'manifest.json')
    require(snapshot_manifest['sourceEntries'] == preparation['sourceEntries'], 'Snapshot input list differs')
    for item in preparation['sourceEntries']:
        check_binding(item)
        check_binding(item, snapshot / item['path'])
    for item in preparation['outputEntries']:
        check_binding(item)
    require(all(item['unchanged'] and item['sha256'] == item['afterSha256']
                and item['bytes'] == item['afterBytes'] for item in preparation['sourceRecheck']),
            'Original preparation had input drift')
    dist = ROOT / preparation['outputDirectory']
    source_bindings = load_json(dist / 'source-bindings.json')
    build_bindings = load_json(dist / 'build-bindings.json')
    fixture_bytes = load_bytes(dist / 'fixture.json')
    fixture = json.loads(fixture_bytes)
    require(raw['fixture']['sourceBindings'] == source_bindings, 'Browser source bindings differ from dist')
    require(raw['fixture']['buildBindings'] == build_bindings, 'Browser build bindings differ from dist')
    require(source_bindings == snapshot_manifest['sourceBindings'], 'Source snapshot bindings differ')
    require(source_bindings['sourceEntries'] == preparation['sourceEntries'], 'Source entry lists differ')
    require(build_bindings['sourceEntries'] == preparation['sourceEntries'], 'Build source entry lists differ')
    for item in build_bindings['outputs']:
        check_binding(item)
    require(sha(fixture_bytes) == raw['originalFixtureSha256'] == source_bindings['fixture']['sha256'],
            'Fixture browser binding differs')
    compact_fixture = json.dumps(fixture, ensure_ascii=False, separators=(',', ':')).encode()
    require(sha(compact_fixture) == raw['originalParsedFixtureSha256'], 'Parsed immutable fixture digest differs')
    require(fixture_bytes == load_bytes(source_bindings['fixture']['path']), 'Fixture differs from original frozen envelope')
    for source in fixture['document']['architecture']['sources']:
        require(sha(source['content'].encode()) == source['digest'], 'Fixture source content digest differs')

    compile_root = ROOT / preparation['temporaryCompileRoot']
    extraction = source_bindings['legacyTreeExtraction']
    archived_app = load_bytes(extraction['source']['path'])
    old_function = archived_app[extraction['startByte']:extraction['endByteExclusive']]
    require(old_function.startswith(b'function TreeNode('), 'Legacy extraction start differs')
    require(len(old_function) == extraction['functionBytes'] and sha(old_function) == extraction['functionSha256'],
            'Legacy function bytes differ')
    legacy_module = extraction['generatedPrefix'].encode() + old_function + extraction['generatedSuffix'].encode()
    require(legacy_module == load_bytes(compile_root / 'LegacyTree.tsx'), 'Legacy compiled module differs from exact extraction')
    require(sha(legacy_module) == extraction['generatedModuleSha256'] == build_bindings['generatedLegacyModuleSha256'],
            'Legacy generated module digest differs')
    copy_pairs = {
        'HierarchyTree.tsx': 'studio/src/HierarchyTree.tsx',
        'icons.tsx': 'studio/src/icons.tsx', 'core.ts': 'studio/src/core/types.ts',
        'main.tsx': 'scripts/m4_hierarchy_support/main.tsx',
        'index.html': 'scripts/m4_hierarchy_support/index.html',
        'probe.css': 'scripts/m4_hierarchy_support/probe.css',
    }
    for destination, original in copy_pairs.items():
        require(load_bytes(compile_root / destination) == load_bytes(original), f'Compile copy differs: {destination}')
    for name in ['fixture.json', 'source-bindings.json']:
        require(load_bytes(compile_root / 'public' / name) == load_bytes(dist / name), f'Public compile copy differs: {name}')
    load_json(compile_root / 'tsconfig.json')
    current_app = load_bytes('studio/src/App.tsx').decode()
    current_tree = load_bytes('studio/src/HierarchyTree.tsx').decode()
    harness = load_bytes('scripts/m4_hierarchy_support/main.tsx').decode()
    legacy_text = old_function.decode()
    require('const selectHierarchyNode = useCallback(' in current_app and
            'const expandHierarchyNode = useCallback(' in current_app and
            'onSelect={selectHierarchyNode} onExpand={expandHierarchyNode}' in current_app,
            'Formal App stable hierarchy callback boundary is absent')
    require('export const HierarchyTree = memo(function HierarchyTree' in current_tree and
            'byId.set(node.id, node)' in current_tree and '}, [architecture]);' in current_tree and
            'state.byId.get(id)' in current_tree and 'const selected = state.selected.has(node.id)' in current_tree,
            'Expected formal indexed/memo tree contract is absent')
    require('architecture.nodes.find(n => n.id === id)' in legacy_text and
            legacy_text.count('selected.includes(node.id)') == 2,
            'Legacy lookup/selection expression count differs from independent read model')
    require(harness.index('const oldReads = oldCounter.stop();') < harness.index('const oldFacts = facts(') and
            harness.index('const newReads = newCounter.stop();') < harness.index('const newFacts = facts('),
            'DOM auditing is not excluded from proxy counts')
    require("if (enabled && (key === 'id' || key === 'label' || key === 'children'))" in harness and
            'oldCounter.reset(); newCounter.reset();' in harness and
            'nativeIsTrusted: event.nativeEvent.isTrusted' in harness,
            'Probe instrumentation contract differs')
    require('createRoot(' in harness and '<StrictMode' not in harness,
            'Actual production React root contract differs')
    product_js = [item for item in preparation['sourceEntries']
                  if item['role'] == 'current-formal-production-asset-reference-only' and item['path'].endswith('.js')]
    require(len(product_js) == 1 and product_js[0]['sha256'] ==
            '2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c',
            'Expected current formal product build binding differs')
    require(raw['runtime']['production'] is True and raw['runtime']['mode'] == 'production'
            and raw['runtime']['reactVersion'] == '19.3.0' and raw['runtime']['harnessUsesStrictMode'] is False,
            'Browser runtime does not match production React contract')
    require(raw['runtime']['loadedUrl'] == 'http://127.0.0.1:8890/react-probe-dist/', 'Actual collected URL differs')
    require(raw['status'] == 'ready' and raw['pendingDomHashes'] == 0 and not raw.get('errors'), 'Browser probe has unresolved errors')

    actions = ['initial', 'stable-camera-1', 'stable-preview-2', 'stable-box-3', 'stable-portDraft-4',
               'stable-camera-5', 'selection', 'document-replacement', 'alias-empty', 'pin', 'collapse',
               'expand', 'architecture-label', 'architecture-repeat', 'architecture-topology',
               'selection', 'tree-expand', 'tree-expand']
    rounds = raw['rounds']
    require(len(rounds) == 18 and [item['action'] for item in rounds] == actions, 'Observed action sequence differs')
    require([item['sequence'] for item in rounds] == list(range(18)), 'Round sequences are not contiguous')
    document = copy.deepcopy(fixture['document'])
    original = fixture['document']
    architecture = original['architecture']
    root = next(node for node in architecture['nodes'] if not node.get('parentId'))
    branch = next(node for node in architecture['nodes'] if len(node['children']) > 20)
    leaf = next(node for node in architecture['nodes'] if node['id'] == branch['children'][0])
    second_leaf = next(node for node in architecture['nodes'] if node['id'] == branch['children'][1])
    targets = [root['id'], branch['id'], leaf['id'], second_leaf['id']]
    require(raw['fixture']['targetIds'] == targets and raw['fixture']['nodeCount'] == 304, 'Target fixture summary differs')
    require(raw['fixture']['documentId'] == original['id'] and
            raw['fixture']['fixtureEnvelopeStorageRevision'] == fixture['revision'] and
            raw['fixture']['fixtureVisualRevision'] == original['revision'], 'Fixture identity/revisions differ')
    for key in ['sourceDigest', 'irDigest']:
        require(raw['fixture'][key] == architecture[key], f'Fixture {key} differs')
    require(raw['fixture']['sourceBindingDigest'] == original['sourceBindingDigest'], 'Fixture source binding digest differs')
    selected = []
    parent = {'camera': 0, 'preview': 0, 'box': 0, 'portDraft': 0, 'stableStep': 0}
    round_audits = []
    for index, item in enumerate(rounds):
        action = item['action']
        stable = action.startswith('stable-')
        architecture_changed = index == 0 or action.startswith('architecture-')
        expected_refs = None
        if index > 0:
            observed_input = item['input']
            require(observed_input['type'] == 'click' and observed_input['isTrusted'] is True
                    and observed_input['nativeIsTrusted'] is True, f'Round {index} is not trusted input')
            expected_source = 'old-tree' if index == 15 else 'new-tree' if index in [16, 17] else 'probe-control'
            require(observed_input['source'] == expected_source, f'Round {index} input source differs')
            selection_changed = action == 'selection'
            document_changed = not stable and not selection_changed
            expected_refs = {'architecture': not architecture_changed, 'document': not document_changed,
                             'selected': not selection_changed, 'onSelect': True, 'onExpand': True}
            expected_old_refs = {**expected_refs, 'onSelect': False, 'onExpand': False}
            require(item['inputReferencesEqualToPrior'] == {'old': expected_old_refs, 'new': expected_refs},
                    f'Round {index} reference receipt differs from code scenario')
            if stable:
                kind = action.split('-')[1]
                parent[kind] += 1
                parent['stableStep'] += 1
            elif action == 'selection':
                if index == 15:
                    callback_node = next(node for node in document['architecture']['nodes']
                                         if node['label'] == observed_input['target'])
                    selected = [callback_node['id']]
                else:
                    selected = [leaf['id']]
            elif action == 'alias-empty':
                document['displayAliases'][leaf['id']] = ''
            elif action == 'pin':
                document['pinnedObjects'] = list(dict.fromkeys([*document['pinnedObjects'], leaf['id']]))
            elif action in ['collapse', 'expand', 'tree-expand']:
                expanded = action == 'expand' or index == 17
                if expanded:
                    document['expandedIds'] = list(dict.fromkeys([*document['expandedIds'], branch['id']]))
                else:
                    document['expandedIds'] = [node_id for node_id in document['expandedIds'] if node_id != branch['id']]
            elif action == 'architecture-label':
                next(node for node in document['architecture']['nodes'] if node['id'] == root['id'])['label'] = root['label'] + ' · same-ID replacement'
            elif action == 'architecture-repeat':
                next(node for node in document['architecture']['nodes'] if node['id'] == branch['id'])['repeat'] = {'count': 299, 'sharing': 'independent'}
            elif action == 'architecture-topology':
                current_branch = next(node for node in document['architecture']['nodes'] if node['id'] == branch['id'])
                current_branch['children'].reverse()
        else:
            require(item['input'] is None and item['inputReferencesEqualToPrior'] == {'old': None, 'new': None},
                    'Initial round has an input/reference claim')
        require(item['parentState'] == parent, f'Round {index} simulated parent state differs')
        expected_counts = read_counts(document, architecture_changed)
        if stable:
            expected_counts['new'] = {'id': 0, 'label': 0, 'children': 0, 'total': 0}
        require(item['nodePropertyReads'] == expected_counts, f'Round {index} independent read counts differ')
        expected_facts = tree_facts(document, selected, targets)
        dom = item['dom']
        require(dom['oldFacts'] == expected_facts and dom['newFacts'] == expected_facts,
                f'Round {index} independent visible tree facts differ')
        require(dom['exactEqual'] is True and dom['firstMismatch'] is None
                and dom['oldLength'] == dom['newLength'] > 0,
                f'Round {index} browser exact DOM comparison differs')
        require(dom['oldSha256'] == dom['newSha256'] and bool(re.fullmatch('[0-9a-f]{64}', dom['oldSha256'])),
                f'Round {index} browser DOM digest pair differs')
        if stable:
            require(dom['oldSha256'] == rounds[0]['dom']['oldSha256'] and
                    dom['oldLength'] == rounds[0]['dom']['oldLength'], 'Stable update changed observed DOM')
        target_by_id = {target['id']: target for target in expected_facts['targets']}
        expected_checks = {
            'treesHaveExactlyEqualDom': True,
            'stableInputReferences': True if stable else None,
            'stableUpdateSkipsNewTree': True if stable else None,
            'stableUpdateReadsOldTree': True if stable else None,
            'replacementOrVisualStateRefreshesNewTree': True if index > 0 and not stable else None,
            'sourceDigestUnchanged': document['architecture']['sourceDigest'] == architecture['sourceDigest'],
            'irDigestFieldUnchanged': document['architecture']['irDigest'] == architecture['irDigest'],
            'sourceBindingDigestUnchanged': document['sourceBindingDigest'] == original['sourceBindingDigest'],
            'sourceArrayUnchangedByReference': True,
            'originalFixtureDeepFrozen': True,
            'emptyAliasRendered': target_by_id[leaf['id']]['label'] == '' if action == 'alias-empty' else None,
            'pinRendered': target_by_id[leaf['id']]['pinIcon'] if action == 'pin' else None,
            'collapsedChildrenHidden': not target_by_id[leaf['id']]['visible'] if action == 'collapse' else None,
            'expandedChildrenShown': target_by_id[leaf['id']]['visible'] if action == 'expand' else None,
            'sameIdNewLabelRendered': target_by_id[root['id']]['label'] == root['label'] + ' · same-ID replacement' if action == 'architecture-label' else None,
            'sameIdNewRepeatRendered': target_by_id[branch['id']]['repeat'] == '×299' if action == 'architecture-repeat' else None,
            'sameIdNewChildOrderRendered': expected_facts['visibleIds'].index(branch['children'][-1]) < expected_facts['visibleIds'].index(branch['children'][0]) if action == 'architecture-topology' else None,
        }
        require(item['checks'] == expected_checks, f'Round {index} browser check fields differ')
        round_audits.append({'sequence': index, 'action': action, 'propertyReadsIndependentlyExact': True,
                             'visibleTreeFactsIndependentlyExact': True,
                             'referencePatternMatchesBoundHarnessCode': True,
                             'observedExactDomComparisonAndDigestPairAgree': True,
                             'oldReads': expected_counts['old'], 'newReads': expected_counts['new'],
                             'visibleNodeCount': expected_facts['visibleNodeCount'],
                             'observedDomSha256': dom['oldSha256']})
    require(raw['currentSummary'] == {'rounds': 18, 'stableRounds': 5, 'checksPassedSoFar': True, 'allObservedDomEqual': True},
            'Recomputed browser summary differs')
    require(document['architecture']['sources'] == original['architecture']['sources'], 'Independent scenario mutated source content')
    recheck = []
    for key, first in sorted(CACHE.items()):
        last = (ROOT / key).read_bytes()
        recheck.append({'path': key, 'bytes': len(first), 'sha256': sha(first),
                        'endBytes': len(last), 'endSha256': sha(last), 'unchanged': last == first})
    require(all(item['unchanged'] for item in recheck), 'Input bytes changed during audit')
    result = {
        'schemaVersion': 1, 'status': 'passed-with-scoped-limits',
        'audit': 'independent-frozen-byte-actual-React-hierarchy-probe',
        'method': {'parseAndHashSameCachedBytes': True, 'endRecheckEveryBoundInput': True,
                   'browserExecutedByThisAudit': False, 'modelExecuted': False,
                   'independentPythonExpressionCountModel': True},
        'summary': {'rounds': 18, 'initialRounds': 1, 'stableParentRounds': 5,
                    'replacementOrVisualStateControlRounds': 9, 'actualTreeCallbackRounds': 3,
                    'trustedClicks': 17, 'trustedClickDenominator': 17,
                    'initialOldReads': 49401, 'initialNewReads': 3043,
                    'eachStableOldReads': 49401, 'eachStableNewReads': 0,
                    'selectionRefreshNewReads': 2739, 'documentReplacementNewReads': 2739,
                    'sameIdArchitectureRefreshNewReads': [3042, 3042, 3042],
                    'reportedExactDomAndEqualDigestPairs': 18,
                    'independentlyRecomputedFullDomDigests': 0,
                    'inputBindings': len(recheck), 'unchangedBindings': len(recheck),
                    'rawBytes': len(load_bytes(raw_path)), 'rawSha256': sha(load_bytes(raw_path)),
                    'actualCollectedUrl': raw['runtime']['loadedUrl']},
        'checks': {'sourceCopiesExact': True, 'archivedLegacyFunctionExact': True,
                   'currentFormalAppAndBuildBound': True, 'fixtureSourceBytesAndDigestsMatch': True,
                   'rawEmbeddedSourceAndBuildBindingsExact': True,
                   'allPropertyCountsRecomputedExactly': True, 'allVisibleTreeFactsRecomputedExactly': True,
                   'allScenarioReferencePatternsMatch': True, 'allObservedDomPairsAgree': True,
                   'allSeventeenInputReceiptsTrusted': True, 'allInputsStableAtEnd': True},
        'limitations': [
            'The complete Studio canvas path was not executed by this independent harness. The 18 rounds are initial render and React test scenarios, not 18 full Studio acceptance tasks.',
            'Raw contains browser-computed exactEqual, paired DOM SHA256/lengths, and visible tree facts, but not the 18 pairs of full innerHTML strings. This audit cannot independently recompute those DOM hashes from raw.',
            'Trusted native click fields are bound browser receipt observations, not independently re-emitted inputs. This audit performs no browser interaction.',
            'The first five controls simulate camera/preview/box/portDraft parent state while keeping tree props stable. They do not run actual canvas gestures.',
            'Architecture label/repeat/topology replacements are synthetic same-ID cloned inputs. Source bytes and existing digest fields remain unchanged; no new semantic IR/source evidence is claimed.',
            'The later old-tree Linear 3 click records a trusted callback, replacement selection references, tree refresh, and DOM digest change. The retained four target fact snapshots do not include Linear 3, so its exact aria-selected state is not independently certified here.',
            'Read counts include Proxy overhead and measure source-expression work. They are not FPS, paint, presented frames, latency, sustained performance, or human/publication acceptance.',
        ],
        'rounds': round_audits, 'inputBindings': recheck,
    }
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    text = f"""# Independent React hierarchy probe audit

Status: passed within the scope below. All {len(recheck)} input files were parsed from the same bytes used for their first SHA256 binding and were unchanged on final re-read.

The raw browser receipt contains 18 rounds: one initial render, five stable parent-state updates, nine replacement/visual-state controls, and three actual tree callbacks. All 17 input receipts record trusted native clicks. Actual collected URL: `http://127.0.0.1:8890/react-probe-dist/`.

The independent Python expression model reproduces every recorded id/label/children count and every visible tree fact. Initial old/new reads are 49,401/3,043; each of five stable updates is 49,401/0. Selection and document replacement refresh the new tree with 2,739 reads. Same-ID label/repeat/topology replacements each refresh it with 3,042 reads. The property counts include Proxy overhead and have no timing meaning.

All 18 browser-reported exact DOM comparisons and paired hashes agree. The raw receipt stores hashes, lengths and visible facts, but omits full innerHTML strings; this audit therefore does not independently re-hash the DOM itself. The 18 rounds do not establish 18 complete Studio tasks.

Archived old function bytes, current component/type/icon copies, source-bound Stress300 fixture, product App and production build, generated legacy module, compiled outputs, browser embedded bindings and preparation snapshots all match. Current formal product JS is bound to SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`. Raw is {len(load_bytes(raw_path)):,} UTF-8 bytes, SHA256 `{sha(load_bytes(raw_path))}`.

The controls simulate parent updates; they do not perform camera or node gestures. The same-ID architecture variants are synthetic inputs and preserve original source bytes/digest fields rather than claiming freshly analyzed IR. The later Linear 3 selection callback refreshes both trees, but Linear 3 is absent from the four retained target fact snapshots.

No FPS, paint, presented frames, latency, human participant, or publication approval follows from this evidence. The audit executes neither the browser nor a model.
"""
    md_output.write_text(text)
    print(json.dumps({'status': result['status'], 'summary': result['summary'],
                      'json': relative(json_output), 'jsonSha256': sha(json_output.read_bytes()),
                      'markdown': relative(md_output), 'markdownSha256': sha(md_output.read_bytes())},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
