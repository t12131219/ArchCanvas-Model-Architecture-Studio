"""Conservative AST lowering, with explicit interfaces and unresolved boundaries.

A source dependency is never advertised as a measured tensor edge. Construction
order alone does not create edges. Local definitions can be inspected recursively;
unsupported Python remains source-backed opaque rather than a fabricated template.
"""
from __future__ import annotations
import ast
from contextlib import contextmanager
import copy
from pathlib import Path
from .schema import SCHEMA, COVERAGE_CONTRACT, GLYPHS, seal
from .sources import units

MODULES = {
    'Linear': 'linear', 'Conv1d': 'convolution', 'Conv2d': 'convolution', 'Conv3d': 'convolution',
    'ConvTranspose2d': 'convolution', 'Embedding': 'embedding', 'LayerNorm': 'normalization',
    'BatchNorm1d': 'normalization', 'BatchNorm2d': 'normalization', 'GroupNorm': 'normalization',
    'LeakyReLU': 'activation', 'ELU': 'activation', 'SiLU': 'activation', 'ReLU': 'activation', 'GELU': 'activation', 'Sigmoid': 'activation', 'Tanh': 'activation',
    'Softmax': 'softmax', 'LogSoftmax': 'softmax', 'Dropout': 'dropout',
    'MaxPool2d': 'pooling', 'AvgPool2d': 'pooling', 'AdaptiveAvgPool2d': 'pooling',
    'Flatten': 'reshape', 'Identity': 'identity', 'LSTM': 'lstm', 'GRU': 'gru', 'RNN': 'rnn',
    'RNNCell': 'rnn-cell', 'GRUCell': 'gru-cell', 'LSTMCell': 'lstm-cell',
    'MultiheadAttention': 'multihead-attention', 'Transformer': 'transformer',
    'TransformerEncoder': 'encoder', 'TransformerEncoderLayer': 'encoder-layer',
    'TransformerDecoder': 'decoder', 'TransformerDecoderLayer': 'decoder-layer',
}
FUNCTIONS = {
    'leaky_relu': 'activation', 'elu': 'activation', 'silu': 'activation', 'relu': 'activation', 'gelu': 'activation', 'sigmoid': 'activation', 'tanh': 'activation',
    'softmax': 'softmax', 'log_softmax': 'softmax', 'matmul': 'matmul', 'bmm': 'matmul',
    'mm': 'matmul', 'einsum': 'einsum', 'linear': 'linear', 'conv2d': 'convolution',
    'max_pool2d': 'pooling', 'avg_pool2d': 'pooling', 'adaptive_avg_pool2d': 'pooling',
    'dropout': 'dropout', 'layer_norm': 'normalization', 'batch_norm': 'normalization',
    'scaled_dot_product_attention': 'scaled-dot-product-attention', 'cat': 'concat', 'stack': 'stack',
    'reshape': 'reshape', 'view': 'reshape', 'flatten': 'reshape', 'transpose': 'transpose',
    'permute': 'transpose', 'contiguous': 'copy', 'clone': 'copy', 'detach': 'detach',
    'squeeze': 'reshape', 'unsqueeze': 'reshape', 'size': 'shape', 'dim': 'shape',
    'masked_fill': 'mask', 'masked_fill_': 'mask', 'to': 'device-cast', 'float': 'dtype-cast',
    'bool': 'dtype-cast', 'long': 'dtype-cast', 'nan_to_num': 'nan-guard',
    'zeros': 'create', 'ones': 'create', 'randn': 'random', 'rand': 'random', 'randn_like': 'random',
    'zeros_like': 'create', 'ones_like': 'create', 'sqrt': 'sqrt', 'exp': 'exp', 'sum': 'reduce',
    'mean': 'reduce', 'norm': 'reduce', 'chunk': 'split', 'split': 'split', 'unbind': 'split',
    'pack_padded_sequence': 'pack-sequence', 'pad_packed_sequence': 'unpack-sequence',
    'len': 'shape', 'range': 'range', 'enumerate': 'enumerate',
    'topk': 'top-k', 'gather': 'gather', 'scatter': 'scatter', 'scatter_add': 'scatter-add',
    'where': 'select', 'index_select': 'index-select',
    'interpolate': 'interpolate', 'pad': 'pad', 'pow': 'pow', 'rsqrt': 'rsqrt', 'abs': 'abs', 'sin': 'sin', 'cos': 'cos',
    # max/min are overloaded: the second argument can be a tensor or a dim.
    'max': 'maximum-or-reduction', 'min': 'minimum-or-reduction', 'amax': 'reduce',
    'clamp': 'clamp', 'expand': 'expand', 't': 'transpose',
    'add': 'add', 'mul': 'mult', 'sub': 'sub', 'div': 'div',
}

# Explicit PyTorch API contracts. These remain framework operations; recognizing
# a public primitive is not a claim to have analyzed its C++/CUDA implementation.
MODULES.update({
    **{name: 'convolution' for name in ('ConvTranspose1d', 'ConvTranspose3d', 'LazyConv1d', 'LazyConv2d', 'LazyConv3d', 'LazyConvTranspose1d', 'LazyConvTranspose2d', 'LazyConvTranspose3d')},
    **{name: 'normalization' for name in ('BatchNorm3d', 'SyncBatchNorm', 'InstanceNorm1d', 'InstanceNorm2d', 'InstanceNorm3d', 'LocalResponseNorm', 'RMSNorm', 'LazyBatchNorm1d', 'LazyBatchNorm2d', 'LazyBatchNorm3d')},
    **{name: 'activation' for name in ('ReLU6', 'PReLU', 'RReLU', 'CELU', 'SELU', 'Mish', 'Hardswish', 'Hardsigmoid', 'Hardtanh', 'Softplus', 'Softsign', 'Tanhshrink', 'Softshrink', 'Hardshrink', 'Threshold')},
    **{name: 'pooling' for name in ('MaxPool1d', 'MaxPool3d', 'AvgPool1d', 'AvgPool3d', 'AdaptiveAvgPool1d', 'AdaptiveAvgPool3d', 'AdaptiveMaxPool1d', 'AdaptiveMaxPool2d', 'AdaptiveMaxPool3d', 'LPPool1d', 'LPPool2d')},
    **{name: 'dropout' for name in ('Dropout1d', 'Dropout2d', 'Dropout3d', 'AlphaDropout', 'FeatureAlphaDropout')},
    **{name: 'pad' for name in ('ZeroPad1d', 'ZeroPad2d', 'ZeroPad3d', 'ConstantPad1d', 'ConstantPad2d', 'ConstantPad3d', 'ReflectionPad1d', 'ReflectionPad2d', 'ReflectionPad3d', 'ReplicationPad1d', 'ReplicationPad2d', 'ReplicationPad3d')},
    'LazyLinear': 'linear', 'Bilinear': 'bilinear', 'EmbeddingBag': 'embedding-reduction',
    'Unflatten': 'reshape', 'Upsample': 'interpolate', 'UpsamplingNearest2d': 'interpolate',
    'UpsamplingBilinear2d': 'interpolate', 'PixelShuffle': 'pixel-shuffle', 'PixelUnshuffle': 'pixel-unshuffle',
    'ChannelShuffle': 'channel-shuffle', 'GLU': 'gated-linear-unit',
    'Fold': 'fold', 'Unfold': 'unfold', 'Softmin': 'softmin', 'Softmax2d': 'softmax',
})
FUNCTIONS.update({
    **{name: 'create' for name in ('full', 'full_like', 'empty', 'empty_like', 'arange', 'linspace', 'eye')},
    **{name: 'repeat' for name in ('repeat', 'repeat_interleave', 'tile')},
    **{name: 'reduce' for name in ('prod', 'std', 'var', 'logsumexp', 'all', 'any')},
    **{name: 'activation' for name in ('relu6', 'prelu', 'rrelu', 'celu', 'selu', 'mish', 'hardswish', 'hardsigmoid', 'hardtanh', 'softplus', 'softsign')},
    'cumsum': 'cumulative-sum', 'cumprod': 'cumulative-product', 'tril': 'triangular', 'triu': 'triangular',
    'argmax': 'argmax', 'argmin': 'argmin', 'sort': 'sort', 'argsort': 'argsort',
    'log': 'log', 'log1p': 'log1p', 'exp2': 'exp', 'square': 'pow', 'reciprocal': 'reciprocal',
    'ceil': 'round', 'floor': 'round', 'round': 'round', 'neg': 'negate',
    'conv1d': 'convolution', 'conv3d': 'convolution', 'conv_transpose1d': 'convolution',
    'conv_transpose2d': 'convolution', 'conv_transpose3d': 'convolution',
    'instance_norm': 'normalization', 'group_norm': 'normalization', 'normalize': 'normalization',
    'embedding': 'embedding', 'embedding_bag': 'embedding-reduction', 'bilinear': 'bilinear',
    'max_pool1d': 'pooling', 'max_pool3d': 'pooling', 'avg_pool1d': 'pooling', 'avg_pool3d': 'pooling',
    'adaptive_avg_pool1d': 'pooling', 'adaptive_avg_pool3d': 'pooling',
    'adaptive_max_pool1d': 'pooling', 'adaptive_max_pool2d': 'pooling', 'adaptive_max_pool3d': 'pooling',
    'pixel_shuffle': 'pixel-shuffle', 'pixel_unshuffle': 'pixel-unshuffle',
    'unfold': 'unfold', 'fold': 'fold', 'roll': 'roll', 'flip': 'flip', 'narrow': 'slice',
    'select': 'select', 'take': 'gather', 'masked_select': 'masked-select',
})


