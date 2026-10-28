"""Small, versioned dataflow rules. Names alone never certify model semantics."""
from .schema import GLYPHS


def recognize(ir):
    nodes, edges = ir['nodes'], ir['edges']
    by = {n['id']: n for n in nodes}
    outgoing = {}
    for e in edges:
        if e['kind'] in {'data', 'alias', 'interface-binding'}:
            outgoing.setdefault(e['source'], []).append(e['target'])
    motifs = []

    def add(kind, members, evidence, parent=None, promote=False):
        identity = 'motif:' + kind + ':' + str(len(motifs))
        members = list(dict.fromkeys(members))
        motif = {'id': identity, 'semantic_type': kind, 'members': members, 'evidence': evidence,
                 'confidence': 'rule-confirmed', 'rule_version': 'dataflow-motifs/1'}
        motifs.append(motif)
        if promote and len(members) > 1 and all(by[m].get('parent') == parent for m in members):
            source = list({(s['file'], s['line'], s['column']): s for m in members for s in by[m]['source']}.values())
            group = {'id': identity, 'kind': 'composite', 'label': kind, 'parent': parent, 'source': source,
                     'evidence_status': 'static-only', 'granularity': 'composite', 'glyph': GLYPHS['composite'],
                     'semantic_type': kind, 'runtime_evidence': [], 'motif': identity}
            nodes.append(group); by[identity] = group
            for m in members: by[m]['parent'] = identity
        return identity

    def next_compute(node_id, parent, visited=None):
        visited = set(visited or ())
        if node_id in visited: return []
        visited.add(node_id)
        result = []
        for target in outgoing.get(node_id, []):
            n = by[target]
            if n.get('parent') != parent: continue
            if n['kind'] == 'compute': result.append((target, [target]))
            elif n['kind'] == 'value-alias':
                result.extend((end, [target, *path]) for end, path in next_compute(target, parent, visited))
        return result

    def serial_mlp(ids):
        allowed = set(ids)
        computations = {identity for identity in ids if by[identity]['kind'] == 'compute'}
        # A path somewhere inside a source container is insufficient to name
        # the entire container. Require its whole local computation to be one
        # supported feed-forward path; concat, unknowns, state and other side
        # computations retain the original source-module identity.
        permitted = {'linear', 'activation', 'dropout', 'reshape', 'identity'}
        if not computations or any(by[identity].get('operator') not in permitted or by[identity].get('mutable') for identity in computations):
            return False
        if any(by[identity]['kind'] in {'opaque', 'control', 'state'} or by[identity].get('operator') == 'phi' for identity in ids):
            return False
        for start in ids:
            if by[start].get('operator') != 'linear': continue
            queue = [(start, False, frozenset())]; seen = set()
            for current, activated, path in queue:
                if current in path: continue
                path = path | {current}
                activated |= by[current].get('operator') == 'activation'
                key = (current, activated, path)
                if key in seen: continue
                seen.add(key)
                if len(seen) > 2048: return False
                if activated and computations <= path and sum(by[identity].get('operator') == 'linear' for identity in path) >= 2:
                    return True
                for target in outgoing.get(current, []):
                    if target in allowed: queue.append((target, activated, path))
        return False

    used = set()
    for n in list(nodes):
        if n.get('operator') != 'convolution' or n['id'] in used: continue
        p = n.get('parent')
        for a, first in next_compute(n['id'], p):
            if by[a].get('operator') != 'activation': continue
            candidates = [(None, [])] + next_compute(a, p)
            pool = next(((b, path) for b, path in candidates if b and by[b].get('operator') == 'pooling'), (None, []))
            members = [n['id'], *first, *pool[1]]
            if set(members) & used: continue
            # Parameter scope belongs to the computation it supplies.
            members += [e['source'] for e in edges if e['target'] in members and e['kind'] == 'parameter-read' and by[e['source']].get('parent') == p]
            add('CNN block', members, ['convolution → activation' + (' → pooling' if pool[0] else ''), 'source operand dependencies'], p, True)
            used.update(members)
            break
    for n in list(nodes):
        if n.get('operator') in {'lstm', 'gru', 'rnn'}:
            add(n['operator'].upper(), [n['id']], ['versioned torch.nn framework type; gates not inferred'])
    # Existing source containers are recursively classified from their actual
    # descendants. This labels evidence, without manufacturing Transformer boxes.
    children = {}
    for n in nodes: children.setdefault(n.get('parent'), []).append(n['id'])
    def descendants(identity):
        result = []
        for child in children.get(identity, []): result.extend([child, *descendants(child)])
        return result
    for n in list(nodes):
        # Control scopes retain their source contract even when their body
        # contains a recognizable local block. Replacing this type would lose
        # loop-carried/conditional boundaries in downstream presentation.
        if n['kind'] != 'composite' or n.get('motif') or n.get('semantic_type') in {'loop-template', 'iteration-region', 'conditional-region'}: continue
        ds = descendants(n['id'])
        # A container which merely contains attention is not itself attention.
        # Source call boundaries stay intact; classify the local operation scope.
        local = children.get(n['id'], [])
        ops = [by[m].get('operator') for m in local]
        attention = ops.count('matmul') >= 2 and 'softmax' in ops and any(op in ops for op in ('div', 'mult', 'mul', 'sqrt'))
        if attention:
            # Necessary pattern only: no unconditional Q/K/V/head/encoder claim.
            add('attention-like', local, ['two matmuls + softmax + scaling in local source scope; Q/K/V roles require further proof'])
            n['semantic_type'] = 'attention-like'
        elif serial_mlp(local) and 'convolution' not in ops:
            add('MLP / feed-forward', local, ['source dependency path: Linear → activation → Linear'])
            n['semantic_type'] = 'MLP / feed-forward'
        elif any(by[m].get('semantic_type') == 'CNN block' for m in ds):
            n['semantic_type'] = 'convolutional network'
        if 'add' in ops and 'normalization' in ops:
            # Keep this weaker than a residual guarantee until a skip producer
            # is matched to the original sublayer input.
            add('add-and-normalization candidate', ds, ['add + normalization; residual origin unproven'])
    ir['motifs'] = motifs
    return ir


