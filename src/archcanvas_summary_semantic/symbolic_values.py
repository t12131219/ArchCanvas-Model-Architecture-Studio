"""Bound symbolic reads without inventing concrete values or runtime types.

Tensor annotations describe the source contract, not a runtime type check.
Attributes stay explicit operations; custom attributes and effects are barriers.
"""
VERSION = 'source-symbolic-value/1'
EXCEPTIONS = {'ValueError', 'TypeError', 'RuntimeError', 'NotImplementedError',
              'IndexError', 'KeyError', 'AssertionError'}
FLOW = {'data', 'alias', 'interface-binding'}
NAMESPACES = {'torch', 'torch.nn', 'torch.nn.functional', 'math'}
CONSTANTS = {'torch.' + name for name in (
    'bool', 'uint8', 'int8', 'int16', 'short', 'int32', 'int', 'int64', 'long',
    'float16', 'half', 'float32', 'float', 'float64', 'double', 'bfloat16',
    'complex64', 'cfloat', 'complex128', 'cdouble')}
ATTRIBUTES = {'shape', 'device', 'dtype', 'ndim'}
TENSOR_MODULES = {'Linear', 'Conv1d', 'Conv2d', 'Conv3d', 'Embedding', 'LayerNorm',
                  'BatchNorm1d', 'BatchNorm2d', 'GroupNorm', 'Dropout', 'ReLU', 'GELU',
                  'Sigmoid', 'Tanh', 'Identity', 'Flatten', 'Softmax', 'LogSoftmax'}
TENSOR_OPS = {'reshape', 'transpose', 'copy', 'detach', 'device-cast', 'dtype-cast',
              'activation', 'softmax', 'normalization', 'mask', 'nan-guard', 'expand',
              'linear', 'convolution', 'pooling', 'matmul', 'concat', 'stack', 'create',
              'random', 'sqrt', 'exp', 'pow', 'rsqrt', 'abs', 'sin', 'cos', 'clamp'}


