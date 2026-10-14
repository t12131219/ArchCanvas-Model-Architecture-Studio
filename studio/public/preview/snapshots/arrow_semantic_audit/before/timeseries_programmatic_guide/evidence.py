"""Read and freeze reviewed source evidence without importing model code."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def walk(tree):
    yield tree
    for child in tree.get('items', []):
        yield from walk(child)


def collect(model, archive_dir, out):
    archive = Path(archive_dir) / model['archive']
    reviewed = json.loads((HERE / 'reviewed_archives.json').read_text())
    archive_hash = digest(archive.read_bytes())
    if archive_hash != reviewed[model['archive']]:
        raise ValueError(f'{archive.name}: archive changed; review and update adapter before drawing')
    needed = set()
    for node in list(walk(model['tree'])) + [n for aux in model.get('aux_inputs',[]) for n in walk(aux)]:
        needed.update(node['source'])
    for path, symbols in model.get('symbols', {}).items():
        needed.update(path + '::' + symbol for symbol in symbols)
    files, spans = {}, {}
    with zipfile.ZipFile(archive) as z:
        for member in sorted({s.split('::')[0] for s in needed} | set(model.get('config_files',[]))):
            path = Path(member)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe evidence path: ' + member)
            data = z.read(member)
            source = data.decode('utf-8-sig')
            tree = ast.parse(source, filename=member) if member.endswith('.py') else ast.Module(body=[],type_ignores=[])
            symbols = {}
            for item in tree.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols[item.name] = item
                    if isinstance(item, ast.ClassDef):
                        for method in item.body:
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                symbols[item.name + '.' + method.name] = method
            lines = source.splitlines()
            files[member] = dict(sha256=digest(data), lines=len(lines), configuration_reference=member in model.get('config_files',[]))
            for name, item in symbols.items():
                key = member + '::' + name
                if key in needed:
                    spans[key] = dict(path=member, symbol=name, start=item.lineno, end=item.end_lineno,
                                      snippet='\n'.join(lines[item.lineno-1:item.end_lineno]))
            target = out / 'sources' / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    missing = needed - spans.keys()
    if missing:
        raise ValueError('Missing source symbol(s): ' + repr(sorted(missing)))
    for i, key in enumerate(sorted(spans), 1):
        spans[key]['evidence_id'] = f'E{i:03d}'
    return dict(archive=model['archive'], archive_sha256=archive_hash, entry=model['entry'],
                mode='static AST + reviewed handwritten adapter; model code never imported or executed',
                files=files, symbols=spans)


def semantic_ir(model, evidence):
    nodes, edges = [], []
    def edge(src, dst, role='tensor', sp='out', dp='in'):
        edges.append(dict(id=f'{src}:{sp}->{dst}:{dp}:{role}', src=src, dst=dst,
                          src_port=sp, dst_port=dp, role=role))
    def visit(node, parent=None):
        nodes.append({k:v for k,v in node.items() if k not in ('items','expand','width','fold_inline')} | dict(parent=parent,
                     source_evidence=[evidence['symbols'][s]['evidence_id'] for s in node['source']],
                     ports=['in','out']))
        children = node.get('items', [])
        for child in children:
            visit(child, node['id'])
        if not children:
            return
        if node['mode'] == 'chain':
            # Container boundary edges are explicit, not runtime tensor observations.
            edge(node['id'], children[0]['id'], 'boundary', 'in', 'in')
            for a,b in zip(children,children[1:]):
                edge(a['id'], b['id'], node.get('flow_role', 'tensor'))
            edge(children[-1]['id'], node['id'], 'boundary', 'out', 'out')
            if node.get('residual') or node.get('retained_input'):
                edge(node['id'], children[-1]['id'], 'residual' if node.get('residual') else 'retained_input', 'in', 'side')
        else:
            for i,child in enumerate(children):
                selector = child.get('input_selector', f'item[{i}]' if node.get('dispatch') else 'in')
                edge(node['id'], child['id'], 'dispatch' if node.get('dispatch') else 'fork', selector, 'in')
                edge(child['id'], node['id'], 'tuple_collection', 'out', f'item[{i}]')
    visit(model['tree'])
    for node in model.get('aux_inputs', []):
        visit(node)
    for extra in model.get('extra_edges', []):
        edge(extra['src'],extra['dst'],extra.get('role','tensor'),extra.get('src_port','out'),extra.get('dst_port','side'))
    index = {n['id']: n for n in nodes}
    if len(index) != len(nodes):
        raise ValueError('Duplicate semantic identity')
    for e in edges:
        for which in ('src','dst'):
            if e[which] not in index:
                raise ValueError('Unknown edge endpoint: ' + e[which])
            port = e[which+'_port']
            if port not in index[e[which]]['ports']:
                index[e[which]]['ports'].append(port)
    return dict(schema='timeseries-semantic-ir/1', model=model['key'], profile=model['profile'],
                nodes=nodes, edges=edges, facts=model['facts'], corrections=model['corrections'],
                semantics='reviewed static adapter; selected profile; boundary and tuple edges explicit')
