"""Conservative, source-preserving Python export of the *current* authored graph.

Reference reconstruction is supported only when every fact has been restored.
New compositions support source capsules connected by explicit module interfaces.
Editing a capsule's internals invalidates its executable source binding.
"""
import ast
import base64
import hashlib
import io
import json
import keyword
import zipfile
from .authoring import compile_module


def _rows(rows):
    return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) for row in rows)


def _remap(value, mapping):
    if isinstance(value, list):
        return [_remap(v, mapping) for v in value]
    if isinstance(value, dict):
        return {mapping.get(k, k): _remap(v, mapping) for k, v in value.items()}
    return mapping.get(value, value) if isinstance(value, str) else value


def _bound_module(binding):
    if not isinstance(binding, dict) or not isinstance(binding.get('source'), str) or not isinstance(binding.get('entry'), str):
        raise ValueError('当前图没有完整的可执行源码绑定；请通过源码窗口导入模型或源码构件。')
    from .source_inventory import inspect_source
    candidate = next((c for c in inspect_source(binding['source'])['candidates'] if c['entry'] == binding['entry']), None)
    if candidate is None:
        raise ValueError('Python 生成需要可识别的 nn.Module 类。')
    constructor = binding.get('constructor', {})
    if not isinstance(constructor, dict) or any(name not in constructor for name in candidate['required']):
        raise ValueError('请填写完整的构造参数后重新解析源码。')
    return compile_module(binding['source'], binding['entry'], constructor)


def _factory(source, entry, constructor):
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    factory = 'build_model'
    while factory in names:
        factory = '_' + factory
    return source.rstrip() + '\n\n\ndef ' + factory + '():\n    return ' + entry + '(**' + repr(constructor) + ')\n', factory


def generate_python(document):
    if not isinstance(document, dict) or document.get('schema') != 'semantic-authoring/1':
        raise ValueError('需要当前语义编辑文档。')
    nodes, edges = document.get('nodes', []), document.get('edges', [])
    if not nodes or len(nodes) > 480 or len(edges) > 3600:
        raise ValueError('Python 生成仅支持 1–480 节点 / 3600 依赖。')
    by = {n['id']: n for n in nodes}
    if len(by) != len(nodes) or len({e['id'] for e in edges}) != len(edges) or any(e['source'] not in by or e['target'] not in by for e in edges):
        raise ValueError('生成图的身份或端点无效。')
    reference = document.get('codeReference')
    if reference:
        compiled = _bound_module(reference)
        if _rows(nodes) != _rows(compiled['ir']['nodes']) or _rows(edges) != _rows(compiled['ir']['edges']):
            raise ValueError('当前图与绑定源码不同或参考重建未完成，不能导出旧源码。请重新解析源码或完成精确重建。')
        source, factory = _factory(compiled['source'], compiled['entry'], compiled['constructor'])
        files, mode = {'generated_model.py': source}, 'exact-source-reconstruction'
        mapping = {'reference': compiled['entry']}
    else:
        files, source, factory, mapping = _composition(document)
        mode = 'source-module-composition'
    for name, text in files.items():
        compile(text, name, 'exec')  # Syntax only. Never import submitted Python.
    manifest = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        for name, text in files.items():
            package.writestr(name, text)
        package.writestr('README.txt', f'Python / PyTorch export\nEntry: generated_model:{factory}\nMode: {mode}\nStatic generation only; execution and shape compatibility are not certified.\n')
    return {'schema': 'archcanvas-summary-python/1', 'files': files, 'source': source, 'entry': 'generated_model:' + factory,
            'mode': mode, 'mapping': mapping, 'sha256': manifest, 'archiveBase64': base64.b64encode(archive.getvalue()).decode(),
            'documentSha256': hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
            'analysis': {'modelExecuted': False, 'syntaxValidated': True, 'sourcePreserved': True}}