def derive(nodes, edges):
    """Recompute facts from actual bindings; do not trust stored certificates."""
    by = {n['id']: n for n in nodes}
    incoming, writes = {}, {e['target'] for e in edges if e['kind'] == 'state-write'}
    for e in edges:
        incoming.setdefault(e['target'], []).append(e)
    facts, tensor, barrier = {}, {}, None
    active = set()

    def tensor_contract(at):
        if at in tensor: return tensor[at]
        if at in active or at not in by: return False
        active.add(at)
        n = by[at]
        ins = [e for e in incoming.get(at, []) if e['kind'] in FLOW]
        result = n.get('source_tensor_annotation') == 'torch.Tensor'
        if not result and n['kind'] in {'interface', 'value-alias'} and not n.get('operator') and len(ins) == 1:
            e = ins[0]
            result = e.get('source_port', 'out') == 'out' and n.get('slot') is None and tensor_contract(e['source'])
            # Input slot names never carry type semantics; input interfaces bind
            # the whole value even when their source parameter has another name.
            if n['kind'] == 'interface' and e.get('source_port', 'out') == 'out':
                result = tensor_contract(e['source'])
        if n.get('operator') == 'phi' and len(ins) == 2 and {e.get('target_port') for e in ins} == {'true', 'false'}:
            result = all(e.get('source_port', 'out') == 'out' and tensor_contract(e['source']) for e in ins)
        if n['kind'] == 'compute' and not n.get('mutable'):
            framework = n.get('framework_type', '')
            if n.get('source_framework_module') == framework and framework.startswith('torch.nn.') and framework.split('.')[-1] in TENSOR_MODULES:
                result = n.get('module_binding', {}).get('status') == 'proved'
            elif n.get('source_framework_function') == n.get('function_target') and n.get('function_target', '').startswith('torch.') and n.get('operator') in TENSOR_OPS:
                result = True  # Framework call contract; runtime types are not asserted.
            elif any(e.get('target_port') == 'receiver' and tensor_contract(e['source']) for e in ins) and n.get('operator') in TENSOR_OPS:
                result = True
            elif n.get('operator') in {'add', 'sub', 'mult', 'div'}:
                result = any(tensor_contract(e['source']) for e in ins)
        active.remove(at); tensor[at] = result
        return result

    for n in nodes:
        if barrier is None:
            value_import = n.get('framework_value_import')
            if value_import in NAMESPACES | CONSTANTS:
                facts[n['id']] = {'rule_version': VERSION, 'kind': 'framework-symbol', 'symbol': value_import,
                                  'scope': 'unshadowed source import in modeled prefix; no monkey-patching claim'}
            elif n.get('module_resource') and n.get('resource_framework_type', '').startswith('torch.nn.'):
                binding = n.get('module_resource_binding', {})
                if binding.get('status') == 'proved' and binding.get('reference') == n.get('module_identity'):
                    facts[n['id']] = {'rule_version': VERSION, 'kind': 'module-resource',
                                      'reference': binding['reference'], 'framework_type': n['resource_framework_type'],
                                      'scope': 'constructor resource selected at this source read; not a call or parameter-stability claim'}
            elif n.get('operator') == 'attribute' and n['kind'] == 'compute':
                ins = [e for e in incoming.get(n['id'], []) if e['kind'] in FLOW]
                # The exact attribute is checked against source syntax as well as
                # its lowering field; the explicit receiver is retained.
                syntax = n.get('syntax', {})
                attr = n.get('attribute_name')
                if len(ins) == 1 and syntax.get('type') == 'Attribute' and syntax.get('fields', {}).get('attr') == attr:
                    e = ins[0]
                    receiver = facts.get(e['source'], {})
                    # Attribute nodes precede their receiver expression in the
                    # lowering list; the dependency edge is authoritative.
                    imported = by[e['source']].get('framework_value_import')
                    if imported in NAMESPACES:
                        receiver = {'kind': 'framework-symbol', 'symbol': imported}
                    symbol = receiver.get('symbol', '') + '.' + str(attr)
                    if receiver.get('kind') == 'framework-symbol' and symbol in CONSTANTS:
                        facts[n['id']] = {'rule_version': VERSION, 'kind': 'framework-attribute', 'symbol': symbol,
                                          'receiver': e['source'], 'edge': e['id'], 'attribute': attr,
                                          'scope': 'framework constant binding; no tensor value claim'}
                    elif attr in ATTRIBUTES and e.get('source_port', 'out') == 'out' and tensor_contract(e['source']):
                        facts[n['id']] = {'rule_version': VERSION, 'kind': 'tensor-attribute',
                                          'receiver': e['source'], 'edge': e['id'], 'attribute': attr,
                                          'scope': 'source Tensor contract only; annotation is not runtime validation; actual value unresolved'}
        if n['kind'] == 'opaque' or n.get('mutable') or n['id'] in writes or (
                n['kind'] == 'control' and n.get('operator') == 'loop'):
            barrier = barrier or n['id']
    return facts


def value_for(n, facts):
    fact = facts.get(n['id'])
    if not fact: return n.get('value')
    if fact['kind'] in {'framework-symbol', 'framework-attribute'}:
        return {'framework_symbol': fact['symbol']}
    if fact['kind'] == 'module-resource':
        return {'module_resource': fact['framework_type']}
    return {'derived_attribute': fact['attribute'], 'basis': 'source Tensor contract'}


def exception_for(n):
    """A supported explicit exit remains an operation, including its arguments."""
    import ast
    from .structure import syntax
    signature = n.get('exception_signature')
    if not signature or n.get('operator') != 'exception-exit': return None
    try:
        expr = ast.parse(n['exception_expression'], mode='eval').body
    except (ValueError, SyntaxError, KeyError):
        return None
    if not isinstance(expr, ast.Call) or not isinstance(expr.func, ast.Name) or expr.func.id not in EXCEPTIONS:
        return None
    if signature != {'builtin': expr.func.id, 'syntax': syntax(expr),
                     'scope': 'source exceptional exit; reachability and execution not asserted'}:
        return None
    if expr.keywords or any(isinstance(a, ast.Starred) for a in expr.args): return None
    return signature


def certify(nodes, edges):
    facts = derive(nodes, edges)
    for n in nodes:
        if n['id'] in facts: n['symbolic_value'] = facts[n['id']]


def validate(nodes, edges):
    facts = derive(nodes, edges)
    return (['invalid symbolic value binding: ' + n['id'] for n in nodes
             if 'symbolic_value' in n and n['symbolic_value'] != facts.get(n['id'])]
            + ['invalid exception exit signature: ' + n['id'] for n in nodes
               if 'exception_signature' in n and exception_for(n) is None])
