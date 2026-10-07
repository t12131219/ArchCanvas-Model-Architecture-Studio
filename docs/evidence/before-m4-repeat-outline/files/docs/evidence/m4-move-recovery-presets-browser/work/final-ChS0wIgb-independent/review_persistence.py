"""Read-only source/file consistency audit. Does not import or run product code."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio')
BASE = ROOT / 'docs/evidence/m4-move-recovery-presets-browser/final-ChS0wIgb'
OUT = BASE.parent / 'work/final-ChS0wIgb-independent'
NS = '{http://www.w3.org/2000/svg}'
movement_stems = ['movement-final-saved', 'movement-final-reopened',
                  'movement-final-export-generated', 'pinned-move-refused-final']
cnn_stems = ['compact-cnn-observed', 'compact-cnn-generated-final']
inputs = [BASE / n for n in ['movement-final-persistence.json', 'movement-final-envelope.json',
          'movement-final-export-link.json', 'compact-cnn-envelope.json', 'compact-cnn-source.py.txt']]
inputs += [BASE / (stem + suffix) for stem in movement_stems + cnn_stems
           for suffix in ['.public.json', '.before.dom.txt', '.after.dom.txt']]
inputs += [BASE / 'movement-final-export' / n
           for n in ['document.json', 'figure.svg', 'figure.svg.receipt.json']]
STORE = ROOT / '.archcanvas/m4-move-recovery-presets-browser-2/canvas-architecture-model.MLP-3654a3534b85-ab8e9edc.json'
DRAFT_STORE = ROOT / '.archcanvas/drafts/draft-d495657a-fb6e-4c97-b899-98638ba67c0d.json'
EXPORT_STORE = ROOT / '.archcanvas/exports/d0c605adfd8a416b91271776cb1df44b'
inputs += [STORE, DRAFT_STORE] + [EXPORT_STORE / n for n in ['document.json', 'figure.svg', 'figure.svg.receipt.json']]
inputs += [ROOT / 'src/archcanvas_python/frontend.py', ROOT / 'src/archcanvas_authoring/draft.py']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def binding(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}

# First hashes precede all audit parsing in this reproducible review. Earlier discovery reads are not claimed as bound reads.
before = [binding(p) for p in inputs]
raw = {str(p): p.read_bytes() for p in inputs}

def js(path):
    return json.loads(raw[str(path)])

def canonical_digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())

def local(tag):
    return tag.rsplit('}', 1)[-1]

def metadata(root):
    return json.loads(next(x.text for x in root if local(x.tag) == 'metadata'))

def tree_value(root):
    return [root.tag, sorted(root.attrib.items()), root.text or '', root.tail or '', [tree_value(x) for x in root]]

def tree_diff(a, b, path='root'):
    result = []
    if a.tag != b.tag:
        result.append({'path': path, 'field': 'tag', 'before': a.tag, 'after': b.tag})
    if a.attrib != b.attrib:
        result.append({'path': path, 'field': 'attributes', 'before': a.attrib, 'after': b.attrib})
    if (a.text or '') != (b.text or ''):
        av, bv = a.text, b.text
        if local(a.tag) == local(b.tag) == 'metadata':
            ad, bd = json.loads(av), json.loads(bv)
            av = {k: ad.get(k) for k in ad.keys() | bd.keys() if ad.get(k) != bd.get(k)}
            bv = {k: bd.get(k) for k in ad.keys() | bd.keys() if ad.get(k) != bd.get(k)}
        result.append({'path': path, 'field': 'text', 'before': av, 'after': bv})
    if len(a) != len(b):
        result.append({'path': path, 'field': 'childCount', 'before': len(a), 'after': len(b)})
    for i, (x, y) in enumerate(zip(a, b)):
        result.extend(tree_diff(x, y, path + '/' + str(i) + ':' + local(x.tag)))
    return result

def node_groups(root):
    return {x.get('data-node-id'): x for x in root.iter() if x.get('data-canonical-id')}

def port_circles(root):
    result = {}
    for x in root.iter():
        key = x.get('data-port-id')
        if not key:
            continue
        circle = x if local(x.tag) == 'circle' else next((y for y in x if local(y.tag) == 'circle' and y.get('fill') != 'transparent'), None)
        if circle is not None:
            result[key] = {k: circle.get(k) for k in ['cx', 'cy', 'r', 'fill']}
    return result

def edge_groups(root):
    return {x.get('data-edge-id'): tree_value(x) for x in root.iter() if x.get('data-edge-id')}

public = {s: js(BASE / (s + '.public.json')) for s in movement_stems + cnn_stems}
dom = {s: {t: raw[str(BASE / (s + '.' + t + '.dom.txt'))].decode() for t in ['before', 'after']}
       for s in movement_stems + cnn_stems}
docenv = js(BASE / 'movement-final-envelope.json')
doc = docenv['document']
architecture = doc['architecture']
claim = js(BASE / 'movement-final-persistence.json')
saved_svg = public['movement-final-saved']['svg']
reopened_svg = public['movement-final-reopened']['svg']
root_svg = ET.fromstring(saved_svg)
meta = metadata(root_svg)
exp_doc = js(BASE / 'movement-final-export/document.json')
exp_svg_raw = raw[str(BASE / 'movement-final-export/figure.svg')]
exp_svg = ET.fromstring(exp_svg_raw)
exp_meta = metadata(exp_svg)
receipt = js(BASE / 'movement-final-export/figure.svg.receipt.json')
semantic_nodes = []
for n in architecture['nodes']:
    item = {k: v for k, v in n.items() if k not in ('source', 'parameterOrigins')}
    if 'parameterOrigins' in n:
        item['parameterOrigins'] = {name: {k: origin[k] for k in ('kind', 'expression', 'path')}
                                    for name, origin in n['parameterOrigins'].items()}
    semantic_nodes.append(item)
source_calculated = canonical_digest([{k: v for k, v in s.items() if k != 'content'} for s in architecture['sources']])
ir_calculated = canonical_digest({'entry': architecture['entry'], 'nodes': semantic_nodes, 'edges': architecture['edges']})
source_rows = [{'path': s['path'], 'contentBytes': len(s['content'].encode()),
                'claimedDigest': s['digest'], 'calculatedDigest': sha(s['content'].encode()),
                'matches': sha(s['content'].encode()) == s['digest']} for s in architecture['sources']]
source_facts = {x['id']: x for x in meta['sourceFacts']}
source_fact_checks = []
for n in architecture['nodes']:
    fact = source_facts.get(n['id'], {})
    fields = {'sourceLabel': n['label'], 'kind': n['kind'], 'category': n['category'],
              'evidence': n['evidence'], 'source': n['source']}
    source_fact_checks.append({'nodeId': n['id'], 'fields': fields,
                               'matches': all(fact.get(k) == v for k, v in fields.items())})
bindings_checks = []
arch_edges = {e['id']: e for e in architecture['edges']}
for b in meta['renderedBindings']:
    e = arch_edges[b['sceneEdgeId']]
    fields = ['source', 'target', 'tensorId', 'role']
    bindings_checks.append({'sceneEdgeId': b['sceneEdgeId'], 'canonicalEdgeIds': b['canonicalEdgeIds'],
                            'matches': b['canonicalEdgeIds'] == [e['id']] and all(b.get(k) == e.get(k) for k in fields)})
scene_nodes = node_groups(root_svg)
export_nodes = node_groups(exp_svg)
node_rects = lambda group: [x.attrib for x in group if local(x.tag) == 'rect']
node_body_checks = [{'nodeId': key, 'ariaLabel': value.get('aria-label'),
                     'exportAriaLabel': export_nodes.get(key, ET.Element('missing')).get('aria-label'),
                     'rectAttributesEqual': key in export_nodes and node_rects(value) == node_rects(export_nodes[key])}
                    for key, value in scene_nodes.items()]
export_diff = tree_diff(root_svg, exp_svg)
pin_root = ET.fromstring(public['pinned-move-refused-final']['svg'])
pin_delta = tree_diff(ET.fromstring(reopened_svg), pin_root)
pin_normalized = copy.deepcopy(pin_root)
pin_normalized.set('data-revision', '17')
pin_normalized.find(NS + 'metadata').text = root_svg.find(NS + 'metadata').text
pin_controls = {s: {t: {'cancelPinControl': 'button "取消固定位置"' in txt,
                        'aliasTextbox': 'textbox "显示名称": 首层·可修复' in txt,
                        'refusalFooter': '选中对象或其内部对象已固定。取消固定后再预览位置修复。' in txt}
                    for t, txt in dom[s].items()} for s in ['movement-final-saved', 'pinned-move-refused-final']}

cnn_env = js(BASE / 'compact-cnn-envelope.json')
cnn = cnn_env['draft']
cnn_source = raw[str(BASE / 'compact-cnn-source.py.txt')].decode()
syntax = ast.parse(cnn_source)
class_node = next(x for x in syntax.body if isinstance(x, ast.ClassDef))
init = next(x for x in class_node.body if isinstance(x, ast.FunctionDef) and x.name == '__init__')
forward = next(x for x in class_node.body if isinstance(x, ast.FunctionDef) and x.name == 'forward')
constructors = {x.targets[0].attr: x.value for x in init.body
                if isinstance(x, ast.Assign) and isinstance(x.targets[0], ast.Attribute)}
forward_assignments = {x.targets[0].id: x.value for x in forward.body
                       if isinstance(x, ast.Assign) and isinstance(x.targets[0], ast.Name)}
hashed_name = lambda identity: 'node_' + hashlib.sha256(identity.encode()).hexdigest()[:16]
cnn_node_rows = []
for n in cnn['nodes']:
    name = hashed_name(n['id'])
    row = {'nodeId': n['id'], 'kind': n['kind'], 'sourceName': name}
    if n['kind'] == 'Input':
        row['forwardArgumentMatches'] = name in [x.arg for x in forward.args.args]
        row['inputShapeEncodedInSource'] = False
        row['inputShapeNote'] = 'Input shape is saved in draft; generated forward signature does not encode shape.'
    elif n['kind'] == 'Output':
        returns = [x.value for x in forward.body if isinstance(x, ast.Return)]
        result = returns[0]
        row['outputKeyMatches'] = isinstance(result, ast.Dict) and n['id'] in [ast.literal_eval(k) for k in result.keys]
    else:
        call = constructors.get(name)
        row['constructorKind'] = ast.unparse(call.func) if call else None
        row['kindMatches'] = bool(call and isinstance(call.func, ast.Attribute) and call.func.attr == n['kind'])
        kwargs = {x.arg: ast.literal_eval(x.value) for x in call.keywords if x.arg != 'dtype'} if call else {}
        row['constructorParameters'] = kwargs
        row['draftParameters'] = n['parameters']
        row['parametersMatch'] = kwargs == n['parameters']
        row['generatedDtype'] = next((ast.unparse(x.value) for x in call.keywords if x.arg == 'dtype'), None) if call else None
    cnn_node_rows.append(row)
cnn_edge_rows = []
outputs = {n['id'] for n in cnn['nodes'] if n['kind'] == 'Output'}
return_dict = next(x.value for x in forward.body if isinstance(x, ast.Return))
return_map = {ast.literal_eval(k): ast.unparse(v) for k, v in zip(return_dict.keys, return_dict.values)}
for e in cnn['edges']:
    source_name = hashed_name(e['source']['nodeId'])
    target = e['target']['nodeId']
    if target in outputs:
        observed = return_map.get(target)
    else:
        call = forward_assignments.get(hashed_name(target))
        observed = ast.unparse(call.args[0]) if call and call.args else None
    cnn_edge_rows.append({'edgeId': e['id'], 'source': e['source'], 'target': e['target'],
                          'expectedSourceName': source_name, 'observedSourceName': observed,
                          'matches': observed == source_name})
cnn_public_rows = []
for stem in cnn_stems:
    root = ET.fromstring(public[stem]['draftSvg'])
    groups = {x.get('data-draft-node'): x for x in root.iter() if x.get('data-draft-node')}
    edge_ids = [x.get('data-draft-edge') for x in root.iter() if x.get('data-draft-edge')]
    cnn_public_rows.append({'stem': stem, 'nodeIdsExact': set(groups) == {n['id'] for n in cnn['nodes']},
                            'edgeIdsExact': set(edge_ids) == {e['id'] for e in cnn['edges']},
                            'positionChecks': [{'nodeId': n['id'],
                              'expectedTransform': f"translate({n['position']['x']} {n['position']['y']})",
                              'observedTransform': groups.get(n['id'], ET.Element('missing')).get('transform'),
                              'matches': groups.get(n['id'], ET.Element('missing')).get('transform') == f"translate({n['position']['x']} {n['position']['y']})"}
                              for n in cnn['nodes']],
                            'footer': public[stem]['footer'], 'scriptAssets': public[stem]['scripts']})

source_text_dialog_checks = {'publicDialogContainsExactStrippedSource': any(cnn_source.strip() in x for x in public['compact-cnn-generated-final']['dialog']),
    'beforeDomContainsDialogTitle': '模型已生成并静态核对' in dom['compact-cnn-generated-final']['before'],
    'afterDomContainsDialogTitle': '模型已生成并静态核对' in dom['compact-cnn-generated-final']['after'],
    'generatedSourceAstParsedOnly': True}

report = {
 'schemaVersion': 1,
 'scope': 'Read-only final-ChS0wIgb movement rev17 save/reopen/export, later rev18 selected-pin refusal, and compact CNN saved draft/generated source correspondence.',
 'method': {'networkBrowserProductOperations': False, 'productCodeExecuted': False, 'actualImageViews': 0,
            'firstHashBeforeAuditParsing': True, 'discoveryReadsPrecededInitialBinding': True,
            'sourceDigestAlgorithmReference': 'src/archcanvas_python/frontend.py:28 and :1019',
            'sourceNameAlgorithmReference': 'src/archcanvas_authoring/draft.py:463',
            'certifies': 'Captured JSON/XML and copied/live file correspondence only.',
            'doesNotCertify': ['capture acquisition method or timestamps', 'browser/service operation history',
                'runtime/model execution correctness', 'storage atomicity or persistence under restart/crash',
                'human or pixel acceptance', 'all pin configurations', 'publication readability or typography']},
 'inputBindings': before,
 'movement': {
   'storeEnvelopeBytesExact': raw[str(STORE)] == raw[str(BASE / 'movement-final-envelope.json')],
   'storeEnvelopeJsonExact': js(STORE) == docenv,
   'storeEnvelopeRevision': docenv['revision'], 'documentRevision': doc['revision'],
   'sourceContentDigests': source_rows,
   'sourceDigest': {'claimed': architecture['sourceDigest'], 'calculated': source_calculated,
                    'matches': architecture['sourceDigest'] == source_calculated},
   'sourceBindingDigestMatchesArchitecture': doc['sourceBindingDigest'] == architecture['sourceDigest'],
   'irDigest': {'claimed': architecture['irDigest'], 'calculated': ir_calculated,
                'matches': architecture['irDigest'] == ir_calculated},
   'savedReopenedSvgExact': saved_svg == reopened_svg,
   'savedSvgCharacters': len(saved_svg), 'savedSvgUtf8Bytes': len(saved_svg.encode()), 'savedSvgSha256': sha(saved_svg.encode()),
   'exportDialogPublicSvgExact': public['movement-final-export-generated']['svg'] == saved_svg,
   'publicRevisionSceneFacts': [{ 'stem': s, 'committedRevision': public[s]['committedRevision'],
       'sceneKind': public[s]['sceneKind'], 'footer': public[s]['footer'], 'scripts': public[s]['scripts']}
       for s in movement_stems],
   'metadataMatchesDocument': {k: meta.get(k) == v for k,v in {
       'documentId': doc['id'], 'revision': doc['revision'], 'sourceDigest': architecture['sourceDigest'], 'irDigest': architecture['irDigest']}.items()},
   'sourceFactChecks': source_fact_checks, 'renderedBindingChecks': bindings_checks,
   'sourceFactNodeCount': len(source_facts), 'renderedNodeCount': len(meta['renderedNodes']),
   'renderedBindingCount': len(meta['renderedBindings']),
   'savedPins': doc['pinnedObjects'], 'savedAliases': doc['displayAliases'],
   'aliasSvgAriaLabel': scene_nodes['call:instance:model.MLP.network.0'].get('aria-label'),
   'canonicalSourceLabel': source_facts['call:instance:model.MLP.network.0']['sourceLabel'],
   'producerClaimRecomputed': {'savedReopenedSvgExact': claim['savedReopenedSvgExact'] == (saved_svg == reopened_svg),
       'svgChars': claim['svgChars'] == len(saved_svg), 'savedDocumentRevision': claim['savedDocumentRevision'] == doc['revision'],
       'exportDocumentExact': claim['exportDocumentExact'] == (exp_doc == doc), 'pinIds': claim['pinIds'] == doc['pinnedObjects'],
       'alias': claim['alias'] == doc['displayAliases'], 'sourceDigest': claim['sourceDigest'] == source_calculated,
       'irDigest': claim['irDigest'] == ir_calculated}},
 'export': {'documentJsonExactSavedDocument': exp_doc == doc,
   'copiedFilesBytesExactLiveExport': {n: raw[str(BASE / 'movement-final-export' / n)] == raw[str(EXPORT_STORE / n)]
       for n in ['document.json', 'figure.svg', 'figure.svg.receipt.json']},
   'linkUrl': js(BASE / 'movement-final-export-link.json')['url'],
   'receiptPathMatchesLiveExport': receipt['path'] == str(EXPORT_STORE / 'figure.svg'),
   'receiptInputDigestMatchesPublicScene': receipt['inputSvgDigest'] == sha(saved_svg.encode()),
   'receiptSceneDigestMatchesPublicScene': receipt['sceneSvgDigest'] == sha(saved_svg.encode()),
   'receiptOutputDigestMatchesFile': receipt['outputDigest'] == sha(exp_svg_raw),
   'receiptSvgDigestMatchesFile': receipt['svgDigest'] == sha(exp_svg_raw),
   'receiptBytesMatchesFile': receipt['bytes'] == len(exp_svg_raw),
   'receiptInputSvgDigest': receipt['inputSvgDigest'], 'receiptSceneSvgDigest': receipt['sceneSvgDigest'],
   'capturedPublicSvgDigest': sha(saved_svg.encode()),
   'inputDigestDiscrepancy': 'The receipt inputSvgDigest/sceneSvgDigest do not equal captured public SVG UTF8 digest. No raw pre-export input SVG is supplied in this scope, so the precise cause and intended input byte correspondence remain unverified. Metadata and body/edge/visible-port correspondence do not remove this byte-binding gap.',
   'outputBytes': len(exp_svg_raw), 'outputSha256': sha(exp_svg_raw),
   'receiptMetadataIdentityChecks': {k: receipt.get(k) == meta.get(k) for k in ['documentId','revision','sourceDigest','irDigest','renderer']},
   'metadataJsonExactPublicScene': exp_meta == meta,
   'publicExportBytesExact': saved_svg.encode() == exp_svg_raw,
   'nodeBodyChecks': node_body_checks, 'edgeGroupsExact': edge_groups(root_svg) == edge_groups(exp_svg),
   'visiblePortCircleCoordinatesAndStyleExact': port_circles(root_svg) == port_circles(exp_svg),
   'visiblePortCircles': {'public': port_circles(root_svg), 'export': port_circles(exp_svg)},
   'transparentPortHitCircles': {'public': sum(local(x.tag) == 'circle' and x.get('fill') == 'transparent' for x in root_svg.iter()),
                                 'export': sum(local(x.tag) == 'circle' and x.get('fill') == 'transparent' for x in exp_svg.iter())},
   'wrapperAndInteractionXmlDifferences': export_diff,
   'differenceInterpretation': 'Export has more precise root height, removes node focus/button roles and container detail controls, moves network ×4 text x339→369, and replaces 11 interactive port groups (including transparent r8 hit circles) with publication circles/titles. Metadata, node body rects, aliases, six edge groups, and visible r2.6 port circle coordinates/styles are preserved. Exact whole-XML or whole-pixel equivalence is not asserted.'},
 'pinRefusal': {'baseRevision': 17, 'refusalRevision': 18, 'xmlDifferences': pin_delta,
   'xmlExactAfterOnlyRevisionNormalization': tree_value(pin_normalized) == tree_value(root_svg),
   'domControls': pin_controls,
   'postRefusalExactPinIdsCertified': False,
   'limitation': 'Public SVG omits pinnedObjects, and no rev18 envelope is in this scope. Selected object still has cancel-pin control and alias, refusal footer is present, and all XML geometry/content stays exact apart from two revision fields. This does not establish the complete post-refusal pin array or history internals.'},
 'compactCnn': {'draftId': cnn['id'], 'storageRevision': cnn_env['revision'], 'draftRevision': cnn['revision'],
   'savedEnvelopeBytesExactLiveDraft': raw[str(BASE / 'compact-cnn-envelope.json')] == raw[str(DRAFT_STORE)],
   'savedEnvelopeJsonExactLiveDraft': cnn_env == js(DRAFT_STORE),
   'nodes': len(cnn['nodes']), 'edges': len(cnn['edges']),
   'sourceBytes': len(cnn_source.encode()), 'sourceSha256': sha(cnn_source.encode()),
   'className': class_node.name, 'nodeSourceChecks': cnn_node_rows, 'edgeSourceChecks': cnn_edge_rows,
   'publicDraftChecks': cnn_public_rows, 'dialogSourceChecks': source_text_dialog_checks,
   'independentGeneratedIrFilePresent': False, 'generatedExportCopyPresent': False,
   'limitation': 'This scope contains generated source and modal text, not a saved generated-model IR or a compact-CNN export copy. Constructor parameter and seven DAG connection correspondences are checked statically by parsing source; dialog claim of product static verification is not independently rerun or certified. Shape/dtype/runtime semantics are not execution-verified.'},
 'sameStemDomPairs': [{'stem': s, 'byteExact': raw[str(BASE/(s+'.before.dom.txt'))] == raw[str(BASE/(s+'.after.dom.txt'))]}
                      for s in movement_stems + cnn_stems],
 'excluded': ['All PNG files; actual viewing assigned to parent.', 'Historical session-2 draft/generation/export records; not mixed into current build.',
              'Moving journals, manifests, aggregate acceptance documents, or product edits.']
}
after = [binding(p) for p in inputs]
report['sourceRecheck'] = {'inputCount': len(before), 'unchangedCount': sum(a == b for a,b in zip(before,after)),
                         'changedInputs': [{'before': a, 'after': b} for a,b in zip(before,after) if a != b],
                         'allUnchanged': before == after}
report['summary'] = {
 'movementProducerClaimFieldsMatched': sum(report['movement']['producerClaimRecomputed'].values()),
 'savedReopenedSceneExact': saved_svg == reopened_svg,
 'exportWholeBytesExactToScene': saved_svg.encode() == exp_svg_raw,
 'exportWholeBytesDifferenceFullyListed': True,
 'fileCopyMismatches': sum(not v for v in report['export']['copiedFilesBytesExactLiveExport'].values()),
 'receiptInputDigestMatchesCapturedPublicSvg': receipt['inputSvgDigest'] == sha(saved_svg.encode()),
 'receiptSceneDigestMatchesCapturedPublicSvg': receipt['sceneSvgDigest'] == sha(saved_svg.encode()),
 'cnnConstructorParameterMismatches': sum(not r.get('parametersMatch', True) for r in cnn_node_rows),
 'cnnSourceEdgeMismatches': sum(not r['matches'] for r in cnn_edge_rows),
 'uncertifiedPostRefusalFullPinArray': True,
 'runtimeVerified': False, 'humanAccepted': False
}
OUT.mkdir(parents=True, exist_ok=True)
dest = OUT / 'persistence-source-review.json'
dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
md = '''# final-ChS0wIgb 文件与来源独立复核

范围仅为新冻结目录的 rev17 保存/重开/SVG 导出、随后 rev18 单个已固定对象拒绝状态，以及紧凑 CNN 草稿/生成源码。未操作浏览器、服务、产品或原始证据；未查看 PNG。历史 session-2 未混入新 build。

- movement 冻结 envelope 与实际 `.archcanvas/m4-move-recovery-presets-browser-2` 保存文件字节完全一致：存储 revision=2、文档 revision=17。嵌入源码字节 SHA、source 集合 digest 与 IR digest 重新计算均对应。
- saved/reopened/export-dialog 的 public SVG 字符串完全一致，20687 字符；pins 为一个明确 ID，别名为“首层·可修复”。8 个 sourceFacts 与 6 个 renderedBindings 的逐字段来源对应成立，源标签仍为 Linear 1。
- 导出 document 全对象等于保存 document；导出三文件与 receipt 指向的实际存储文件字节相同，输出摘要和 bytes 对应。但 receipt 的 inputSvgDigest/sceneSvgDigest 为 `5dfa9535…`，captured public SVG UTF8 SHA 为 `58b0cb64…`，两项输入字节绑定不成立；没有原始 pre-export input SVG，未推断原因。导出 SVG 与画布 SVG 非字节/全 XML 完全相同：高度精度、交互属性/容器详情控件、×4 文本横坐标及端口包装变化完整保留在 JSON。metadata、节点主体 rect、别名、6 组连线及 11 个可见端口圆坐标/样式一致，透明 hitcircle 已删。
- pinned refusal 从 rev17 到 rev18，XML 只有 root data-revision 与 metadata revision 两处变化；其余树完全相同，DOM 保留别名及“取消固定位置”控件并有拒绝 footer。没有 rev18 envelope，public 不含 pinnedObjects，因此未认证完整 post-refusal pin 数组或历史内部状态。
- compact CNN 冻结 envelope 与实际 draft 保存文件字节完全一致，8 模块/7 连接、draft/storage revision=1。独立 AST 静态检查核对 6 个模块构造参数、输入/输出命名及 7 条源码连接；observed/generated 的 public SVG ID 和节点位置对应草稿。生成 modal 的 public 文本含完整源码。未提供独立 generated IR 或 compact CNN export copy；没有运行产品核验或模型执行。

绑定 33 个原始输入，末复核全部未变化。详细字段、完整 XML 差异、原始 bytes/SHA 和限定见同名 JSON；发现的 whole-export XML 差异与 post-refusal 完整 pin 缺口均未消除。

本复核只建立记录及文件内容对应，不认证采集方法/时序、保存操作链或重启/故障持久性、模型 runtime、全部固定压力、像素/字体/物理阅读效果或人类验收。此前 discovery 读取早于绑定；本脚本的 first hash 早于 audit parsing。
'''
md = md.replace('绑定 33 个', f'绑定 {len(before)} 个')
(OUT / 'persistence-source-review.md').write_text(md)
print(json.dumps({'inputCount': len(before), 'sourceRecheck': report['sourceRecheck'], 'summary': report['summary'],
                  'report': binding(dest), 'markdown': binding(OUT / 'persistence-source-review.md')}, ensure_ascii=False))