def _composition(doc):
    nodes, edges = doc['nodes'], doc['edges']
    by = {n['id']: n for n in nodes}
    definitions = doc.get('modules', {})
    roots = [n for n in nodes if not n.get('parent')]
    components = [n for n in roots if n['id'] in definitions and definitions[n['id']].get('source')]
    interfaces = [n for n in roots if n.get('kind') == 'interface']
    if len(components) + len(interfaces) != len(roots) or not components or len(components) > 24:
        raise ValueError('仅支持顶层源码构件和显式输入输出；未知原子、分组或无源码构件需先转为源码模块。')
    files, owner, internal_edges, ports, mapping = {}, {}, set(), {}, {}
    for index, root in enumerate(components):
        identity, binding = root['id'], definitions[root['id']]
        compiled = _bound_module(binding)
        ids = binding.get('codeBinding')
        if not isinstance(ids, dict):
            raise ValueError('源码构件缺少可验证身份映射；请重新解析并替换构件。')
        expected_nodes = _remap(compiled['ir']['nodes'], ids)
        expected_edges = _remap(compiled['ir']['edges'], ids)
        inside = {identity}
        for _ in nodes:
            added = {n['id'] for n in nodes if n.get('parent') in inside} - inside
            if not added:
                break
            inside.update(added)
        if _rows(expected_nodes) != _rows([n for n in nodes if n['id'] in inside]) or _rows(expected_edges) != _rows([e for e in edges if e['source'] in inside and e['target'] in inside]):
            raise ValueError('源码构件内部结构已修改，不能用原源码导出。请重新解析源码。')
        for key in inside:
            owner[key] = identity
        internal_edges.update(e['id'] for e in expected_edges)
        inputs = [n for n in expected_nodes if n.get('parent') == identity and n.get('role') == 'input' and n['kind'] == 'interface']
        outputs = [n for n in expected_nodes if n.get('parent') == identity and n.get('role') == 'output' and n['kind'] == 'interface']
        if len(outputs) != 1:
            raise ValueError('每个源码构件必须具有一个结构化返回值。')
        filename = f'component_{index}.py'
        files[filename], factory = _factory(binding['source'], binding['entry'], binding.get('constructor', {}))
        ports[identity] = {'inputs': inputs, 'output': outputs[0], 'factory': factory, 'index': index}
        mapping[identity] = f'blocks.{index}'
    if len(owner) + len(interfaces) != len(nodes):
        raise ValueError('图包含未归属、循环或无效的模块层级，不能忽略节点。')
    external = [e for e in edges if e['id'] not in internal_edges]
    drivers = {}
    for e in external:
        key = (e['target'], str(e['target_port']))
        if key in drivers or e.get('condition') is not None or e.get('kind') != 'data':
            raise ValueError('外部连接必须是单驱动数据依赖；条件、反馈或重复输入不能直接生成。')
        drivers[key] = e
    inputs = [n for n in interfaces if n.get('role') == 'input']
    outputs = [n for n in interfaces if n.get('role') == 'output']
    if not inputs or not outputs or len(inputs) + len(outputs) != len(interfaces):
        raise ValueError('请添加并连接模型的输入和输出接口。')
    names = [n['label'] for n in inputs]
    if len(set(names)) != len(names) or any(not s.isidentifier() or keyword.iskeyword(s) or s in {'self', '_values'} for s in names):
        raise ValueError('模型输入名称必须是唯一的 Python 参数名。')
    values = {(n['id'], 'out'): n['label'] for n in inputs}
    lines = ['from torch import nn']
    lines += [f'from component_{p["index"]} import {p["factory"]} as _build_{p["index"]}' for p in ports.values()]
    lines += ['', 'class AuthoredModel(nn.Module):', '    def __init__(self):', '        super().__init__()',
              '        self.blocks = nn.ModuleList([' + ', '.join(f'_build_{i}()' for i in range(len(components))) + '])', '',
              '    def forward(self, ' + ', '.join(names) + '):', '        _values = {}']
    remaining, consumed = dict(ports), set()
    while remaining:
        progress = False
        for identity, p in list(remaining.items()):
            args, used = [], []
            for n in p['inputs']:
                edge = drivers.get((n['id'], 'in'))
                if not edge:
                    raise ValueError('源码构件存在未连接输入：' + n['label'])
                expression = values.get((edge['source'], str(edge['source_port'])))
                if expression is None:
                    break
                # Python forward parameters are positional unless explicitly keyword-only.
                args.append((n['label'], expression)); used.append(edge['id'])
            else:
                tree = ast.parse(definitions[identity]['source'])
                cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == definitions[identity]['entry'])
                forward = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'forward'), None)
                if not forward or forward.args.vararg or forward.args.kwarg:
                    raise ValueError('组合生成需要明确的 forward 参数；继承或可变参数请作为完整模型导入。')
                posonly = {a.arg for a in forward.args.posonlyargs}
                arguments = ', '.join(value if name in posonly else name + '=' + value for name, value in args)
                expression = f'_values[{p["index"]}]'
                lines.append(f'        {expression} = self.blocks[{p["index"]}]({arguments})')
                values[(p['output']['id'], 'out')] = expression
                consumed.update(used); del remaining[identity]; progress = True
        if not progress:
            raise ValueError('图存在环路或连接到了源码模块内部原子；请通过模块接口连接。')
    results = []
    for n in outputs:
        edge = drivers.get((n['id'], 'in'))
        expression = values.get((edge['source'], str(edge['source_port']))) if edge else None
        if expression is None:
            raise ValueError('模型输出未连接到有效结果。')
        consumed.add(edge['id']); results.append(expression)
    if consumed != {e['id'] for e in external}:
        raise ValueError('存在不能还原成 Python 的外部连接；没有忽略任何连接。')
    lines += ['        return ' + (results[0] if len(results) == 1 else '(' + ', '.join(results) + ')'), '',
              'def build_model():', '    return AuthoredModel()', '']
    source = '\n'.join(lines); files['generated_model.py'] = source
    return files, source, 'build_model', mapping
