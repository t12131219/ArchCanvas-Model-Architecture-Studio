#!/usr/bin/env python3
"""Bounded, no-execution source projection for the recursive Studio preview.

Migrated from Summary_Merge/source_adapter under the user's explicit preview
replacement request. The portable summary-source-adapter/1 contract is retained;
authoring and reviewed source transactions continue to use archcanvas_python.
Only standard-library AST parsing runs here, never supplied model code.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from importlib.resources import files as package_files
from pathlib import Path, PurePosixPath
from archcanvas_python.discovery import ModelIndex

REGISTRY = json.loads(package_files('archcanvas_preview').joinpath('registry.json').read_text(encoding='utf-8'))
MAX_FILES, MAX_BYTES, MAX_NODES, MAX_EDGES, MAX_DEPTH = 80, 2_000_000, 480, 3600, 10


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class AdapterError(ValueError):
    pass


def files_checked(files):
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise AdapterError('请选择 1–80 个 Python 源文件。')
    result = {}
    for name, text in files.items():
        if not isinstance(name,str):raise AdapterError('源码路径必须是字符串。')
        p = PurePosixPath(name.replace('\\', '/'))
        if p.is_absolute() or '..' in p.parts or p.suffix != '.py' or not isinstance(text, str):
            raise AdapterError('仅接受相对路径的 .py 文本。')
        if str(p) in result:raise AdapterError('源码路径重复。')
        result[str(p)] = text
    if sum(len(s.encode('utf-8')) for s in result.values()) > MAX_BYTES:
        raise AdapterError('源码总量超过 2 MB。')
    return result


class Analyzer:
    def __init__(self, files, config=None):
        self.files = files_checked(files)
        self.config = {} if config is None else config
        if not isinstance(self.config, dict):
            raise AdapterError('构造参数必须是 JSON 对象。')
        self.units, self.classes, self.nodes, self.edges = {}, {}, [], []
        self.evidence, self.diagnostics, self.instances = {}, [], {}
        self.active_opaque = False
        self.serial = 0
        for name, text in sorted(self.files.items()):
            try:
                tree = ast.parse(text, filename=name)
            except (SyntaxError, RecursionError) as e:
                raise AdapterError(f'{name}: Python 语法无法解析: {e}') from e
            imports = {}
            for stmt in tree.body:
                if isinstance(stmt, ast.Import):
                    for a in stmt.names:
                        imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
                if isinstance(stmt, ast.ImportFrom):
                    for a in stmt.names:
                        imports[a.asname or a.name] = ('.' * stmt.level) + (stmt.module + '.' if stmt.module else '') + a.name
            # A reassigned import cannot license a known PyTorch operator.
            for stmt in tree.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.FunctionDef, ast.ClassDef)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
                    for target in targets:
                        for n in ast.walk(target):
                            if isinstance(n, ast.Name): imports.pop(n.id, None)
                    if isinstance(stmt, ast.FunctionDef): imports.pop(stmt.name, None)
            module = name[:-3].replace('/', '.')
            if module == '__init__':
                module = ''
            elif module.endswith('.__init__'):
                module = module[:-9]
            self.units[name] = {'tree': tree, 'imports': imports, 'module': module}
            for c in tree.body:
                if isinstance(c, ast.ClassDef):
                    self.classes[module + ':' + c.name] = (name, c)
        self.model_index = ModelIndex(self.files)

    def span(self, file, node):
        snippet = ast.get_source_segment(self.files[file], node) or ast.unparse(node)
        data = {'file': file, 'line': node.lineno, 'endLine': node.end_lineno,
                'column': node.col_offset, 'endColumn': node.end_col_offset, 'expression': snippet}
        key = 'e-' + sha(canonical(data))[:16]
        self.evidence[key] = data
        return key

    def symbol(self, file, expr):
        name = ast.unparse(expr)
        first, dot, rest = name.partition('.')
        return self.units[file]['imports'].get(first, first) + (dot + rest if dot else '')

    def local(self, file, expr):
        resolved = self.model_index.resolve(self.model_index.symbol(file, expr))
        if resolved in self.classes:
            return resolved
        raw = ast.unparse(expr)
        module = self.units[file]['module']
        same = module + ':' + raw
        if same in self.classes:
            return same
        symbol = self.symbol(file, expr)
        mod, _, cls = symbol.rpartition('.')
        if mod.startswith('.'):
            # Resolve one or more dots relative to the importing package.
            level = len(mod) - len(mod.lstrip('.'))
            parts = module.split('.')[:-1]
            mod = '.'.join(parts[:len(parts)-level+1] + ([mod.lstrip('.')] if mod.lstrip('.') else []))
        key = mod + ':' + cls
        return key if key in self.classes else None

    def supported_class(self, key):
        file, cls = self.classes[key]
        hooks = {'__getattribute__', '__getattr__', '__setattr__'}
        order = self.model_index.mro(key)
        return (self.model_index.resolve(key) == key and self.model_index.is_module(key) and order is not None
                and not self.model_index.method_blocked(key, '__init__')
                and all(not definition.decorator_list and not any(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in hooks for n in definition.body)
                    for owner in order if owner in self.classes for _, definition in [self.classes[owner]]))

    def add(self, parent, kind, label, file, expr, **fields):
        if len(self.nodes) >= MAX_NODES:
            raise AdapterError('分析超过 480 个节点；请选择更小的模型入口。')
        self.serial += 1
        # Identity is source position plus call scope, independent of display placement.
        identity = f'{parent or "model"}/{kind}-{expr.lineno}-{expr.col_offset}-{self.serial}'
        node = {'id': identity, 'parent': parent, 'kind': kind, 'label': label,
                'source_evidence': [self.span(file, expr)], 'expression': ast.unparse(expr), **fields}
        self.nodes.append(node)
        return identity

    def refs(self, value):
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [r for v in value.values() for r in self.refs(v)]
        if isinstance(value, (list, tuple)):
            return [r for v in value for r in self.refs(v)]
        return []

    def connect(self, value, target, port, evidence, role='source_dependency'):
        for index, source in enumerate(self.refs(value)):
            if len(self.edges) >= MAX_EDGES:
                raise AdapterError('分析超过 3600 条依赖；请选择更小的模型入口。')
            self.edges.append({'id': f'edge-{len(self.edges)+1}', 'source': source, 'target': target,
                               'sourcePort': 'out', 'targetPort': port if len(self.refs(value)) == 1 else f'{port}[{index}]',
                               'wire': source + ':out', 'role': role, 'source_evidence': [evidence]})

    def diagnostic(self, file, expr, message, node):
        self.diagnostics.append({'node': node, 'evidence': self.span(file, expr), 'message': message})

    def literal(self, expr, values):
        if isinstance(expr, ast.Name) and expr.id in values:
            return values[expr.id]
        try:
            return ast.literal_eval(expr)
        except (ValueError, TypeError):
            return {'unresolved': ast.unparse(expr)}

    def spec(self, file, expr, values, identity, attrs):
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == 'self':
            return attrs.get(expr.attr, {'type': 'opaque', 'expression': ast.unparse(expr), 'identity': identity})
        if not isinstance(expr, ast.Call):
            return {'type': 'opaque', 'expression': ast.unparse(expr), 'identity': identity}
        symbol = self.symbol(file, expr.func)
        key = self.local(file, expr.func)
        data = {'identity': identity, 'file': file, 'span': self.span(file, expr),
                'expression': ast.unparse(expr), 'name': symbol.rsplit('.', 1)[-1],
                'args': [self.literal(a, values) for a in expr.args],
                'kwargs': {k.arg: self.literal(k.value, values) for k in expr.keywords if k.arg}}
        if any(isinstance(a, ast.Starred) for a in expr.args) or any(k.arg is None for k in expr.keywords):
            return {**data, 'type': 'opaque'}
        if key:
            return {**data, 'type': 'local', 'class': key}
        if symbol == 'torch.nn.Sequential' and not expr.keywords and not any(isinstance(a, ast.Starred) for a in expr.args):
            return {**data, 'type': 'sequential', 'children': [self.spec(file, a, values, identity + f'.{i}', attrs) for i, a in enumerate(expr.args)]}
        if symbol.startswith('torch.nn.') and symbol[9:] in REGISTRY['modules']:
            return {**data, 'type': 'module', 'kind': REGISTRY['modules'][symbol[9:]]}
        return {**data, 'type': 'opaque'}

    def registered_state_call(self, key, file, call, attrs, values, module_aliases):
        """Recognize Module state registration without running its producer.

        Buffer/parameter registration does not replace unrelated child modules.
        This narrow topology contract does not apply to an override, a dynamic
        destination, or a producer that receives this model or a child alias.
        Unknown initializer helpers retain the conservative opaque behavior.
        """
        if (not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != 'self' or call.func.attr not in ('register_buffer', 'register_parameter')
                or call.func.attr in attrs or self.model_index.method(key, call.func.attr)
                or self.model_index.method_blocked(key, call.func.attr)
                or any(unit['module'] == 'torch' or unit['module'].startswith('torch.') for unit in self.units.values())):
            return False
        names = ('name', 'tensor', 'persistent') if call.func.attr == 'register_buffer' else ('name', 'param')
        if (len(call.args) > len(names) or any(isinstance(arg, ast.Starred) for arg in call.args)
                or any(item.arg not in names for item in call.keywords)):
            return False
        arguments = dict(zip(names, call.args))
        if any(item.arg in arguments for item in call.keywords):
            return False
        arguments.update({item.arg: item.value for item in call.keywords})
        name = self.literal(arguments['name'], values) if 'name' in arguments else None
        value = arguments.get(names[1])
        if type(name) is not str or not name or '.' in name or name in attrs or value is None:
            return False
        if any(isinstance(part, ast.Name) and part.id in {'self', *module_aliases} for part in ast.walk(value)):
            return False
        if 'persistent' in arguments and type(self.literal(arguments['persistent'], values)) is not bool:
            return False
        return True

    def constructor(self, key, args, kwargs, instance):
        inherited = self.model_index.method(key, '__init__')
        file, init = inherited if inherited else (self.classes[key][0], None)
        attrs, values, module_aliases = {}, {}, set()
        if not isinstance(init, ast.FunctionDef) or init.decorator_list or init.args.vararg or init.args.kwarg:
            return attrs, values
        receivers = init.args.posonlyargs + init.args.args
        if (not receivers or receivers[0].arg != 'self'
                or any(p.arg == 'super' for p in [*receivers, *init.args.kwonlyargs])
                or any(isinstance(part, ast.Name) and part.id in ('self', 'super')
                       and isinstance(part.ctx, (ast.Store, ast.Del)) for part in ast.walk(init))):
            return attrs, values
        # The familiar spelling super().__init__ is a framework contract only
        # when the builtin was not rebound in this source module.
        for statement in self.units[file]['tree'].body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if statement.name == 'super':
                    return attrs, values
            elif (any(isinstance(part, ast.Name) and part.id == 'super' and isinstance(part.ctx, (ast.Store, ast.Del))
                      for part in ast.walk(statement)) or 'super' in self.units[file]['imports']):
                return attrs, values
        positional = (init.args.posonlyargs + init.args.args)[1:]
        keyword_only = list(init.args.kwonlyargs)
        parameters = positional + keyword_only
        defaults = dict(zip([p.arg for p in positional][-len(init.args.defaults):], init.args.defaults)) if init.args.defaults else {}
        defaults.update({p.arg: v for p, v in zip(init.args.kwonlyargs, init.args.kw_defaults) if v is not None})
        if len(args)>len(positional) or any(k not in [p.arg for p in parameters] for k in kwargs):
            return attrs, values
        if any(p.arg in kwargs for p in positional[:len(args)] + list(init.args.posonlyargs[1:])):
            return attrs, values
        for i, p in enumerate(positional):
            values[p.arg] = args[i] if i < len(args) else kwargs.get(p.arg, self.literal(defaults[p.arg], {}) if p.arg in defaults else {'unresolved': p.arg})
        for p in keyword_only:
            values[p.arg] = kwargs.get(p.arg, self.literal(defaults[p.arg], {}) if p.arg in defaults else {'unresolved': p.arg})
        for stmt in init.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                if any(isinstance(t,ast.Name) and t.id in self.units[file]['imports'] for t in targets):
                    return {}, values
                for t in targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self' and stmt.value:
                        attrs[t.attr] = self.spec(file, stmt.value, values, instance + '.' + t.attr, attrs)
                    elif isinstance(t, ast.Name) and stmt.value:
                        # Keep scalar aliases for state names, and remember
                        # local aliases of children so they cannot be passed to
                        # an unchecked state-producing helper as if harmless.
                        values[t.id] = self.literal(stmt.value, values)
                        if any(isinstance(n, ast.Name) and n.id in {'self', *module_aliases}
                               for n in ast.walk(stmt.value)):
                            module_aliases.add(t.id)
            elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                # A guarded assignment does not establish a selected instance.
                for t in ast.walk(stmt):
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'self' and isinstance(t.ctx, ast.Store):
                        attrs[t.attr] = {'type': 'opaque', 'identity': instance + '.' + t.attr, 'expression': ast.unparse(stmt)}
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                super_init = isinstance(call.func, ast.Attribute) and call.func.attr == '__init__' and isinstance(call.func.value, ast.Call) and isinstance(call.func.value.func, ast.Name) and call.func.value.func.id == 'super'
                if not super_init:
                    if self.registered_state_call(key, file, call, attrs, values, module_aliases):
                        continue
                    # An initializer helper can replace earlier attributes.
                    return {}, values
                if attrs or call.args or call.keywords:
                    return {}, values
            elif not isinstance(stmt, (ast.Pass, ast.Expr)):
                return {}, values
        return attrs, values

    def opaque(self, parent, file, expr, env, reason):
        identity = self.add(parent, 'opaque', '待解析 · ' + type(expr).__name__, file, expr, certainty='opaque')
        deps = []
        # Record only real variable dependencies, never adjacent statements.
        for n in ast.walk(expr):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in env:
                for r in self.refs(env[n.id]):
                    if r not in deps:
                        deps.append(r)
        for i, r in enumerate(deps):
            self.connect(r, identity, f'dependency[{i}]', self.span(file, expr))
        self.diagnostic(file, expr, reason, identity)
        return identity

    def invoke(self, spec, parent, file, call, args, kwargs, depth, stack):
        identity = spec.get('identity', ast.unparse(call.func) if isinstance(call, ast.Call) else 'entry')
        if spec['type'] == 'local' and (depth >= MAX_DEPTH or spec['class'] in stack or not self.supported_class(spec['class'])):
            spec = {**spec, 'type': 'opaque'}
        kind = 'group' if spec['type'] in ('local', 'sequential') else spec.get('kind', 'opaque')
        node = self.add(parent, kind, spec.get('name', 'Unresolved call'), file, call,
                        instance=identity, certainty='static' if kind != 'opaque' else 'opaque',
                        constructor=spec.get('expression'), moduleType=spec.get('name'),
                        constructorArgs=spec.get('args',[]), constructorKwargs=spec.get('kwargs',{}))
        self.instances.setdefault(identity, []).append(node)
        evidence = self.span(file, call)
        if spec['type'] not in ('local', 'sequential'):
            for i, arg in enumerate(args):
                self.connect(arg, node, f'arg[{i}]', evidence)
            for key, value in kwargs.items():
                self.connect(value, node, key, evidence)
            if kind == 'opaque':
                self.diagnostic(file, call, '外部或动态模块没有可验证的展开契约；保留调用及输入依赖。', node)
            return node
        if spec['type'] == 'sequential':
            inp = self.add(node, 'input', 'Sequential input', file, call)
            self.connect(args, inp, 'in', evidence)
            value = inp
            for child in spec['children']:
                value = self.invoke(child, node, file, call, [value], {}, depth+1, stack)
            out = self.add(node, 'output', 'Sequential output', file, call)
            self.connect(value, out, 'value', evidence)
            return out
        key = spec['class']
        method = self.model_index.effective_method(key)
        method_file, forward = method if method else (self.classes[key][0], None)
        attrs, values = self.constructor(key, spec.get('args', []), spec.get('kwargs', {}), identity)
        if not isinstance(forward, ast.FunctionDef) or forward.decorator_list or forward.args.vararg or forward.args.kwarg:
            self.nodes[next(i for i,n in enumerate(self.nodes) if n['id']==node)].update(kind='opaque',certainty='opaque')
            for i, arg in enumerate(args):
                self.connect(arg, node, f'arg[{i}]', evidence)
            for k, arg in kwargs.items():self.connect(arg,node,k,evidence)
            self.diagnostic(file, call, 'forward/__call__ 缺失、被装饰或签名动态，保留整体模块。', node)
            return node
        env = {}
        params = forward.args.posonlyargs + forward.args.args
        params = [p for p in params if p.arg != 'self'] + forward.args.kwonlyargs
        positional = [p for p in forward.args.posonlyargs + forward.args.args if p.arg != 'self']
        invalid = (len(args)>len(positional) or any(k not in [p.arg for p in params] for k in kwargs)
                   or any(p.arg in kwargs for p in positional[:len(args)] + forward.args.posonlyargs if p.arg != 'self'))
        defaults = dict(zip([p.arg for p in positional][-len(forward.args.defaults):], forward.args.defaults)) if forward.args.defaults else {}
        defaults.update({p.arg: v for p, v in zip(forward.args.kwonlyargs, forward.args.kw_defaults) if v is not None})
        if parent is not None and any(p.arg not in kwargs and p not in positional[:len(args)] and p.arg not in defaults for p in params):
            invalid = True
        if invalid:
            self.nodes[next(i for i,n in enumerate(self.nodes) if n['id']==node)].update(kind='opaque',certainty='opaque')
            self.connect(args,node,'args',evidence);self.connect(kwargs,node,'kwargs',evidence)
            self.diagnostic(file,call,'调用签名无法静态绑定。',node);return node
        for i, p in enumerate(params):
            external = args[i] if i < len(args) else kwargs.get(p.arg)
            if external is None and p.arg in defaults:
                default = defaults[p.arg]
                external = self.add(node, 'literal', ast.unparse(default), method_file, default)
            inp = self.add(node, 'input', p.arg, method_file, p)
            self.connect(external, inp, 'in', evidence)
            env[p.arg] = inp
        result = self.statements(forward.body, node, method_file, env, attrs, values, depth+1, stack+[key])
        if result is None:
            result = self.opaque(node, method_file, forward, env, '无法静态确定返回值。')
        def output(value, slot):
            if isinstance(value, list):
                return [output(v, f'{slot}[{i}]') for i,v in enumerate(value)]
            if isinstance(value, dict):
                return {k: output(v, f'{slot}[{k}]') for k,v in value.items()}
            out = self.add(node, 'output', slot, method_file, forward.body[-1])
            self.connect(value, out, 'value', self.span(method_file, forward.body[-1]))
            return out
        return output(result, 'return')

    def expression(self, expr, parent, file, env, attrs, values, depth, stack):
        if isinstance(expr, ast.Name) and expr.id in env:
            return env[expr.id]
        if isinstance(expr, ast.Constant):
            return self.add(parent, 'literal', ast.unparse(expr), file, expr)
        if isinstance(expr, (ast.Tuple, ast.List)):
            return [self.expression(v,parent,file,env,attrs,values,depth,stack) for v in expr.elts]
        if isinstance(expr, ast.Dict) and all(isinstance(k,ast.Constant) and isinstance(k.value,str) for k in expr.keys):
            return {k.value:self.expression(v,parent,file,env,attrs,values,depth,stack) for k,v in zip(expr.keys,expr.values)}
        if isinstance(expr, ast.Subscript):
            value = self.expression(expr.value,parent,file,env,attrs,values,depth,stack)
            try:
                index = ast.literal_eval(expr.slice)
                if isinstance(value,(list,dict)):
                    return value[index]
            except (ValueError,TypeError,KeyError,IndexError):
                pass
            node = self.add(parent,'index',ast.unparse(expr),file,expr,certainty='syntax')
            self.connect(value,node,'value',self.span(file,expr))
            for n in ast.walk(expr.slice):
                if isinstance(n,ast.Name) and n.id in env:
                    self.connect(env[n.id],node,'index',self.span(file,expr),'shape_dependency')
            return node
        if isinstance(expr, ast.BinOp):
            operation = REGISTRY['binary'].get(type(expr.op).__name__)
            if operation:
                left = self.expression(expr.left,parent,file,env,attrs,values,depth,stack)
                right = self.expression(expr.right,parent,file,env,attrs,values,depth,stack)
                node = self.add(parent,operation,ast.unparse(expr),file,expr,certainty='syntax')
                self.connect(left,node,'lhs',self.span(file,expr));self.connect(right,node,'rhs',self.span(file,expr))
                return node
        if isinstance(expr, ast.Call):
            if any(isinstance(a,ast.Starred) for a in expr.args) or any(k.arg is None for k in expr.keywords):
                return self.opaque(parent,file,expr,env,'展开参数无法静态绑定。')
            spec = None
            if isinstance(expr.func,ast.Attribute) and isinstance(expr.func.value,ast.Name) and expr.func.value.id=='self':
                spec = attrs.get(expr.func.attr)
            if spec:
                if spec.get('kwargs',{}).get('inplace') is not None and spec['kwargs']['inplace'] is not False:
                    return self.opaque(parent,file,expr,env,'原位运算的别名效应未解析；保留原调用。')
                args=[self.expression(a,parent,file,env,attrs,values,depth,stack) for a in expr.args]
                kwargs={k.arg:self.expression(k.value,parent,file,env,attrs,values,depth,stack) for k in expr.keywords}
                return self.invoke(spec,parent,file,expr,args,kwargs,depth,stack)
            symbol=self.symbol(file,expr.func)
            operation=REGISTRY['functions'].get(symbol)
            receiver=None
            if isinstance(expr.func,ast.Attribute) and isinstance(expr.func.value,ast.Name) and expr.func.value.id in env:
                operation=REGISTRY['tensor_methods'].get(expr.func.attr)
                receiver=env[expr.func.value.id]
            if operation:
                args=[self.expression(a,parent,file,env,attrs,values,depth,stack) for a in expr.args]
                kwargs={k.arg:self.expression(k.value,parent,file,env,attrs,values,depth,stack) for k in expr.keywords}
                node=self.add(parent,operation,ast.unparse(expr),file,expr,certainty='syntax')
                if receiver:self.connect(receiver,node,'receiver',self.span(file,expr))
                for i,a in enumerate(args):self.connect(a,node,f'arg[{i}]',self.span(file,expr))
                for k,a in kwargs.items():self.connect(a,node,k,self.span(file,expr),'shape_dependency' if k in ('dim','axis') else 'source_dependency')
                return node
            return self.opaque(parent,file,expr,env,'未注册调用，保留源码和实际变量依赖。')
        return self.opaque(parent,file,expr,env,'此表达式暂未有静态适配契约。')

    def assign(self,target,value,env,parent,file):
        if isinstance(target,ast.Name):
            env[target.id]=value
        elif isinstance(target,(ast.Tuple,ast.List)):
            if isinstance(value,list) and len(value)==len(target.elts):
                for t,v in zip(target.elts,value):self.assign(t,v,env,parent,file)
            else:
                for i,t in enumerate(target.elts):
                    node=self.add(parent,'index',f'output[{i}]',file,t,certainty='syntax')
                    self.connect(value,node,f'item[{i}]',self.span(file,t))
                    self.assign(t,node,env,parent,file)

    def statements(self,body,parent,file,env,attrs,values,depth,stack):
        def rest(index):
            region=ast.Module(body=body[index:],type_ignores=[])
            region.lineno=body[index].lineno;region.col_offset=body[index].col_offset
            region.end_lineno=body[-1].end_lineno;region.end_col_offset=body[-1].end_col_offset
            return region

        def mutates(call):
            if not isinstance(call,ast.Call):return False
            if isinstance(call.func,ast.Attribute) and call.func.attr.endswith('_'):return True
            if any(k.arg in ('inplace','out') and not (isinstance(k.value,ast.Constant) and k.value.value in (None,False)) for k in call.keywords):return True
            if isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='self':
                spec=attrs.get(call.func.attr,{})
                index=REGISTRY['inplace_module_positions'].get(spec.get('name'))
                value=spec.get('kwargs',{}).get('inplace',spec.get('args',[])[index] if index is not None and len(spec.get('args',[]))>index else False)
                return value not in (None,False)
            index=REGISTRY['inplace_function_positions'].get(self.symbol(file,call.func))
            return index is not None and len(call.args)>index and not (isinstance(call.args[index],ast.Constant) and call.args[index].value is False)

        for index, stmt in enumerate(body):
            # Mutating calls can alter variables reused later. Keep the whole
            # remaining region instead of claiming an unchanged skip path.
            unsafe = any(mutates(n) for n in ast.walk(stmt))
            shadow = isinstance(stmt,(ast.Assign,ast.AnnAssign)) and any(isinstance(n,ast.Name) and n.id in self.units[file]['imports'] for t in (stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]) for n in ast.walk(t))
            if unsafe or shadow:
                return self.opaque(parent,file,rest(index),env,'原位操作或导入名被重新绑定，剩余计算保留为待解析区域。')
            if isinstance(stmt,ast.Return):
                return self.expression(stmt.value,parent,file,env,attrs,values,depth,stack) if stmt.value else []
            if isinstance(stmt,(ast.Assign,ast.AnnAssign)) and stmt.value:
                targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]
                if any(not isinstance(t,(ast.Name,ast.Tuple,ast.List)) for t in targets):
                    return self.opaque(parent,file,rest(index),env,'有状态/切片赋值，保留剩余 forward 为不透明区域。')
                value=self.expression(stmt.value,parent,file,env,attrs,values,depth,stack)
                for t in targets:self.assign(t,value,env,parent,file)
            elif isinstance(stmt,ast.Expr) and isinstance(stmt.value,ast.Constant):
                continue
            elif isinstance(stmt,ast.Pass):
                continue
            else:
                # Do not draw an invented path through mutually exclusive arms
                # or silently ignore the effects of an unsupported statement.
                return self.opaque(parent,file,rest(index),env,'动态控制流或副作用；此后计算整体保留，不猜测执行路径。')
        return None

    def run(self,entry=None):
        candidates=[k for k in self.classes if self.model_index.resolve(k) == k and self.model_index.is_module(k) and self.model_index.effective_method(k)]
        matches=[k for k in candidates if entry in (k,k.rsplit(':',1)[-1])] if entry else candidates
        if len(matches)!=1:
            raise AdapterError('请指定模型入口 file.module:Class。候选：'+', '.join(candidates))
        key=matches[0];file,cls=self.classes[key]
        self.invoke({'type':'local','class':key,'name':cls.name,'identity':key,'args':[],
                     'kwargs':self.config,'expression':key},None,file,cls,[],{},0,[])
        ir={'schema':'summary-source-ir/1','entry':key,'nodes':self.nodes,'edges':self.edges,
            'instances':self.instances,'analysis':'static-source-dependencies','modelExecuted':False,
            'shapePolicy':'No tensor dimensions or execution path inferred',
            'registrySha256':sha(canonical(REGISTRY))}
        serial=canonical(ir)
        manifest=[{'path':p,'sha256':sha(s),'text':s} for p,s in sorted(self.files.items())]
        source_digest=sha(canonical([{k:v for k,v in f.items() if k!='text'} for f in manifest]))
        return {'schema':'summary-source-adapter/1','id':'source-'+sha(key+source_digest+serial)[:16],
                'title':cls.name,'entry':key,'files':manifest,'sourceSha256':source_digest,
                'ir':ir,'canonicalIR':serial,'irSha256':sha(serial),'evidence':self.evidence,
                'diagnostics':self.diagnostics,'config':self.config,'adapterVersion':1}


def analyze(files,entry=None,config=None):
    if entry is not None and not isinstance(entry, str):
        raise AdapterError('模型入口必须是字符串。')
    if config is not None:
        if not isinstance(config, dict):
            raise AdapterError('构造参数必须是 JSON 对象。')
        try:
            json.dumps(config, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise AdapterError('构造参数必须是有限的 JSON 字面量。') from exc
    try:
        bundle = Analyzer(files,config).run(entry)
        from archcanvas_adapters import enrich_preview
        return enrich_preview(bundle, files)
    except (RecursionError, TypeError, AttributeError) as exc:
        raise AdapterError('源码超出静态分析的支持范围或嵌套预算。') from exc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,help='Python file or repository directory')
    parser.add_argument('--entry',help='module:Class or unambiguous Class')
    parser.add_argument('--config',default='{}',help='JSON constructor literals (no execution)')
    parser.add_argument('--out',type=Path,required=True,help='Portable source adapter JSON bundle')
    args=parser.parse_args()
    base=args.source if args.source.is_dir() else args.source.parent
    paths=sorted(args.source.rglob('*.py')) if args.source.is_dir() else [args.source]
    paths=[p for p in paths if not p.is_symlink() and not any(v in ('.git','.venv','venv','__pycache__') for v in p.relative_to(base).parts)]
    if len(paths)>MAX_FILES:parser.error('源码多于 80 文件；请选择模型子目录。')
    try:
        files={str(p.relative_to(base)):p.read_text(encoding='utf-8-sig') for p in paths}
        bundle=analyze(files,args.entry,json.loads(args.config))
    except (ValueError,OSError,RecursionError) as e:parser.error(str(e))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
    print(f'{bundle["title"]}: {len(bundle["ir"]["nodes"])} nodes, {len(bundle["ir"]["edges"])} edges, {len(bundle["diagnostics"])} opaque diagnostics → {args.out}')


if __name__=='__main__':main()
