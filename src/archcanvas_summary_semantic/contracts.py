"""Versioned, operand-backed local contracts over the extracted source graph.

Names never select a model family. Certificates describe normal-return paths
and keep all source branches, guards, resources and implementation operations.
"""
from .schema import digest, source_graph_digest

FLOW = {'data', 'alias', 'interface-binding'}


def value_operands(node, edges):
    """Operands that can prove value lineage, not all source dependencies.

    Shape, exemplar, dtype, device and axis edges stay in the IR and in summary
    cuts. This policy only restricts the evidence for a residual branch.
    Index/mask operands and ordinary algebra are deliberately not filtered.
    """
    op = node.get('operator')
    if op in {'shape', 'attribute', 'scalar-cast', 'create', 'random', 'range', 'enumerate'}:
        return []
    if op not in {'device-cast', 'dtype-cast', 'reshape', 'transpose', 'copy', 'detach',
                  'expand', 'softmax', 'dropout', 'activation', 'pooling', 'interpolate',
                  'reduce', 'split', 'nan-guard'}:
        return edges
    if any(e['target_port'] == 'receiver' for e in edges):
        return [e for e in edges if e['target_port'] == 'receiver']
    inputs = [e for e in edges if e['target_port'] in {'arg:0', 'kw:input'}]
    if inputs:
        return inputs
    return edges if len(edges) == 1 and edges[0]['target_port'] == 'in' else []


