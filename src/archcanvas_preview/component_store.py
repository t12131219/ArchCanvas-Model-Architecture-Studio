"""Persistent project components, extracted by the native static AST parser."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading

from .analyze import AdapterError, files_checked
from .component_library import SCHEMA, candidates, digest, extract, fingerprints, packed, short_name, validate_module

MAX_LIBRARY_BYTES = 128_000_000
MAX_IMPORT_BYTES = 32_000_000
_IMPORT = threading.BoundedSemaphore(1)


def project_components(files, entry, config=None, title=None):
    files = files_checked(files)
    if not isinstance(entry, str) or len(entry) > 300:
        raise AdapterError('请选择一个明确的模型入口。')
    if config is None:
        config = {}
    if not isinstance(config, dict) or len(packed(config)) > 16_000:
        raise AdapterError('构造参数必须为不超过 16 KB 的 JSON 对象。')
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 160):
        raise AdapterError('项目名称需为 1–160 字符。')
    payload = dict(files=files, entry=entry, config=config, title=title or entry)
    if not _IMPORT.acquire(blocking=False):
        raise AdapterError('另一个项目正在提取构件，请稍后重试。')
    try:
        bootstrap = 'import sys;sys.path.insert(0,sys.argv[1]);from archcanvas_preview.component_store import _worker;_worker()'
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', bootstrap, str(Path(__file__).resolve().parents[1])],
                                        input=packed(payload), stdout=output, stderr=subprocess.DEVNULL, timeout=20, check=False)
            except subprocess.TimeoutExpired as exc:
                raise AdapterError('项目静态解析超过 20 秒预算，构件库未更改。') from exc
            if result.returncode or output.tell() > MAX_IMPORT_BYTES:
                raise AdapterError('项目静态解析失败或超过资源预算，构件库未更改。')
            output.seek(0)
            response = json.load(output)
        if 'error' in response:
            raise AdapterError(response['error'])
        return response
    finally:
        _IMPORT.release()


def _worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_IMPORT_BYTES,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
        from .semantic_bridge import analyze_summary
        from archcanvas_summary_semantic.schema import validate_ir
        payload = json.load(sys.stdin)
        ir = analyze_summary(payload['files'], payload['entry'], payload['config'])['ir']['semantic_ir']
        if not validate_ir(ir)['ok']:
            raise ValueError('项目源码未通过原生语义校验。')
        project_id = digest([payload['files'], payload['entry'], payload['config']])
        modules, count = {}, 0
        for node in candidates(ir):
            count += 1
            module = extract(ir, node)
            validate_module(module)
            structure, variant = fingerprints(module)
            ident = 'src-' + variant[:24]
            origin = dict(model=project_id, title=payload['title'], node=node['id'], label=node['label'], name=module['title'],
                          irSha256=ir.get('ir_digest'), source=copy.deepcopy(node.get('source', [])))
            if ident in modules:
                modules[ident]['sourceLibrary']['origins'].append(origin)
                continue
            module['sourceLibrary'] = dict(schema=SCHEMA, id=ident, family='family-' + digest(['模块' if node['kind'] == 'composite' else '算子', module['title']])[:24],
                                           structure=structure, fingerprint=variant, category='模块' if node['kind'] == 'composite' else '算子', origins=[origin])
            modules[ident] = module
        if not modules:
            raise ValueError('当前入口中没有可提取的源码模块或算子。')
        response = dict(modules=modules, candidates=count, projectId=project_id, project=payload,
                        analysis=dict(mode='isolated-static-ast', modelExecuted=False, maxNodes=480, maxEdges=3600))
    except Exception as exc:
        response = {'error': str(exc)[:2000]}
    sys.stdout.buffer.write(packed(response))


class ComponentStore:
    def __init__(self, root: Path):
        self.root, self.lock = root, threading.RLock()
        self.path = root / 'library.json'

    def _read(self):
        return json.loads(self.path.read_bytes()) if self.path.exists() else {'schema': SCHEMA, 'modules': {}, 'projects': {}}

    def import_project(self, files, entry, config=None, title=None):
        result = project_components(files, entry, config, title)
        with self.lock:
            state = self._read()
            added, reused = 0, 0
            for ident, module in result['modules'].items():
                if ident not in state['modules']:
                    state['modules'][ident] = module
                    added += 1
                else:
                    reused += 1
                    origins = state['modules'][ident]['sourceLibrary']['origins']
                    for origin in module['sourceLibrary']['origins']:
                        if origin not in origins:
                            origins.append(origin)
            state['projects'][result['projectId']] = result['project']
            raw = packed(state)
            if len(raw) > MAX_LIBRARY_BYTES:
                raise AdapterError('项目构件库超过 128 MB 预算，原库保留。')
            self.root.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.library-', dir=self.root)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return dict(added=added, reused=reused, candidates=result['candidates'], projectId=result['projectId'], analysis=result['analysis'])

    def module(self, ident):
        if not re.fullmatch(r'src-[a-f0-9]{24}', ident):
            raise ValueError('源码构件身份无效。')
        with self.lock:
            module = self._read()['modules'].get(ident)
        if module is None:
            raise ValueError('项目构件不存在。')
        return module

    def catalog(self):
        with self.lock:
            state = self._read()
        families = {}
        for ident, module in state['modules'].items():
            library = module['sourceLibrary']
            family = families.setdefault(library['family'], dict(id=library['family'], title=module['title'], category=library['category'], aliases=[], variants=[]))
            family['aliases'] = sorted(set(family['aliases']) | {o['name'] for o in library['origins'] if o.get('name') and o['name'] != family['title']})
            raw = packed(module)
            config = []
            for node in module['ir']['nodes']:
                if node.get('constructor'):
                    record = dict(component=short_name(node), constructor=node['constructor'])
                    if record not in config:
                        config.append(record)
            family['variants'].append(dict(id=ident, structure=library['structure'], path=ident + '.json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                           nodes=len(module['ir']['nodes']), edges=len(module['ir']['edges']), configuration=config,
                                           occurrences=len(library['origins']), sources=sorted({o['title'] for o in library['origins']})))
        return dict(schema=SCHEMA, scope='project', families=sorted(families.values(), key=lambda f: f['title'].lower()),
                    stats=dict(candidates=sum(len(m['sourceLibrary']['origins']) for m in state['modules'].values()), families=len(families), variants=len(state['modules']), projects=len(state['projects'])))