def recognize_runtime(ir):
    """Promote only observed dataflow patterns; no module-name inference."""
    nodes = ir['nodes']; by = {n['id']: n for n in nodes}
    children, outgoing = {}, {}
    for n in nodes: children.setdefault(n.get('parent'), []).append(n['id'])
    for e in ir['edges']:
        if e['evidence'] == 'runtime-tensor': outgoing.setdefault(e['source'], []).append(e['target'])
    def descendants(identity):
        result = []
        for child in children.get(identity, []): result.extend([child, *descendants(child)])
        return result
    for container in nodes:
        if container.get('semantic_type') != 'observed-module-call': continue
        members = children.get(container['id'], [])
        ops = {m: by[m].get('operator', '') for m in members}
        mm = [m for m, op in ops.items() if any(s in op for s in ('aten.bmm.', 'aten.mm.', 'aten.matmul.'))]
        softmax = [m for m, op in ops.items() if 'softmax' in op]
        found = None
        # Find score-matmul → scaling → softmax → value-matmul by actual
        # producer/consumer links, allowing intervening shape/mask/guard ops.
        for start in mm:
            todo = [(start, False, False, [])]; seen = set()
            for current, scaled, normalized, path in todo:
                scaled |= any(token in ops.get(current, '') for token in ('aten.div.', 'aten.mul.'))
                normalized |= current in softmax
                key = (current, scaled, normalized)
                if key in seen: continue
                seen.add(key)
                if current != start and current in mm and scaled and normalized:
                    found = [start, *path, current]; break
                for target in outgoing.get(current, []):
                    if target in ops: todo.append((target, scaled, normalized, [*path, current]))
            if found: break
        if found:
            four_dim = [m for m in members if any(len(t['shape']) == 4 and t['shape'][1] > 1 for t in by[m].get('outputs', []))]
            kind = 'multi-head attention-like' if four_dim else 'scaled attention-like'
            container['semantic_type'] = kind
            ir['motifs'].append({'id': 'motif:observed:' + container['id'], 'semantic_type': kind,
                                  'members': list(dict.fromkeys(found)), 'evidence': ['observed matmul → scale → softmax → matmul tensor dependencies',
                                   'observed rank-4 multi-head-shaped intermediate' if four_dim else 'Q/K/V high-level roles remain candidates'],
                                  'confidence': 'runtime-pattern-confirmed', 'rule_version': 'runtime-motifs/1'})
        framework_type = container.get('framework_type') or ''
        if framework_type.startswith('torch.nn.') and framework_type.split('.')[-1] in {'LSTM', 'GRU', 'RNN'}:
            container['semantic_type'] = framework_type.split('.')[-1] + ' · observed framework module'
    return ir