class Contracts:
    def __init__(self, ir):
        self.ir = ir
        self.by = {n['id']: n for n in ir['nodes']}
        self.ins, self.children = {}, {}
        for e in ir['edges']:
            self.ins.setdefault(e['target'], []).append(e)
        for n in ir['nodes']:
            self.children.setdefault(n.get('source_parent', n.get('parent')), []).append(n['id'])
        self.certificates, self.sdpa, self.mha, self.ffn, self.layers = [], {}, {}, {}, {}
        self.desc_cache = {}

    def descendants(self, identity):
        if identity not in self.desc_cache:
            self.desc_cache[identity] = [child for c in self.children.get(identity, []) for child in [c, *self.descendants(c)]]
        return self.desc_cache[identity]

    def incoming(self, identity):
        return [e for e in self.ins.get(identity, []) if e['kind'] in FLOW]

    def resolve(self, identity, slot='out', stop=None):
        seen = set()
        while identity in self.by and (identity, slot) not in seen:
            seen.add((identity, slot))
            n = self.by[identity]
            if n.get('parent') == stop and n['kind'] == 'interface' and n.get('role') == 'input':
                break
            edges = self.incoming(identity)
            if n.get('return_selection'):
                identity = n['return_selection']['selected']
                continue
            if n['kind'] in {'interface', 'value-alias'} and not n.get('operator') and len(edges) == 1 and not edges[0].get('condition'):
                e = edges[0]
                identity = e['source']
                outer = str(e.get('source_port', 'out'))
                slot = outer if slot == 'out' else slot if outer == 'out' else outer + '.' + slot
                continue
            if n.get('operator') == 'structure' and slot != 'out':
                head, _, rest = slot.partition('.')
                candidates = [e for e in edges if e['target_port'] == head]
                if len(candidates) == 1:
                    identity, slot = candidates[0]['source'], rest or candidates[0].get('source_port', 'out')
                    continue
            break
        return identity, slot

    def operand(self, identity, port, stop=None):
        edges = [e for e in self.incoming(identity) if e['target_port'] == port and not e.get('condition')]
        return self.resolve(edges[0]['source'], str(edges[0].get('source_port', 'out')), stop) if len(edges) == 1 else None

    def node(self, value):
        return self.by.get(value[0], {}) if value else {}

    def op(self, value):
        return self.node(value).get('operator')

    def constant(self, value):
        return self.node(value).get('value', {'unresolved': True})

    def certify(self, rule, node, roles, proof, dependencies=(), not_asserted=(), members=None):
        members = list(dict.fromkeys(members if members is not None else [node, *self.descendants(node)]))
        scope = set(members)
        certificate = {'id': 'contract:' + rule + ':' + digest(node)[:12], 'rule': rule, 'rule_version': 'source-contracts/1',
                       'node': node, 'members': members, 'roles': roles, 'proof': proof,
                       'source': self.by[node]['source'], 'dependencies': list(dependencies),
                       'edges': [e['id'] for e in self.ir['edges'] if e['source'] in scope or e['target'] in scope],
                       'scope': 'normal-return paths of the extracted invocation and its fixed constructor configuration',
                       'not_asserted': ['arbitrary-input execution coverage', *not_asserted]}
        self.certificates.append(certificate)
        return certificate

    def data_path(self, start, end, depth=0):
        """Find an actual value path, excluding shape-only and effect links."""
        if depth > 12: return None
        todo, seen = [(end, [])], set()
        for value, path in todo:
            if value == start: return path
            if value in seen or len(path) >= 64 or len(seen) > 4096: continue
            seen.add(value)
            n = self.node(value)
            if n.get('operator') == 'phi':
                alternatives = self.incoming(value[0])
                if len(alternatives) == 2 and {e.get('condition', {}).get('outcome') for e in alternatives} == {'true', 'false'} and len({e.get('condition', {}).get('branch') for e in alternatives}) == 1:
                    paths = [self.data_path(start, self.resolve(e['source'], e.get('source_port', 'out')), depth + 1) for e in alternatives]
                    if all(p is not None for p in paths):
                        return list(dict.fromkeys([*(i for p in paths for i in p), value[0], *path]))
                continue
            if not n or n['kind'] != 'compute' or n.get('mutable') or n.get('operator') in {'shape', 'attribute', 'scalar-cast', 'phi'}:
                continue
            for edge in value_operands(n, self.incoming(value[0])):
                if not edge.get('condition'):
                    todo.append((self.resolve(edge['source'], edge.get('source_port', 'out')), [value[0], *path]))
        return None

    def residuals(self):
        normalizers = [n for n in self.ir['nodes'] if n.get('operator') == 'normalization']
        for add in self.ir['nodes']:
            if add.get('operator') != 'add' or add.get('mutable'): continue
            if add.get('arguments', {}).get('kwargs', {}).get('alpha', 1) != 1: continue
            ins = self.incoming(add['id'])
            if len(ins) != 2 or any(e.get('condition') for e in ins): continue
            inputs = [self.resolve(e['source'], e.get('source_port', 'out')) for e in ins]
            if inputs[0] == inputs[1]: continue
            for index in (0, 1):
                skip, branch = inputs[index], inputs[1 - index]
                path = self.data_path(skip, branch)
                if not path: continue
                norm = next((n for n in normalizers if self.operand(n['id'], 'arg:0') == (add['id'], 'out')), None)
                prenorm = next((self.by[i] for i in path if self.by[i].get('operator') == 'normalization' and self.operand(i, 'arg:0') == skip), None)
                normalization = norm or prenorm
                kind = 'postnorm' if norm else 'prenorm' if prenorm else 'plain'
                roles = {'skip': skip[0], 'skip_slot': skip[1], 'branch': branch[0], 'branch_slot': branch[1],
                         'add': add['id'], 'output': norm['id'] if norm else add['id'], 'order': kind,
                         'normalization': normalization['id'] if normalization else None,
                         'normalization_type': normalization.get('framework_type') if normalization else None,
                         'branch_path': path}
                self.certify('residual-' + kind, roles['output'], roles,
                    ['the same producer and result slot feed both branch computation and a distinct addition operand',
                     'normalization position is determined by exact operand binding; normalization type remains explicit'],
                    members=[*path, add['id'], *([norm['id']] if norm else [])],
                    not_asserted=['identity branch computation', 'in-place alias equivalence'])
                break

    def local_unary_chain(self, frame, allowed):
        """Prove a whole source scope from its return and exact unary operands.

        Source helpers are retained as independently identified enclosures;
        only their explicit one-to-one interface bindings are traversed. A
        containing wrapper is not a second semantic owner of the same chain.
        """
        members = [frame, *self.descendants(frame)]
        scope = set(members)
        nodes = [self.by[i] for i in members]
        computations = {n['id'] for n in nodes if n['kind'] == 'compute'}
        if not computations or any(self.by[i].get('operator') not in allowed for i in computations):
            return None
        for n in nodes:
            if (n['kind'] in {'opaque', 'control', 'state', 'buffer'} or n.get('mutable') or n.get('condition') or
                n.get('iteration_contract') or n.get('repeat_contract') or n.get('iteration') or n.get('return_selection') or
                n.get('evidence_status') == 'runtime-only' or n.get('operator') == 'phi' or
                n.get('constructor', {}).get('kwargs', {}).get('inplace') is True):
                return None
        edges = [e for e in self.ir['edges'] if e['source'] in scope or e['target'] in scope]
        if any(e.get('condition') or e['kind'] not in FLOW | {'parameter-read'} for e in edges):
            return None
        outputs = [self.by[i] for i in self.children.get(frame, []) if self.by[i]['kind'] == 'interface' and self.by[i].get('role') == 'output']
        if len(outputs) != 1:
            return None
        current = self.resolve(outputs[0]['id'], stop=frame)
        reverse, seen = [], set()
        while current and current not in seen and current[0] in computations:
            seen.add(current)
            if current[1] != 'out':
                return None
            incoming = self.incoming(current[0])
            if len(incoming) != 1 or incoming[0]['target_port'] != 'arg:0':
                return None
            reverse.append(current[0])
            current = self.operand(current[0], 'arg:0', frame)
        if set(reverse) != computations or not current or current[1] != 'out':
            return None
        start = self.node(current)
        if start.get('source_parent', start.get('parent')) != frame or start.get('role') != 'input' or start['kind'] != 'interface':
            return None
        operations = list(reversed(reverse))
        # Nearest common source ancestor, independent of motif/drawing parents.
        ancestors = []
        for identity in operations:
            chain = []
            parent = self.by[identity].get('source_parent', self.by[identity].get('parent'))
            while parent in self.by:
                chain.append(parent)
                parent = self.by[parent].get('source_parent', self.by[parent].get('parent'))
            ancestors.append(chain)
        common = next((i for i in ancestors[0] if all(i in chain for chain in ancestors[1:])), None)
        if common != frame:
            return None
        helpers = []
        for n in nodes:
            if n['kind'] != 'composite' or n['id'] == frame:
                continue
            closure = [n['id'], *self.descendants(n['id'])]
            inside = set(closure)
            if inside & computations:
                helpers.append({'node': n['id'], 'source_parent': n.get('source_parent', n.get('parent')),
                    'members': closure, 'cuts': [e['id'] for e in self.ir['edges'] if (e['source'] in inside) != (e['target'] in inside)]})
        return {'rule_version': 'source-local-chain/1', 'operations': operations,
                'input': {'node': current[0], 'slot': current[1]}, 'output': outputs[0]['id'], 'helpers': helpers}

    def feedforward(self, frame):
        chain = self.local_unary_chain(frame, {'linear', 'activation', 'dropout', 'identity'})
        if not chain:
            return
        operations = chain['operations']
        if (self.by[operations[0]].get('operator') != 'linear' or self.by[operations[-1]].get('operator') != 'linear' or
            sum(self.by[i].get('operator') == 'linear' for i in operations) != 2):
            return
        activations = [i for i in operations if self.by[i].get('operator') == 'activation']
        if not activations:
            return
        cert = self.certify('feed-forward', frame,
            {'input_projection': operations[0], 'activation': activations[0], 'output_projection': operations[-1], 'output': operations[-1]},
            ['the entire local computation is a Linear → activation → Linear dependency chain; explicit wrappers retained'],
            not_asserted=['independent projection parameters', 'helper purity or arbitrary alias equivalence'])
        cert['source_chain'] = chain
        self.ffn[frame] = cert

    def _variants(self, value, leaf, allowed, seen=None):
        """All value alternatives must reach the same certified base.

        Only two-sided phi joins and explicitly recorded operation wrappers
        are traversed. A one-sided/unbound branch can never prove equivalence.
        """
        if not value:
            return None
        seen = set(seen or ())
        if value in seen:
            return None
        seen.add(value)
        n = self.node(value)
        if n.get('mutable') or n['kind'] == 'opaque' or value[1] != 'out':
            return None
        if leaf(n):
            return value
        if n.get('operator') == 'phi':
            edges = self.incoming(value[0])
            if len(edges) != 2 or {e.get('condition', {}).get('outcome') for e in edges} != {'true', 'false'} or len({e.get('condition', {}).get('branch') for e in edges}) != 1:
                return None
            bases = [self._variants(self.resolve(e['source'], e.get('source_port', 'out')), leaf, allowed, seen) for e in edges]
            return bases[0] if bases[0] is not None and bases[0] == bases[1] else None
        port = allowed(n)
        return self._variants(self.operand(value[0], port), leaf, allowed, seen) if port is not None else None

    def attention(self, frame):
        scope = [frame, *self.descendants(frame)]
        if any(self.by[i]['kind'] == 'opaque' or self.by[i].get('mutable') for i in scope):
            return
        def tail(n):
            if n.get('operator') == 'dropout': return 'arg:0'
            if n.get('operator') == 'nan-guard' and n.get('arguments', {}).get('kwargs', {}).get('nan') == 0.0:
                return 'arg:0'
            return None
        def score_wrapper(n):
            if n.get('operator') != 'mask': return None
            fill = self.operand(n['id'], 'arg:1')
            scalar = self.node(fill)
            if scalar.get('operator') != 'scalar-cast' or scalar.get('function_target') != 'float' or scalar.get('arguments', {}).get('args') != ['-inf']:
                return None
            return 'receiver'
        for identity in scope:
            output = self.by[identity]
            if output.get('operator') != 'matmul': continue
            weights, values = self.operand(identity, 'arg:0'), self.operand(identity, 'arg:1', frame)
            softmax = self._variants(weights, lambda n: n.get('operator') == 'softmax', tail)
            norm = self.node(softmax)
            if norm.get('arguments', {}).get('kwargs', {}).get('dim') != -1:
                continue
            scaled = self._variants(self.operand(norm['id'], 'arg:0'), lambda n: n.get('operator') == 'div', score_wrapper)
            if not scaled: continue
            scores, divisor = self.operand(scaled[0], '0'), self.operand(scaled[0], '2')
            if self.op(scores) != 'matmul' or self.op(divisor) != 'sqrt': continue
            q, transposed = self.operand(scores[0], 'arg:0', frame), self.operand(scores[0], 'arg:1')
            key_transpose = self.node(transposed)
            if key_transpose.get('operator') != 'transpose' or key_transpose.get('arguments', {}).get('args') not in ([-2, -1], [-1, -2]): continue
            k = self.operand(transposed[0], 'receiver', frame)
            dim = self.operand(divisor[0], 'arg:0')
            size = self.node(dim)
            if size.get('operator') != 'shape' or size.get('arguments', {}).get('args') != [-1] or self.operand(dim[0], 'receiver', frame) != q:
                continue
            if not all(v and self.node(v).get('parent') == frame and self.node(v).get('role') == 'input' for v in (q, k, values)):
                continue
            cert = self.certify('scaled-dot-product-attention', frame,
                {'query': q[0], 'key': k[0], 'value': values[0], 'scores': scores[0], 'key_transpose': transposed[0],
                 'scale': scaled[0], 'softmax': softmax[0], 'output': identity,
                 'masks': [i for i in scope if self.by[i].get('operator') == 'mask'],
                 'dropout': [i for i in scope if self.by[i].get('operator') == 'dropout'],
                 'numerical_guards': [i for i in scope if self.by[i].get('operator') == 'nan-guard']},
                ['Q @ transpose(K,-2,-1) divided by sqrt(Q.size(-1))',
                 'all score alternatives preserve that score or apply masked_fill(...,-inf)',
                 'softmax(dim=-1); all weight alternatives retain explicit dropout/nan-to-zero wrappers',
                 'weights @ V operand order'], not_asserted=['causal mask content', 'mask broadcast validity for arbitrary inputs'])
            self.sdpa[frame] = cert
            break

    def dimension(self, value, tensor, axis):
        if not value: return False
        n = self.node(value)
        return (n.get('operator') == 'attribute' and n.get('label', '').endswith('.shape') and value[1] == str(axis)
                and self.operand(value[0], 'in') == tensor)

    def split(self, value, frame):
        n = self.node(value)
        if n.get('operator') == 'copy':
            value = self.operand(value[0], 'receiver'); n = self.node(value)
        if n.get('operator') != 'transpose' or n.get('arguments', {}).get('args') not in ([1, 2], [2, 1]): return None
        view = self.operand(value[0], 'receiver'); v = self.node(view)
        if v.get('operator') != 'reshape' or len(v.get('arguments', {}).get('args', [])) != 4: return None
        projection = self.operand(view[0], 'receiver')
        if self.op(projection) != 'linear': return None
        if not self.dimension(self.operand(view[0], 'arg:0'), projection, 0) or not self.dimension(self.operand(view[0], 'arg:1'), projection, 1): return None
        h, d = v['arguments']['args'][2:]
        linear = self.node(projection)
        width = (linear.get('constructor', {}).get('args') or [None, None])[1]
        if type(h) is not int or type(d) is not int or h <= 0 or d <= 0 or h * d != width: return None
        source = self.operand(projection[0], 'arg:0', frame)
        if not source or self.node(source).get('parent') != frame or self.node(source).get('role') != 'input': return None
        return {'projection': projection[0], 'source': source[0], 'heads': h, 'head_dimension': d, 'split': value[0], 'reshape': view[0]}

    def multihead(self, frame):
        descendants = self.descendants(frame)
        helpers = [self.sdpa[i] for i in descendants if i in self.sdpa]
        if len(helpers) != 1 or any(self.by[i]['kind'] == 'opaque' or self.by[i].get('mutable') for i in descendants): return
        sdpa = helpers[0]
        split = {role: self.split(self.resolve(sdpa['roles'][role]), frame) for role in ('query', 'key', 'value')}
        if any(v is None for v in split.values()) or len({(s['heads'], s['head_dimension']) for s in split.values()}) != 1: return
        result = (sdpa['roles']['output'], 'out')
        for identity in descendants:
            output = self.by[identity]
            if output.get('operator') != 'linear': continue
            view = self.operand(identity, 'arg:0'); v = self.node(view)
            if v.get('operator') != 'reshape' or len(v.get('arguments', {}).get('args', [])) != 3: continue
            contiguous = self.operand(view[0], 'receiver')
            transposed = self.operand(contiguous[0], 'receiver') if self.op(contiguous) == 'copy' else contiguous
            if self.op(transposed) != 'transpose' or self.node(transposed).get('arguments', {}).get('args') not in ([1, 2], [2, 1]) or self.operand(transposed[0], 'receiver') != result: continue
            b, t, merged = [self.operand(view[0], 'arg:' + str(i)) for i in range(3)]
            if not self.dimension(b, result, 0) or not self.dimension(t, result, 2) or self.op(merged) != 'mult': continue
            h, d = self.operand(merged[0], '0'), self.operand(merged[0], '2')
            if not self.dimension(h, result, 1) or not self.dimension(d, result, 3): continue
            # Three separately bound role interfaces are required at this scope.
            # An enclosing residual block can feed all three from its one input;
            # that does not make the whole residual block an attention module.
            if len({s['source'] for s in split.values()}) != 3: continue
            outputs = [n for n in (self.by[i] for i in self.children.get(frame, [])) if n['kind'] == 'interface' and n.get('role') == 'output']
            selected = [n for n in outputs if n.get('return_selection')] or outputs
            if not any(self.resolve(n['id']) == (identity, 'out') for n in selected): continue
            caller = {role: self.resolve(s['source']) for role, s in split.items()}
            mode = 'self' if len(set(caller.values())) == 1 else 'cross' if caller['key'] == caller['value'] and caller['query'] != caller['key'] else 'general'
            cert = self.certify('multihead-attention', frame,
                {'inputs': {role: s['source'] for role, s in split.items()}, 'sources': {role: {'node': value[0], 'slot': value[1]} for role, value in caller.items()},
                 'projections': {role: s['projection'] for role, s in split.items()},
                 'heads': split['query']['heads'], 'head_dimension': split['query']['head_dimension'],
                 'attention': sdpa['node'], 'output_projection': identity, 'output': identity, 'mode': mode,
                 'mask_semantics': 'supplied masks; causal content not asserted'},
                ['three Linear projections preserve batch and length axes while splitting D=H*Dh',
                 'head axis transpose feeds certified attention Q/K/V',
                 'attention output transposes head/length axes back and merges H*Dh before output projection',
                 'self/cross identity compares pre-projection producers and exact result slots'],
                dependencies=[sdpa['id']], not_asserted=['independent Q/K/V parameters', 'automatic causal masking'])
            self.mha[frame] = cert
            break

    def run(self):
        frames = [n['id'] for n in self.ir['nodes'] if n['kind'] == 'composite' and not n.get('motif')]
        for frame in frames:
            # A whole MHA containing an attention helper must not be mistaken
            # for that helper: its Q/K/V must be direct interfaces of the scope.
            self.attention(frame)
        for frame in frames:
            self.multihead(frame)
            self.feedforward(frame)
        self.residuals()
        return self.certificates


def recognize_contracts(ir):
    certificates = Contracts(ir).run()
    if certificates:
        ir['semantic_contracts'] = certificates
        ir['semantic_contract_basis'] = source_graph_digest(ir)
    return ir


def validate_source_chains(ir):
    """Re-derive the new chain witness; a sealed list of IDs is insufficient."""
    errors = []
    for cert in ir.get('semantic_contracts', []):
        if 'source_chain' not in cert:
            continue
        try:
            engine = Contracts(ir)
            engine.feedforward(cert['node'])
            actual = engine.ffn.get(cert['node'])
            if cert['rule'] != 'feed-forward' or not actual or any(cert.get(key) != actual[key] for key in ['source_chain', 'roles', 'members', 'edges', 'proof']):
                errors.append('invalid source chain evidence: ' + cert['id'])
        except (KeyError, TypeError, RecursionError):
            errors.append('invalid source chain evidence: ' + cert['id'])
    return errors
