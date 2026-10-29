#!/usr/bin/env python3
"""Extract portable source components from native semantic facts.

This is an explicit build step, never a dependency on the open Studio document.
Matching is deliberately conservative: ordered graph facts, not Python equivalence.
"""
import ast
import copy
import hashlib
import json
from collections import defaultdict

SCHEMA = 'archcanvas-source-components/1'


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


def fingerprints(module):
    """Ignore instance spelling/provenance; keep operators, slots and sharing.

    Families ignore constructor/argument literal values, variants retain them.
    Unknown facts stay in the signature, so a new parser field cannot silently
    broaden equivalence. Node order is retained (no speculative graph isomorphism).
    """
    nodes, edges = module['ir']['nodes'], module['ir']['edges']
    ids = {n['id']: f'n{i}' for i, n in enumerate(nodes)}
    ids.update({e['id']: f'e{i}' for i, e in enumerate(edges)})
    names, identities, scopes = {}, {}, {}

    def symbol(value, table):
        return table.setdefault(value, f'v{len(table)}')

    class Alpha(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id not in {'torch', 'nn', 'F', 'math', 'True', 'False', 'None'}:
                node.id = symbol(node.id, names)
            return node

    def expression(value):
        try:
            return ast.dump(Alpha().visit(ast.parse(value)), include_attributes=False)
        except (SyntaxError, ValueError):
            # Truncated/unrecognized syntax remains exact, rather than guessed.
            return value

    ignored = {'id', 'label', 'source', 'source_parent', 'glyph', 'runtime_evidence',
               'module_binding', 'source_class', 'module_path', 'motif', 'reason',
               'semantic_type', 'repeat_index'}

    def normalize(value, key=''):
        if isinstance(value, dict):
            return {k: normalize(v, k) for k, v in sorted(value.items())}
        if isinstance(value, list):
            return [normalize(v, key) for v in value]
        if isinstance(value, str):
            if value in ids:
                return ids[value]
            if key in {'module_identity', 'reference', 'instances'}:
                return symbol(value, identities)
            if key in {'parameter_scope', 'effect_scope'}:
                return symbol(value, scopes)
            if key in {'unresolved', 'syntax', 'expression'}:
                return expression(value)
        return value

    facts = []
    for n in nodes:
        fact = normalize({k: v for k, v in n.items() if k not in ignored})
        if n['kind'] == 'opaque':
            fact['opaque_source'] = [expression(s.get('expression', '')) for s in n.get('source', [])]
        facts.append(fact)
    links = [normalize({k: v for k, v in e.items() if k not in {'id', 'source_refs', 'runtime_evidence'}}) for e in edges]
    exact = [facts, links]

    def shape(value, parameters=False):
        if isinstance(value, dict):
            return {k: shape(v, parameters or k in {'constructor', 'arguments'}) for k, v in value.items()}
        if isinstance(value, list):
            return [shape(v, parameters) for v in value]
        if parameters and isinstance(value, (int, float)) and not isinstance(value, bool):
            return '<number>'
        return value

    return digest(shape(exact)), digest(exact)


def source_only(n):
    return n.get('evidence_status') != 'runtime-only' and not n['id'].startswith('runtime')


def candidates(ir):
    for n in ir['nodes']:
        if not source_only(n):
            continue
        if n['kind'] == 'composite' and (n.get('source_class') or n.get('semantic_type') == 'source-function' or n.get('motif')):
            yield n
        elif n['kind'] == 'compute' and (n.get('framework_type') or n.get('function_target', '').startswith(('torch.', 'math.'))):
            yield n


def short_name(node):
    raw = node.get('source_class') or node.get('framework_type') or node.get('function_target') or node['label']
    name = raw.removeprefix('self.').split('.')[-1]
    return name



def extract(ir, node):
    """Close descendants and resources; expose crossing slots as real interfaces.

    Original node/edge identities and source records remain provenance. Only the
    detached root name/parent and synthetic boundary interfaces are new facts.
    """
    eligible = [n for n in ir['nodes'] if source_only(n)]
    children = defaultdict(list)
    for n in eligible:
        children[n.get('parent')].append(n['id'])
    inside = {node['id']}
    todo = [node['id']]
    for ident in todo:
        for child in children[ident]:
            if child not in inside:
                inside.add(child)
                todo.append(child)
    original_inside = set(inside)
    by = {n['id']: n for n in eligible}
    # A standalone atom must keep the declared resource it reads.
    for e in ir['edges']:
        if e['target'] in inside and e['kind'] == 'parameter-read' and e['source'] in by:
            inside.add(e['source'])
    nodes = copy.deepcopy([n for n in eligible if n['id'] in inside])
    links = copy.deepcopy([e for e in ir['edges'] if e['source'] in inside and e['target'] in inside])
    title = short_name(node)
    root_id = node['id'] if node['kind'] == 'composite' else 'component:root'
    if node['kind'] != 'composite':
        nodes.insert(0, dict(id=root_id, kind='composite', label=title, parent=None,
                             semantic_type='source-library-component', granularity='composite',
                             evidence_status='declared', source=[]))
    for n in nodes:
        n['runtime_evidence'] = []
        if n.get('evidence_status') == 'source-runtime-associated':
            n['evidence_status'] = 'static-only'
        if n['id'] == root_id:
            n['parent'] = None
            n['label'] = title
        elif n.get('parent') not in inside:
            n['parent'] = root_id
    boundary = [e for e in ir['edges'] if (e['source'] in inside) != (e['target'] in inside)
                and e['source'] in by and e['target'] in by
                and not (e['source'] in inside - original_inside and e['target'] not in inside)]
    ports = {}
    for original in boundary:
        incoming = original['target'] in inside
        terminal = by[original['target'] if incoming else original['source']]
        if terminal['kind'] == 'interface' and terminal.get('parent') == root_id and terminal.get('role') == ('input' if incoming else 'output'):
            continue  # The source module already declares this public port.
        # Shared external producers remain one input with the same fan-out.
        key = ('input' if incoming else 'output', original['source'], original['source_port'])
        if key not in ports:
            ident = 'component:port:' + str(len(ports))
            label = str(original['target_port'] if incoming else original['source_port'])
            ports[key] = ident
            nodes.append(dict(id=ident, kind='interface', label=label, parent=root_id,
                              role=key[0], slot=label, granularity='atomic', source=[], evidence_status='declared'))
        e = copy.deepcopy(original)
        e['id'] = 'component:edge:' + str(len(links))
        if incoming:
            e['source'], e['source_port'] = ports[key], 'out'
        else:
            e['target'], e['target_port'] = ports[key], 'in'
            e['kind'], e['evidence'] = 'data', 'source-library-boundary'
            if any(x['source'] == e['source'] and x['target'] == e['target'] and x['source_port'] == e['source_port'] for x in links):
                continue
        links.append(e)
    used_files = {s['file'] for n in nodes for s in n.get('source', []) if 'file' in s}
    return dict(schema='semantic-module/1', title=title, entry=None, constructor=copy.deepcopy(node.get('constructor', {})),
                ir=dict(schema='archcanvas-source-semantic/2', title=title, nodes=nodes, edges=links,
                        sources=copy.deepcopy([s for s in ir.get('sources', []) if s['path'] in used_files])),
                sourceBoundary=copy.deepcopy(boundary))


def validate_module(module):
    """Validate detached authoring boundaries (including declared interfaces).

    These are editable components, not sealed, executable source documents.
    Match SemanticEngine's hierarchy and endpoint checks without pretending
    synthetic boundary ports were statements in the user's Python source.
    """
    ir = module['ir']
    nodes = {n['id']: n for n in ir['nodes']}
    if ir.get('schema') != 'archcanvas-source-semantic/2' or len(nodes) != len(ir['nodes']):
        raise ValueError('Invalid component schema or duplicate node IDs.')
    for node in nodes.values():
        seen, current = set(), node
        while current:
            if current['id'] in seen:
                raise ValueError('Cyclic component hierarchy.')
            seen.add(current['id'])
            parent = current.get('parent')
            if parent and parent not in nodes:
                raise ValueError('Missing component parent.')
            current = nodes.get(parent)
    edges = set()
    for edge in ir['edges']:
        if edge['id'] in edges or edge['source'] not in nodes or edge['target'] not in nodes:
            raise ValueError('Invalid component edge.')
        edges.add(edge['id'])
    return True