def text(n):
    return ast.unparse(n) if n is not None else ''


def literal(n, values):
    """Resolve bounded constructor constants without Python eval/import."""
    if n is None:
        return None
    if isinstance(n, ast.Name) and n.id in values:
        return values[n.id]
    if isinstance(n, ast.Attribute) and text(n) in values:
        return values[text(n)]
    if isinstance(n, ast.BinOp):
        a, b = literal(n.left, values), literal(n.right, values)
        if type(a) in (int, float) and type(b) in (int, float):
            if isinstance(n.op, ast.Add): return a + b
            if isinstance(n.op, ast.Sub): return a - b
            if isinstance(n.op, ast.Mult): return a * b
            if isinstance(n.op, ast.FloorDiv) and b: return a // b
    try:
        return ast.literal_eval(n)
    except (ValueError, TypeError):
        return {'unresolved': text(n)}


class Analyzer:
    def __init__(self, source, entry, constructor=None, cell=None, max_nodes=8000, max_depth=12, project_root=None, factory_entry=False, max_edges=30000):
        self.path = Path(source).resolve()
        self.units, self.diagnostics = units(self.path)
        from .project import Project
        self.project = Project(self.path, project_root)
        self.project.register(self.path, self.units)
        self.factory_entry = factory_entry
        self.project_explicit = project_root is not None
        self.constructor = constructor or {}
        self.entry, self.cell = entry.split(':')[-1], cell
        self.max_nodes, self.max_depth = max_nodes, max_depth
        self.max_edges = max_edges
        self.nodes, self.edges, self.branches, self.counts = [], [], [], {}
        self.coverage_blockers = []
        self.node_by = {}
        self._scopes = {}
        self._active_units = self.units
        self._build_scope(self.units)

    def _build_scope(self, scope_units):
        self.definitions = {}
        for u in scope_units:
            for n in u['tree'].body:
                if isinstance(n, (ast.ClassDef, ast.FunctionDef)):
                    self.definitions.setdefault(n.name, []).append((u, n))
        self.imports = {}
        for u in scope_units:
            for n in u['tree'].body:
                if isinstance(n, ast.Import):
                    for alias in n.names: self.imports[alias.asname or alias.name] = alias.name
                elif isinstance(n, ast.ImportFrom):
                    for alias in n.names: self.imports[alias.asname or alias.name] = (n.module or '') + '.' + alias.name
        # Module bindings and the current function's lexical bindings are
        # checked separately: a parameter in another function does not rebind
        # this function's imported namespace.
        shadowed = set()
        def module_bindings(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                shadowed.add(node.name); return
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                shadowed.add(node.id)
            for child in ast.iter_child_nodes(node): module_bindings(child)
        for u in scope_units:
            module_bindings(u['tree'])
            for n in ast.walk(u['tree']):
                if isinstance(n, ast.Global): shadowed.update(n.names)
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)):
                    base = n
                    while isinstance(base, ast.Attribute): base = base.value
                    if isinstance(base, ast.Name) and base.id in self.imports: shadowed.add(base.id)
        self.value_imports = {k: v for k, v in self.imports.items() if k not in shadowed}
        self.value_shadowed = shadowed | self.imports.keys()
        # Notebook setup globals are evidence only; resolve literal assignments,
        # never run dataset/download/optimizer cells.
        self.globals = {}
        for u in scope_units:
            for n in u['tree'].body:
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                    value = literal(n.value, self.globals)
                    if not isinstance(value, dict): self.globals[n.targets[0].id] = value


    @contextmanager
    def scope(self, unit):
        fields = ('definitions', 'imports', 'value_imports', 'value_shadowed', 'globals', '_active_units')
        old = {key: getattr(self, key) for key in fields}
        if unit not in self._active_units:
            if unit['path'] not in self._scopes:
                self._build_scope([unit])
                self._active_units = [unit]
                self._scopes[unit['path']] = {key: getattr(self, key) for key in fields}
            else:
                for key, value in self._scopes[unit['path']].items():
                    setattr(self, key, value)
        try:
            yield
        finally:
            for key, value in old.items():
                setattr(self, key, value)

    def expression_unit(self, node, fallback=None):
        return self.project.owner(node) or fallback or self._active_units[0]

    def callable(self, cls):
        # Python explicit __call__ overrides nn.Module.__call__, including its hooks.
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        return methods.get('__call__') or methods.get('forward')

    def evidence(self, u, n, symbol):
        return [{'file': u['path'], 'line': n.lineno, 'end_line': n.end_lineno,
                 'column': n.col_offset, 'end_column': n.end_col_offset, 'symbol': symbol,
                 'expression': text(n)[:360]}]

    def add(self, kind, label, parent, u, n, symbol, **extra):
        if len(self.nodes) >= self.max_nodes:
            raise ValueError(f'analysis node budget exceeded ({self.max_nodes}); choose a smaller entry')
        loc = f'{parent or "model"}/{n.lineno}:{n.col_offset}:{kind}'
        self.counts[loc] = self.counts.get(loc, 0) + 1
        identity = loc + ':' + str(self.counts[loc])
        node = {'id': identity, 'kind': kind, 'label': label, 'parent': parent, 'source_parent': parent,
                'source': self.evidence(u, n, symbol), 'evidence_status': 'opaque' if kind == 'opaque' else 'static-only',
                'granularity': 'composite' if kind == 'composite' else 'atomic',
                'glyph': GLYPHS[kind], 'runtime_evidence': [], **extra}
        if kind == 'compute' and isinstance(n, ast.expr):
            from .structure import syntax
            node['syntax'] = syntax(n)
            if node.get('operator') in {'rnn-cell', 'gru-cell', 'lstm-cell'} and isinstance(n, ast.Call):
                # syntax() intentionally abstracts dynamic expressions. Keep
                # argument expansion separately: *args cannot prove absent hx.
                node['cell_call'] = {'rule_version': 'source-cell-call/1',
                                     'positional_count': len(n.args),
                                     'keyword_names': [k.arg for k in n.keywords],
                                     'positional_expansion': any(isinstance(a, ast.Starred) for a in n.args),
                                     'keyword_expansion': any(k.arg is None for k in n.keywords)}
        self.nodes.append(node)
        self.node_by[identity] = node
        return identity

    def edge(self, source, target, kind='data', target_port='in', evidence='source-dependency', **extra):
        if not source or not target or source == target: return
        value = {'source': source, 'target': target, 'kind': kind, 'source_port': 'out',
                 'target_port': target_port, 'evidence': evidence, **extra}
        if any(all(e.get(k) == v for k, v in value.items()) for e in self.edges): return
        if len(self.edges) >= self.max_edges:
            raise ValueError(f'analysis edge budget exceeded ({self.max_edges}); choose a smaller entry')
        value['id'] = f'e{len(self.edges):05d}'
        self.edges.append(value)

    def definition(self, name, cell=None):
        candidates = self.definitions.get(name, [])
        if not candidates and len(self._active_units) == 1:
            return self.project.definition(name, self._active_units[0])
        if cell is not None: candidates = [(u, n) for u, n in candidates if u['cell'] == cell]
        return candidates[0] if len(candidates) == 1 else None

    def resolve(self, name, unit=None):
        if unit is not None and unit not in self._active_units:
            with self.scope(unit):
                return self.resolve(name)
        head, *tail = name.split('.')
        imported = self.imports.get(head, head)
        if head in self.imports and imported.split('.')[0] in {'torch', 'math'}:
            base = imported.split('.')[0]
            if self.project.module(base, self._active_units[0]) or (self.project.root/base).is_dir():
                return 'project-local:' + '.'.join([imported, *tail])
        return '.'.join([imported, *tail])

    def value_namespace(self, expression, unit):
        """Check the original expression's lexical namespace, including init/factories."""
        unit = self.expression_unit(expression, unit)
        if unit not in self._active_units:
            with self.scope(unit):
                return self.value_namespace(expression, unit)
        head = text(expression).split('.')[0]
        if head not in self.value_imports: return False
        for fn in ast.walk(unit['tree']):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or not (fn.lineno <= expression.lineno <= fn.end_lineno):
                continue
            bound = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
            bound.update(n.arg for n in ast.walk(fn) if isinstance(n, ast.arg))
            bound.update(a.asname or a.name.split('.')[0] for n in ast.walk(fn)
                         if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names)
            if head in bound: return False
        return True

    def module_map(self, cls, values):
        result = {}
        init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'), None)
        if not init: return result
        # Conditional constructors remain annotated, never arbitrarily select a path.
        for n in ast.walk(init):
            if isinstance(n, ast.Assign):
                for target in n.targets:
                    name = text(target)
                    if isinstance(target, ast.Attribute) and name.startswith('self.'):
                        if name in result: result[name] = None
                        else: result[name] = n.value
                        value = literal(n.value, values)
                        if not isinstance(value, dict): values[name] = value
        for key in result:
            seen = {key}
            while isinstance(result[key], ast.Attribute) and text(result[key]) in result and text(result[key]) not in seen:
                target = text(result[key]); seen.add(target); result[key] = result[target]
        return result

    def constructor_values(self, cls, call, values):
        init = next((m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == '__init__'), None)
        if not init:
            return {}
        args = [a.arg for a in init.args.args if a.arg != 'self']
        bound = {p: literal(a, values) for p, a in zip(args[-len(init.args.defaults):], init.args.defaults)} if init.args.defaults else {}
        bound.update({p: literal(a, values) for p, a in zip(args, call.args)})
        bound.update({k.arg: literal(k.value, values) for k in call.keywords if k.arg})
        return bound

    def factory(self, call, unit):
        """Inline only a unique, single-return nn constructor factory as AST.

        No loops, assignments, side effects, dynamic argument binding or imports
        are executed. Evidence retains both the factory return and invocation.
        """
        if not isinstance(call, ast.Call):
            return None
        pair = self.definition(text(call.func), unit['cell']) or self.definition(text(call.func))
        if not pair or not isinstance(pair[1], ast.FunctionDef) or pair[1].decorator_list or pair[1].args.posonlyargs:
            return None
        source, fn = pair
        body = [n for n in fn.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Call):
            return None
        result = body[0].value
        if not self.resolve(text(result.func)).startswith('torch.nn.') or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            return None
        params = [a.arg for a in fn.args.args]
        if len(call.args) > len(params):
            return None
        bindings = dict(zip(params[-len(fn.args.defaults):], fn.args.defaults)) if fn.args.defaults else {}
        bindings.update(zip(params, call.args))
        for k in call.keywords:
            if k.arg not in params or k.arg in params[:len(call.args)]:
                return None
            bindings[k.arg] = k.value
        if any(p not in bindings for p in params):
            return None
        class Substitute(ast.NodeTransformer):
            def visit_Name(self, n):
                return copy.deepcopy(bindings[n.id]) if n.id in bindings else n
        return source, Substitute().visit(copy.deepcopy(result)), body[0]

    def call(self, cls_pair, *args, **kwargs):
        with self.scope(cls_pair[0]):
            return self._call(cls_pair, *args, **kwargs)

    def _call(self, cls_pair, parent, label, actuals, keywords, ctor, depth, module_path='', owner=None, ctor_objects=None, object_identity=None, owner_values=None, function_modules=None, forward_constants=None, object_reference=None):
        u, cls = cls_pair
        chosen = self.callable(cls) if isinstance(cls, ast.ClassDef) else cls
        symbol = cls.name + '.' + chosen.name if isinstance(cls, ast.ClassDef) and chosen else cls.name
        if depth > self.max_depth:
            return self.add('opaque', label + ' (depth limit)', parent, u, cls, symbol, reason='analysis-depth-limit')
        is_class = isinstance(cls, ast.ClassDef)
        fn = chosen
        if fn and (fn.decorator_list or is_class and cls.decorator_list):
            return self.add('opaque', label, parent, u, fn, symbol, reason='decorated-callable-unresolved')
        if fn:
            self.coverage_blockers.extend({'file': u['path'], 'line': n.lineno, 'kind': type(n).__name__} for n in ast.walk(fn) if isinstance(n, (ast.BoolOp, ast.Try, ast.Assert, ast.While, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)) and hasattr(n, 'lineno'))
        if not fn:
            return self.add('opaque', label, parent, u, cls, symbol, reason='no local forward or __call__ definition')
        local_shadowed = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
        local_shadowed.update(n.arg for n in ast.walk(fn) if isinstance(n, ast.arg))
        local_shadowed.update(a.asname or a.name.split('.')[0] for n in ast.walk(fn)
                              if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names)
        value_imports = {k: v for k, v in self.value_imports.items() if k not in local_shadowed}
        value_shadowed = self.value_shadowed | local_shadowed
        composite = self.add('composite', label, parent, u, fn, symbol,
                             semantic_type='source-module' if is_class else 'source-function', module_path=module_path,
                             constructor=ctor, source_class=cls.name if is_class else None)
        if object_identity is not None:
            self.node_by[composite]['module_identity'] = object_identity
        values = dict(self.globals)
        if is_class:
            init = next((m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == '__init__'), None)
            if init and init.args.defaults:
                params = [a.arg for a in init.args.args]
                values.update({p: literal(a, values) for p, a in zip(params[-len(init.args.defaults):], init.args.defaults)})
        values.update(owner_values or {})
        values.update(ctor)
        owner = cls if is_class else owner
        modules = self.module_map(owner, values) if owner is not None else {}
        from .construction import Construction, Module
        construction = Construction(self, u, owner, values, ctor_objects, object_identity if object_identity is not None else module_path,
                                    object_reference or 'entry')
        iteration_modules = dict(function_modules or {})
        iteration_paths = {name: spec.identity for name, spec in iteration_modules.items()}
        env = {}
        args = [a for a in fn.args.args if a.arg != 'self'] + fn.args.kwonlyargs
        positional = [a.arg for a in fn.args.args if a.arg != 'self']
        defaults = dict(zip(positional[-len(fn.args.defaults):], fn.args.defaults)) if fn.args.defaults else {}
        defaults.update({arg.arg: value for arg, value in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if value is not None})
        invocation_values = dict(forward_constants or {})
        for index, arg in enumerate(args):
            node = self.add('interface', arg.arg, composite, u, arg, symbol, role='input', slot=arg.arg)
            annotation = text(arg.annotation)
            head, *tail = annotation.split('.')
            if head in value_imports and '.'.join([value_imports[head], *tail]) == 'torch.Tensor':
                self.node_by[node]['source_tensor_annotation'] = 'torch.Tensor'
            env[arg.arg] = node
            binding = keywords.get(arg.arg) or (actuals[index] if index < len(actuals) else None)
            self.edge(binding, node, 'interface-binding', arg.arg)
            if depth > 0 and not binding and arg.arg not in invocation_values and arg.arg in defaults:
                default = literal(defaults[arg.arg], {})
                if default is None or type(default) in (bool, int, float, str):
                    invocation_values[arg.arg] = default
            if depth > 0 and not binding and arg.arg in invocation_values:
                self.node_by[node]['source_constant_input'] = {'value': invocation_values[arg.arg],
                    'scope': 'literal argument or default of this source invocation; other paths retained'}
        returned, write_scopes = [], []

        def rebound_target(target, bindings):
            # A forward-time write invalidates constructor-time module identity,
            # including writes to a containing object or module collection.
            writes = set().union(*write_scopes) if write_scopes else set()
            return next((name for name in sorted(writes) if name in bindings and (target == name or
                         target.startswith(name + '.') or target.startswith(name + '['))), None)

        def expr(n, scope, bindings):
            if n is None or isinstance(n, ast.Constant): return None
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)) and isinstance(n.operand, ast.Constant): return None
            if isinstance(n, ast.Subscript):
                node = self.add('compute', 'getitem · ' + text(n.slice)[:45], scope, u, n, symbol, operator='getitem', selector=text(n.slice))
                self.edge(expr(n.value, scope, bindings), node, target_port='value')
                def selector_dependencies(selector):
                    if isinstance(selector, ast.Slice):
                        return [x for x in (selector.lower, selector.upper, selector.step) if x is not None]
                    if isinstance(selector, ast.Tuple):
                        return [x for child in selector.elts for x in selector_dependencies(child)]
                    return [selector]
                for i, child in enumerate(selector_dependencies(n.slice)):
                    self.edge(expr(child, scope, bindings), node, target_port='index:' + str(i))
                return node
            if isinstance(n, ast.Name):
                if n.id in bindings: return bindings[n.id]
                key = 'global:' + n.id
                if key not in bindings:
                    bindings[key] = self.add('state' if n.id not in self.globals else 'buffer', n.id, scope, u, n, symbol,
                                             role='external-value', value=self.globals.get(n.id, {'unresolved': n.id}))
                    if n.id in value_imports:
                        self.node_by[bindings[key]]['framework_value_import'] = value_imports[n.id]
                return bindings[key]
            if isinstance(n, (ast.Tuple, ast.List, ast.Dict)):
                children = n.values if isinstance(n, ast.Dict) else n.elts
                node = self.add('compute', 'structured value', scope, u, n, symbol, operator='structure',
                                structure_kind=type(n).__name__.lower())
                for i, child in enumerate(children): self.edge(expr(child, scope, bindings), node, target_port=str(i))
                return node
            if isinstance(n, ast.Attribute):
                key = text(n)
                if key in bindings: return bindings[key]
                kind = 'state' if key.startswith('self.') else 'compute'
                node = self.add(kind, key, scope, u, n, symbol, operator='attribute', attribute_name=n.attr,
                                value=values.get(key, {'unresolved': key}))
                resource = construction.get(key) if rebound_target(key, bindings) is None else None
                if isinstance(resource, Module):
                    qualified = self.resolve(text(resource.call.func), self.expression_unit(resource.call, u))
                    if self.value_namespace(resource.call.func, u) and qualified == 'torch.nn.' + qualified.split('.')[-1] and qualified.split('.')[-1] in MODULES:
                        self.node_by[node].update(resource_framework_type=qualified,
                            resource_constructor={'args': [literal(a, resource.constants) for a in resource.call.args],
                                         'kwargs': {k.arg: literal(k.value, resource.constants) for k in resource.call.keywords if k.arg}},
                            module_resource=True,
                            module_resource_binding={'reference': resource.reference, 'selection': key,
                                            'construction_evidence': resource.evidence, 'allocation': resource.allocation})
                if not key.startswith('self.'): self.edge(expr(n.value, scope, bindings), node)
                bindings[key] = node
                return node
            if isinstance(n, ast.Call):
                target = text(n.func)
                if target.endswith('.forward') and target[:-8] in modules:
                    target = target[:-8]
                rebound = rebound_target(target, bindings)
                raw_module = modules.get(target) if rebound is None and target not in construction.blocked else None
                declared_factory = self.factory(raw_module, u)
                bound_module = (iteration_modules.get(target) or construction.get(target)) if rebound is None else None
                if bound_module is None and rebound is None and isinstance(n.func, ast.Subscript):
                    bound_module = construction.read(n.func, values, {**construction.objects, **iteration_modules}, target)
                if isinstance(bound_module, Module):
                    raw_module = bound_module.call
                factory = declared_factory or self.factory(raw_module, u)
                if factory: raw_module = factory[1]
                receiver = None
                # Receiver first, then positional and keyword expressions: preserve
                # dependencies (not an invented edge between adjacent statements).
                if isinstance(n.func, ast.Attribute):
                    chained = isinstance(n.func.value, (ast.Call, ast.Subscript))
                    bound_receiver = target.split('.')[0] in bindings
                    state_method = target.startswith('self.') and n.func.attr in FUNCTIONS and text(n.func.value) != 'self'
                    namespace = target.startswith(('torch.', 'nn.', 'F.', 'math.'))
                    if chained or (not namespace and (bound_receiver or state_method)):
                        receiver = expr(n.func.value, scope, bindings)
                actuals = [expr(a, scope, bindings) for a in n.args]
                kw = {k.arg: expr(k.value, scope, bindings) for k in n.keywords if k.arg}
                helper = None
                if rebound is None and owner is not None and target.startswith('self.') and target not in modules:
                    name = target[5:]
                    helper_fn = next((m for m in owner.body if isinstance(m, ast.FunctionDef) and m.name == name), None)
                    if helper_fn: helper = (u, helper_fn)
                elif rebound is None and self.definition(target) and isinstance(self.definition(target)[1], ast.FunctionDef):
                    helper = self.definition(target)
                if helper:
                    params = [a.arg for a in helper[1].args.args if a.arg != 'self']
                    supplied = dict(zip(params, n.args))
                    supplied.update({k.arg: k.value for k in n.keywords if k.arg})
                    callable_modules = {}
                    for name, argument in supplied.items():
                        spec = iteration_modules.get(text(argument)) or construction.get(text(argument))
                        if isinstance(spec, Module):
                            callable_modules[name] = spec
                    constants = {name: literal(argument, {}) for name, argument in supplied.items() if isinstance(argument, ast.Constant)}
                    return self.call(helper, scope, target, actuals, kw, ctor if helper[0] is u else {}, depth + 1, module_path, owner if helper[0] is u else None, ctor_objects if helper[0] is u else None, object_identity, values if helper[0] is u else None, callable_modules, constants, object_reference)
                if isinstance(raw_module, ast.Call):
                    display_name = target[5:] if target.startswith('self.') else target
                    bound_module = bound_module or construction.get(target)
                    module_values = bound_module.constants if isinstance(bound_module, Module) else values
                    constructor_name = text(raw_module.func)
                    short = self.resolve(constructor_name, self.expression_unit(raw_module, u)).split('.')[-1]
                    allocation_unit = self.expression_unit(raw_module, u)
                    with self.scope(allocation_unit):
                        local = self.definition(constructor_name, allocation_unit['cell']) or self.definition(constructor_name)
                    if local and isinstance(local[1], ast.ClassDef):
                        bound = construction.arguments(bound_module, local[1]) if isinstance(bound_module, Module) else None
                        v, refs = bound if bound is not None else (self.constructor_values(local[1], raw_module, values), {})
                        child_path = iteration_paths[target] if target in iteration_modules else (module_path + '.' + display_name).strip('.')
                        child_fn = self.callable(local[1])
                        child_params = [a.arg for a in child_fn.args.args if a.arg != 'self'] if child_fn else []
                        supplied = dict(zip(child_params, n.args)); supplied.update({k.arg: k.value for k in n.keywords if k.arg})
                        constants = {name: literal(argument, {}) for name, argument in supplied.items() if isinstance(argument, ast.Constant)}
                        before = len(self.nodes)
                        result = self.call(local, scope, display_name, actuals, kw, v, depth + 1,
                                         child_path, ctor_objects=refs,
                                         object_identity=bound_module.identity if isinstance(bound_module, Module) else None,
                                         forward_constants=constants,
                                         object_reference=bound_module.reference if isinstance(bound_module, Module) else None)
                        if isinstance(bound_module, Module) and before < len(self.nodes):
                            self.nodes[before]['module_binding'] = {
                                'reference': bound_module.reference, 'selection': target,
                                'construction_evidence': bound_module.evidence,
                                'allocation': bound_module.allocation}
                        return result
                    if short == 'Sequential' and self.resolve(constructor_name).startswith('torch.nn.'):
                        frame = self.add('composite', target[5:], scope, u, n, symbol, semantic_type='sequential', module_path=(module_path + '.' + target[5:]).strip('.'))
                        previous = actuals[0] if actuals else None
                        def sequential_child(child, previous, frame, path, child_label, level):
                            if level > self.max_depth:
                                sub = self.add('opaque', child_label, frame, u, child, symbol, reason='analysis-depth-limit')
                                self.edge(previous, sub, evidence='framework-contract')
                                return sub
                            if isinstance(child, ast.Call):
                                child_type = self.resolve(text(child.func))
                                child_short = child_type.split('.')[-1]
                                pair = self.definition(text(child.func), u['cell']) or self.definition(text(child.func))
                                if pair and isinstance(pair[1], ast.ClassDef):
                                    v = self.constructor_values(pair[1], child, values)
                                    return self.call(pair, frame, child_label + ': ' + child_short, [previous], {}, v, level + 1, path)
                                if child_type == 'torch.nn.Sequential':
                                    nested = self.add('composite', child_label + ': Sequential', frame, u, child, symbol, semantic_type='sequential', module_path=path)
                                    for j, item in enumerate(child.args):
                                        previous = sequential_child(item, previous, nested, path + '.' + str(j), str(j), level + 1)
                                    out = self.add('interface', 'out', nested, u, child, symbol, role='output')
                                    self.edge(previous, out, 'interface-binding', evidence='framework-contract')
                                    return out
                                known = child_type == 'torch.nn.' + child_short and child_short in MODULES
                                sub = self.add('compute' if known else 'opaque', child_label + ': ' + child_short, frame, u, child, symbol,
                                               operator=MODULES[child_short] if known else child_type, framework_type=child_type,
                                               module_path=path, constructor={'args': [literal(a, values) for a in child.args], 'kwargs': {k.arg: literal(k.value, values) for k in child.keywords if k.arg}})
                                if any(k.arg == 'inplace' and literal(k.value, values) is True for k in child.keywords):
                                    self.node_by[sub].update(mutable=True, effect_scope='sequential-call; external-aliases-unresolved')
                                    self.coverage_blockers.append({'file': u['path'], 'line': child.lineno,
                                                                   'kind': 'sequential-mutation-alias-unresolved'})
                            else:
                                sub = self.add('opaque', text(child)[:60], frame, u, child, symbol, reason='unresolved sequential child')
                            self.edge(previous, sub, evidence='framework-contract')
                            return sub
                        for i, child in enumerate(raw_module.args):
                            previous = sequential_child(child, previous, frame, (module_path + '.' + target[5:] + '.' + str(i)).strip('.'), str(i), depth + 1)
                        output = self.add('interface', 'out', frame, u, n, symbol, role='output')
                        self.edge(previous, output, 'interface-binding', evidence='framework-contract')
                        return output
                    qualified = self.resolve(constructor_name, self.expression_unit(raw_module, u))
                    known = qualified == 'torch.nn.' + short and short in MODULES and self.value_namespace(raw_module.func, self.expression_unit(raw_module, u))
                    operator = MODULES[short] if known else qualified
                    kind = 'compute' if known else 'opaque'
                    node = self.add(kind, f'{display_name} · {short}', scope, u, n, symbol, operator=operator,
                                    module_path=(module_path + '.' + display_name).strip('.') if target not in iteration_modules else iteration_paths[target],
                                    framework_type=qualified, constructor={'args': [literal(a, module_values) for a in raw_module.args], 'kwargs': {k.arg: literal(k.value, module_values) for k in raw_module.keywords if k.arg}})
                    if self.value_namespace(raw_module.func, u):
                        self.node_by[node]['source_framework_module'] = qualified
                    if isinstance(bound_module, Module):
                        self.node_by[node]['module_binding'] = {
                            'reference': bound_module.reference, 'selection': target,
                            'construction_evidence': bound_module.evidence,
                            'allocation': bound_module.allocation}
                    if object_identity is not None or target in iteration_modules:
                        self.node_by[node]['module_identity'] = bound_module.identity if isinstance(bound_module, Module) else (object_identity + '.' + display_name)
                    if factory:
                        self.node_by[node]['source'].extend(self.evidence(factory[0], factory[2], text(modules[target].func)))
                        self.node_by[node]['constructor_factory'] = text(modules[target].func)
                    # Parameter resources are separate from the compute call, and
                    # shapes/sharing remain unknown until a runtime observation.
                    if known and short in {'Linear', 'Conv1d', 'Conv2d', 'Conv3d', 'Embedding', 'LayerNorm', 'BatchNorm1d', 'BatchNorm2d'}:
                        resource = self.add('parameter', target[5:] + '.parameters', scope, self.expression_unit(raw_module, u), raw_module, symbol,
                                            parameter_scope=self.node_by[node]['module_path'], identity_status='declared-scope; sharing-unresolved')
                        if self.node_by[node].get('module_identity'):
                            self.node_by[resource]['module_identity'] = self.node_by[node]['module_identity']
                        self.edge(resource, node, 'parameter-read', evidence='framework-contract')
                else:
                    qualified = self.resolve(target)
                    short = target.split('.')[-1]
                    tensor_method = receiver is not None and short in FUNCTIONS
                    shadowed_callable = rebound and (target in modules or target == rebound)
                    scalar_cast = target in {'float', 'int', 'bool'} and len(n.args) == 1 and isinstance(n.args[0], ast.Constant) and not n.keywords and not self.definition(target) and target not in bindings
                    known = not shadowed_callable and ((qualified in {prefix + short for prefix in ('torch.', 'torch.nn.functional.', 'torch.nn.utils.rnn.', 'math.')} and target.split('.')[0] in value_imports or tensor_method or target in {'len', 'range', 'enumerate'}) and short in FUNCTIONS or scalar_cast)
                    node = self.add('compute' if known else 'opaque', short, scope, u, n, symbol,
                                    operator='scalar-cast' if scalar_cast else FUNCTIONS.get(short, qualified) if known else qualified, function_target=qualified,
                                    arguments={'args': [literal(a, values) for a in n.args],
                                               'kwargs': {k.arg: literal(k.value, values) for k in n.keywords if k.arg}},
                                    reason=None if known else 'rebound-call-target' if shadowed_callable else 'unresolved-call-target')
                    if target.split('.')[0] in value_imports:
                        self.node_by[node]['source_framework_function'] = qualified
                    if scalar_cast and target not in value_shadowed:
                        self.node_by[node]['source_scalar_cast'] = target
                if self.project_explicit and self.node_by[node]['kind'] == 'opaque':
                    declared = modules.get(target)
                    reason = ('conditional-constructor-binding' if target in construction.blocked else
                              'injected-constructor-object-unresolved' if isinstance(declared, (ast.Name, ast.Attribute)) else
                              'external-or-dynamic-call-target')
                    self.node_by[node]['unknown_boundary'] = {
                        'category': reason, 'target': target, 'qualified_target': qualified,
                        'source_file': u['path'], 'project_root': str(self.project.root),
                        'policy': 'source operands retained; no runtime execution or identity guess'}
                if rebound and (target in modules or target == rebound):
                    self.edge(bindings[rebound], node, target_port='callable')
                self.edge(receiver, node, target_port='receiver')
                for i, value in enumerate(actuals): self.edge(value, node, target_port=f'arg:{i}')
                for key, value in kw.items(): self.edge(value, node, target_port='kw:' + key)
                inplace = None
                if isinstance(raw_module, ast.Call):
                    inplace = next((literal(k.value, values) for k in raw_module.keywords if k.arg == 'inplace'), None)
                else:
                    inplace = next((literal(k.value, values) for k in n.keywords if k.arg == 'inplace'), None)
                method_effect = isinstance(n.func, ast.Attribute) and n.func.attr.endswith('_') and not n.func.attr.endswith('__')
                if method_effect or inplace is True:
                    self.node_by[node]['mutable'] = True
                    self.node_by[node]['effect_scope'] = 'direct-aliases-only; view-and-external-aliases-unresolved'
                    destination = n.func.value if method_effect and receiver else n.args[0] if n.args else None
                    apply_effect(destination, node, scope, bindings)
                return node
            if isinstance(n, ast.IfExp):
                control = self.add('control', text(n.test)[:70], scope, u, n.test, symbol, operator='if-expression')
                self.edge(expr(n.test, scope, bindings), control, 'control')
                self.branches.append({'id': control, 'file': u['path'], 'line': n.lineno, 'column': n.col_offset, 'outcomes': ['true', 'false'], 'kind': 'if-expression'})
                node = self.add('compute', 'conditional join', scope, u, n, symbol, operator='phi')
                self.edge(expr(n.body, scope, dict(bindings)), node, target_port='true', condition={'branch': control, 'outcome': 'true'})
                self.edge(expr(n.orelse, scope, dict(bindings)), node, target_port='false', condition={'branch': control, 'outcome': 'false'})
                self.edge(control, node, 'control')
                return node
            operators = {ast.BinOp: type(getattr(n, 'op', None)).__name__.lower(), ast.UnaryOp: 'unary', ast.Compare: 'compare', ast.BoolOp: 'boolean', ast.Subscript: 'getitem'}
            op = next((v for k, v in operators.items() if isinstance(n, k)), None)
            node = self.add('compute' if op else 'opaque', op or type(n).__name__, scope, u, n, symbol,
                            operator=op or 'unresolved-expression')
            for i, child in enumerate(ast.iter_child_nodes(n)):
                if isinstance(child, ast.expr): self.edge(expr(child, scope, bindings), node, target_port=str(i))
            return node

        def invalidate_reads(name, bindings):
            for key in list(bindings):
                if key.startswith(name + '.') or key.startswith(name + '['): del bindings[key]

        def apply_effect(destination, effect, scope, bindings):
            # Track proven whole-value aliases only. A view or custom object may
            # share storage, but source syntax alone does not establish that.
            base = destination
            while isinstance(base, ast.Subscript): base = base.value
            if not isinstance(base, (ast.Name, ast.Attribute)):
                self.node_by[effect].update(kind='opaque', evidence_status='opaque', glyph=GLYPHS['opaque'],
                                            reason='unresolved-mutation-receiver')
                self.coverage_blockers.append({'file': u['path'], 'line': self.node_by[effect]['source'][0]['line'],
                                               'kind': 'unresolved-mutation-receiver'})
                return
            name = text(base)
            before = expr(base, scope, bindings)
            self.edge(before, effect, 'state-write', target_port='previous')
            def origin(value):
                seen = set()
                while value and value not in seen:
                    seen.add(value)
                    item = self.node_by[value]
                    if item['kind'] != 'value-alias' or item.get('slot') is not None: break
                    incoming = next((e for e in self.edges if e['target'] == value and e['kind'] == 'alias'), None)
                    if not incoming: break
                    value = incoming['source']
                return value
            source = origin(before)
            affected = [key for key, value in bindings.items() if not key.startswith('global:') and origin(value) == source]
            for key in sorted(set(affected + [name])):
                invalidate_reads(key, bindings)
                bindings[key] = effect
                if write_scopes: write_scopes[-1].add(key)
            self.coverage_blockers.append({'file': u['path'], 'line': self.node_by[effect]['source'][0]['line'],
                                           'kind': 'mutation-alias-coverage-unresolved'})

        def assign(target, producer, scope, bindings, slot=None, writes=None):
            if isinstance(target, (ast.Tuple, ast.List)):
                for i, child in enumerate(target.elts): assign(child, producer, scope, bindings, f'{slot + "." if slot else ""}{i}', writes)
                return
            if isinstance(target, ast.Subscript):
                previous = expr(target, scope, bindings)
                store = self.add('opaque', 'setitem · ' + text(target.slice)[:45], scope, u, target, symbol,
                                 operator='setitem', selector=text(target.slice), mutable=True,
                                 reason='storage-alias-effects-unresolved',
                                 effect_scope='direct-aliases-only; view-and-external-aliases-unresolved')
                self.edge(previous, store, target_port='destination')
                self.edge(producer, store, target_port='value')
                apply_effect(target.value, store, scope, bindings)
                return
            name = text(target)
            # Cached reads belong to a particular binding generation. Rebinding
            # x must not make the next x.shape read reuse the previous producer.
            invalidate_reads(name, bindings)
            alias = self.add('state' if isinstance(target, ast.Attribute) else 'value-alias', name, scope, u, target, symbol, slot=slot)
            self.edge(producer, alias, 'state-write' if isinstance(target, ast.Attribute) else 'alias',
                      target_port=slot or 'value', source_port=slot if slot is not None else 'out')
            bindings[name] = alias
            if writes is not None: writes.add(name)

        def iteration(statement, scope, bindings):
            from .iteration import VERSION, loop_names
            names = loop_names(statement, bindings)
            if not names:
                return None
            # Speculation only lowers source; it never runs Python. A failed
            # proof restores all generated facts before the ordinary opaque
            # template is emitted, including IDs and control/effect receipts.
            checkpoint = (len(self.nodes), len(self.edges), len(self.branches),
                          len(self.coverage_blockers), dict(self.counts), dict(bindings))
            region = self.add('composite', 'Iteration', scope, u, statement, symbol,
                              semantic_type='iteration-region')
            control = self.add('control', ('for ' + text(statement.target) + ' in ' + text(statement.iter))[:90] if isinstance(statement, ast.For) else 'while ' + text(statement.test)[:80], region, u, statement, symbol,
                               operator='loop', loop_semantics='source-iteration-bindings; time-axis-and-count-unproved')
            self.branches.append({'id': control, 'file': u['path'], 'line': statement.lineno, 'kind': 'loop', 'outcomes': ['zero', 'nonzero'], 'path_coverage': 'unresolved'})
            frame = self.add('composite', 'loop body (source template)', region, u, statement, symbol, semantic_type='loop-template')
            self.edge(control, frame, 'control')
            loop_env, entries, initial_edges = dict(bindings), {}, {}
            for name in names:
                entry = self.add('state', name + ' · iteration entry', region, u, statement, symbol,
                                 operator='iteration-phi', role='iteration-entry',
                                 iteration={'loop': control, 'name': name})
                entries[name] = entry
                self.edge(bindings[name], entry, target_port='initial', iteration={'loop': control, 'phase': 'initial'})
                initial_edges[name] = self.edges[-1]['id']
                invalidate_reads(name, loop_env)
                loop_env[name] = entry
            before_guard = len(self.nodes)
            predicate = expr(statement.iter if isinstance(statement, ast.For) else statement.test,
                             scope if isinstance(statement, ast.For) else region,
                             bindings if isinstance(statement, ast.For) else loop_env)
            guard_nodes = [n['id'] for n in self.nodes[before_guard:]]
            self.edge(predicate, control, 'control')
            guard_edge = self.edges[-1]['id'] if predicate else None
            loop_writes = set()
            if isinstance(statement, ast.For):
                item = self.add('interface', 'iteration item', frame, u, statement.target, symbol,
                                role='iteration-item', iteration={'loop': control})
                self.edge(control, item, 'interface-binding', source_port='item', target_port='item')
                assign(statement.target, item, frame, loop_env, writes=loop_writes)
            loop_writes.update(statements(statement.body, frame, loop_env))
            generated = self.nodes[checkpoint[0]:]
            # A local variable read before its reaching definition must not be
            # mistaken for an external invariant on the next iteration.
            assigned = {n.id for child in statement.body for n in ast.walk(child)
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            rejected = (guard_edge is None or any(n['kind'] == 'opaque' or n.get('mutable')
                        or n.get('operator') == 'exception-exit'
                        or n.get('role') == 'external-value' and n['label'] in assigned
                        for n in generated) or any(e['kind'] == 'state-write' for e in self.edges[checkpoint[1]:]))
            if rejected:
                node_count, edge_count, branch_count, blocker_count, counts, old_bindings = checkpoint
                for n in self.nodes[node_count:]: self.node_by.pop(n['id'], None)
                del self.nodes[node_count:]
                del self.edges[edge_count:]
                del self.branches[branch_count:]
                del self.coverage_blockers[blocker_count:]
                self.counts = counts
                bindings.clear()
                bindings.update(old_bindings)
                return None
            contract = {'rule_version': VERSION, 'region': region, 'body': frame, 'guard_edge': guard_edge,
                        'guard_nodes': guard_nodes, 'loop_kind': 'for' if isinstance(statement, ast.For) else 'while',
                        'scope': 'source-name-bindings; normal-completion; zero-or-more-iterations',
                        'bindings': [], 'not_asserted': ['time axis', 'fixed count', 'termination',
                                                       'tensor shape', 'storage identity', 'purity']}
            for name, entry in entries.items():
                self.edge(loop_env[name], entry, target_port='backedge', iteration={'loop': control, 'phase': 'normal-completion'})
                backedge = self.edges[-1]['id']
                exit_node = self.add('state', name + ' · iteration result', scope, u, statement, symbol,
                                     operator='iteration-result', role='iteration-exit',
                                     iteration={'loop': control, 'name': name})
                self.edge(entry, exit_node, 'interface-binding', target_port='value', iteration={'loop': control, 'phase': 'exit'})
                exit_edge = self.edges[-1]['id']
                self.edge(control, exit_node, 'control', target_port='completion', iteration={'loop': control, 'phase': 'completion'})
                completion_edge = self.edges[-1]['id']
                reads = [e['id'] for e in self.edges[checkpoint[1]:]
                         if e['source'] == entry and e['id'] != exit_edge]
                contract['bindings'].append({'name': name, 'initial': bindings[name], 'entry': entry,
                    'body_value': loop_env[name], 'exit': exit_node, 'initial_edge': initial_edges[name],
                    'backedge': backedge, 'exit_edge': exit_edge, 'completion_edge': completion_edge, 'read_edges': reads})
                invalidate_reads(name, bindings)
                bindings[name] = exit_node
            # Variables introduced only inside the body (including the for
            # target) can be unbound on the zero-iteration path.
            for name in sorted(loop_writes - entries.keys()):
                join = self.add('opaque', name + ' · loop-carried value', scope, u, statement, symbol, reason='iteration-binding-unresolved')
                self.edge(bindings.get(name), join, target_port='initial')
                self.edge(loop_env.get(name), join, target_port='body')
                invalidate_reads(name, bindings)
                bindings[name] = join
            self.node_by[control]['iteration_contract'] = contract
            return loop_writes

        def statements(body, scope, bindings):
            written = set()
            write_scopes.append(written)
            for statement in body:
                if isinstance(statement, ast.Assign):
                    value = expr(statement.value, scope, bindings)
                    for target in statement.targets: assign(target, value, scope, bindings, writes=written)
                elif isinstance(statement, ast.AnnAssign):
                    if statement.value is not None:
                        assign(statement.target, expr(statement.value, scope, bindings), scope, bindings, writes=written)
                elif isinstance(statement, ast.AugAssign):
                    value = expr(ast.copy_location(ast.BinOp(left=statement.target, op=statement.op, right=statement.value), statement), scope, bindings)
                    if not isinstance(statement.target, ast.Subscript):
                        effect = self.add('opaque', 'augmented write · ' + text(statement.target), scope, u, statement, symbol,
                                          operator='augmented-write', mutable=True, reason='inplace-overload-unresolved',
                                          effect_scope='direct-aliases-only; view-and-external-aliases-unresolved')
                        self.edge(value, effect, target_port='value')
                        apply_effect(statement.target, effect, scope, bindings)
                        value = effect
                    assign(statement.target, value, scope, bindings, writes=written)
                elif isinstance(statement, ast.Return):
                    value = expr(statement.value, scope, bindings)
                    output = self.add('interface', 'return', scope, u, statement, symbol, role='output')
                    self.edge(value, output, 'interface-binding')
                    returned.append(output)
                    break
                elif isinstance(statement, ast.Raise):
                    # An explicit exceptional exit is known control flow. It is
                    # not an unresolved tensor-producing operation.
                    exit_node = self.add('control', 'raise ' + text(statement.exc)[:80], scope, u, statement, symbol,
                                         operator='exception-exit', exception_expression=text(statement.exc))
                    from .symbolic_values import EXCEPTIONS
                    if (isinstance(statement.exc, ast.Call) and isinstance(statement.exc.func, ast.Name)
                            and statement.exc.func.id in EXCEPTIONS - value_shadowed
                            and not statement.exc.keywords and not any(isinstance(a, ast.Starred) for a in statement.exc.args)
                            and statement.cause is None):
                        from .structure import syntax
                        self.node_by[exit_node]['exception_signature'] = {
                            'builtin': statement.exc.func.id, 'syntax': syntax(statement.exc),
                            'scope': 'source exceptional exit; reachability and execution not asserted'}
                    if isinstance(statement.exc, ast.Call):
                        for i, arg in enumerate(statement.exc.args):
                            self.edge(expr(arg, scope, bindings), exit_node, 'control', str(i))
                    self.coverage_blockers.append({'file': u['path'], 'line': statement.lineno, 'kind': 'exception-paths-not-verified'})
                    break
                elif isinstance(statement, ast.If):
                    control = self.add('control', text(statement.test)[:70], scope, u, statement.test, symbol, operator='if')
                    self.edge(expr(statement.test, scope, bindings), control, 'control')
                    self.branches.append({'id': control, 'file': u['path'], 'line': statement.lineno, 'column': statement.col_offset,
                                          'outcomes': ['true', 'false'], 'kind': 'if'})
                    alternatives, branch_writes = [], set()
                    for outcome, block in [('true', statement.body), ('false', statement.orelse)]:
                        frame = self.add('composite', outcome, scope, u, statement, symbol, semantic_type='conditional-region', condition={'branch': control, 'outcome': outcome})
                        self.edge(control, frame, 'control', outcome)
                        branch_env = dict(bindings)
                        branch_writes.update(statements(block, frame, branch_env))
                        alternatives.append(branch_env)
                    # Reading a property or external value does not assign it.
                    # Join actual writes only, never expression-cache entries.
                    for name in sorted(branch_writes):
                        a, b = alternatives[0].get(name), alternatives[1].get(name)
                        if a == b: continue
                        phi = self.add('value-alias', name + ' · branch join', scope, u, statement, symbol, operator='phi')
                        self.edge(a, phi, target_port='true', condition={'branch': control, 'outcome': 'true'})
                        self.edge(b, phi, target_port='false', condition={'branch': control, 'outcome': 'false'})
                        invalidate_reads(name, bindings)
                        bindings[name] = phi
                    written.update(branch_writes)
                elif isinstance(statement, (ast.For, ast.While)):
                    serial = construction.serial_loop(statement, fn)
                    if serial and rebound_target(text(statement.iter), bindings) is None:
                        collection, state, iterator = serial
                        identities = [m.reference for m in collection.elements]
                        sharing = 'independent' if len(set(identities)) == len(identities) else 'shared' if len(set(identities)) == 1 else 'mixed'
                        parameter_sharing = 'shared' if sharing == 'shared' and identities else 'independent' if identities and sharing == 'independent' and all(m.allocation in {'default-deepcopy', 'fresh-framework-construction'} for m in collection.elements) else 'unresolved'
                        contract = {'rule_version': 'bounded-module-sequence/1', 'count': len(identities),
                                    'state': state, 'iterator': iterator, 'collection': text(statement.iter),
                                    'instances': identities, 'module_sharing': sharing, 'parameter_sharing': parameter_sharing,
                                    'homogeneous': False,
                                    'allocation_evidence': [m.allocation for m in collection.elements],
                                    'construction_evidence': collection.evidence,
                                    'scope': 'fixed construction; straight serial body; all instances retained',
                                    'not_asserted': ['output equivalence between layers', 'arbitrary constructor side effects']}
                        frame = self.add('composite', 'Serial sequence · ' + str(len(identities)), scope, u, statement, symbol,
                                         semantic_type='serial-repeat', repeat_contract=contract)
                        # A module object is not a tensor carried value. Every concrete
                        # iteration has its own call and exact recurrent tensor binding.
                        for i, module in enumerate(collection.elements):
                            instance = self.add('composite', 'Layer ' + str(i + 1), frame, u, statement, symbol,
                                                semantic_type='repeat-instance', module_identity=module.reference,
                                                repeat_index=i)
                            iteration_modules[iterator] = module
                            iteration_paths[iterator] = '.'.join(filter(None, [module_path, text(statement.iter).removeprefix('self.'), str(i)]))
                            # A for target is rebound before each concrete call,
                            # including when an earlier loop used the same name.
                            invalidate_reads(iterator, bindings)
                            bindings.pop(iterator, None)
                            statements(statement.body, instance, bindings)
                        if collection.elements:
                            bindings[iterator] = self.add('state', iterator + ' · module reference', frame, u, statement.target, symbol,
                                                         role='module-reference', module_identity=identities[-1])
                            written.add(iterator)
                        written.add(state)
                        continue
                    loop_writes = iteration(statement, scope, bindings)
                    if loop_writes is not None:
                        written.update(loop_writes)
                        continue
                    control = self.add('control', ('for ' + text(statement.target) + ' in ' + text(statement.iter))[:90] if isinstance(statement, ast.For) else 'while ' + text(statement.test)[:80], scope, u, statement, symbol,
                                       operator='loop', loop_semantics='source-body-template; repetition-and-carried-state-unresolved')
                    self.branches.append({'id': control, 'file': u['path'], 'line': statement.lineno, 'kind': 'loop', 'outcomes': ['zero', 'nonzero'], 'path_coverage': 'unresolved'})
                    self.edge(expr(statement.iter if isinstance(statement, ast.For) else statement.test, scope, bindings), control, 'control')
                    frame = self.add('composite', 'loop body (source template)', scope, u, statement, symbol, semantic_type='loop-template')
                    self.edge(control, frame, 'control')
                    loop_env = dict(bindings)
                    loop_writes = set()
                    if isinstance(statement, ast.For): assign(statement.target, control, frame, loop_env, writes=loop_writes)
                    loop_writes.update(statements(statement.body, frame, loop_env))
                    for name in sorted(loop_writes):
                        join = self.add('opaque', name + ' · loop-carried value', scope, u, statement, symbol, reason='iteration-binding-unresolved')
                        self.edge(bindings.get(name), join, target_port='initial')
                        self.edge(loop_env.get(name), join, target_port='body')
                        invalidate_reads(name, bindings)
                        bindings[name] = join
                    written.update(loop_writes)
                elif isinstance(statement, ast.Expr): expr(statement.value, scope, bindings)
                elif isinstance(statement, (ast.Pass, ast.Import, ast.ImportFrom)): continue
                else:
                    self.add('opaque', type(statement).__name__, scope, u, statement, symbol, reason='unsupported-statement')
            write_scopes.pop()
            return written
        statements(fn.body, composite, env)
        if len(returned) == 1: return returned[0]
        output = self.add('interface', 'outputs / conditional returns', composite, u, fn, symbol, role='output')
        for i, value in enumerate(returned): self.edge(value, output, 'interface-binding', str(i))
        # A call-site default can select one normal return without deleting the
        # other source paths. Never specialize entry inputs or rebound guards.
        written_names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        safe_values = {k: v for k, v in invocation_values.items() if k not in written_names}
        def local_syntax(node):
            yield node
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                yield from local_syntax(child)
        def selected_return(body):
            for statement in body:
                if isinstance(statement, ast.Return): return statement.lineno
                if isinstance(statement, ast.If):
                    if isinstance(statement.test, ast.Name) and statement.test.id in safe_values:
                        found = selected_return(statement.body if bool(safe_values[statement.test.id]) else statement.orelse)
                        if found is not None: return found
                    elif any(isinstance(n, ast.Return) for n in ast.walk(statement)):
                        return -1
                elif not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and any(isinstance(n, ast.Return) for n in local_syntax(statement)):
                    # An unhandled try/with/match/loop may return before the
                    # following statements. Opaque control is not fallthrough.
                    return -1
            return None
        generator = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in local_syntax(fn))
        line = None if generator or isinstance(fn, ast.AsyncFunctionDef) else selected_return(fn.body)
        selected = [r for r in returned if self.node_by[r]['source'][0]['line'] == line]
        if len(selected) == 1:
            self.node_by[output]['return_selection'] = {'selected': selected[0], 'call_constants': safe_values,
                                                       'scope': 'normal-return paths of this invocation; source alternatives retained'}
        return output

    def factory_model(self, pair):
        """An explicit factory entry is analyzed, never run or guessed from names."""
        from .construction import Construction, Module
        unit, fn = pair
        if not isinstance(fn, ast.FunctionDef):
            raise ValueError('factory entry must be a source function')
        call = ast.Call(func=ast.Name(id=fn.name, ctx=ast.Load()), args=[],
                        keywords=[ast.keyword(arg=k, value=ast.parse(repr(v), mode='eval').body)
                                  for k,v in self.constructor.items()])
        ast.copy_location(call, fn)
        ast.fix_missing_locations(call)
        construction = Construction(self, unit, None, {}, {}, '', 'entry-factory')
        module = construction.read(call, {}, {}, 'factory-result')
        local = None
        if isinstance(module, Module):
            with self.scope(self.expression_unit(module.call, unit)):
                local = self.definition(text(module.call.func))
        if not local or not isinstance(local[1], ast.ClassDef):
            self.add('opaque', self.entry, None, unit, fn, fn.name,
                     reason='factory-result-not-proved; unsupported effect, return or construction')
            return
        bound = construction.arguments(module, local[1])
        if bound is None:
            self.add('opaque', self.entry, None, unit, fn, fn.name, reason='factory-constructor-binding-unresolved')
            return
        self.call(local, None, self.entry, [], {}, bound[0], 0,
                  ctor_objects=bound[1], object_identity=module.identity, object_reference=module.reference)
        self.nodes[0]['factory_binding'] = {'entry': self.entry, 'construction_evidence': module.evidence,
                                          'scope': 'bounded static factory; not an executed constructor'}

    def run(self):
        pair = self.definition(self.entry, self.cell)
        if pair is None:
            raise ValueError('entry missing or ambiguous; provide --cell for notebook redefinitions: ' + self.entry)
        if self.factory_entry:
            self.factory_model(pair)
        else:
            self.call(pair, None, self.entry, [], {}, self.constructor, 0)
        source_meta = [{k: u[k] for k in ('path', 'physical', 'cell', 'sha256', 'unit_sha256')} for loaded in self.project.loaded.values() for u in loaded]
        self.diagnostics.extend(self.project.diagnostics)
        ir = {'schema': SCHEMA, 'title': self.entry, 'entry': {'file': str(self.path), 'class': self.entry, 'cell': self.cell, 'constructor': self.constructor},
              'coverage_contract': COVERAGE_CONTRACT, 'sources': source_meta, 'nodes': self.nodes, 'edges': self.edges,
              'branches': self.branches, 'motifs': [], 'diagnostics': self.diagnostics,
              'runtime': {'status': 'not-requested', 'model_executed': False},
              'coverage_blockers': self.coverage_blockers,
              'coverage': {'status': 'not-verified', 'scope': 'static-source', 'complete': False,
                           'reason': 'static dependencies are not execution proof'},
              'limitations': ['Static edges express source dependencies, not observed tensor bindings.',
                              'Unresolved calls/loops/external definitions remain explicit opaque boundaries.',
                              'Mutation updates proven direct aliases only; views, external aliases and interprocedural effects remain unresolved.',
                              'Notebook cells are parsed as data; notebook setup/training cells are never executed.']}
        if self.project_explicit or self.factory_entry or len(self.project.loaded) > 1:
            ir['analysis'] = {'kind': 'static-source', 'project_root': str(self.project.root),
                              'loaded_files': len(self.project.loaded), 'file_budget': self.project.max_files,
                              'entry_kind': 'factory' if self.factory_entry else 'callable',
                              'imports_executed': False}
        from .identity import certify
        certify(self.nodes, self.edges)
        from .symbolic_values import certify as certify_values
        certify_values(self.nodes, self.edges)
        from .structure import certify as certify_structure
        certify_structure(self.nodes, self.edges)
        from .motifs import recognize
        recognize(ir)
        from .contracts import recognize_contracts
        recognize_contracts(ir)
        return seal(ir)


def analyze(source, entry, constructor=None, cell=None, **limits):
    return Analyzer(source, entry, constructor, cell, **limits).run()
