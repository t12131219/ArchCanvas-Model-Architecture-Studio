"""Explicit runtime supplementation of an unchanged, source-only IR."""
from copy import deepcopy
from pathlib import Path

from .merge import merge
from .probe import normalize_spec, observe
from .schema import digest, seal, source_graph_digest, validate_ir


def check_source(ir, root):
    """Check every extracted file, not just the entry point's generation."""
    if ir.get('authoring', {}).get('edited'):
        raise ValueError('编辑后的结构不能作为原始 Python 执行；请打开原始源码 IR')
    if ir.get('analysis', {}).get('entry_kind') == 'factory':
        raise ValueError('工厂入口暂不支持 CPU 探针；请使用明确的模型类入口')
    if ir.get('runtime', {}).get('status') not in (None, 'not-requested') or any(
            n['id'] == 'runtime-observations' or n['id'].startswith('runtime:') for n in ir['nodes']):
        raise ValueError('此图已包含运行凭据；重新运行请打开原始源码 IR，避免重复或混合运行证据')
    entry = ir['entry']
    if entry.get('cell') is not None or Path(entry['file']).suffix != '.py':
        raise ValueError('CPU 探针需要磁盘上的原始 .py 文件；笔记本暂仅支持静态分析')
    source = Path(entry['file']).resolve()
    if not source.is_relative_to(root):
        raise ValueError('入口源码必须位于所选源码根目录内')
    for item in ir['sources']:
        file = Path(item['physical']).resolve()
        if item.get('cell') is not None or not file.is_relative_to(root):
            raise ValueError('所有静态来源必须是所选根目录内的原始 Python 文件')
        if not file.is_file() or digest(file.read_bytes()) != item['sha256']:
            raise ValueError('源码缺失或已变化，请重新进行静态分析：' + str(file))
    return source


def assist(ir, interpreter, source_root, spec, timeout=45):
    """No inferred configuration, code generation, installation or auto probing."""
    if not isinstance(ir, dict) or not validate_ir(ir)['ok']:
        raise ValueError('需要有效的原始源码语义 IR')
    if ir.get('ir_digest') != digest({k: v for k, v in ir.items() if k != 'ir_digest'}):
        raise ValueError('IR 摘要不一致，请重新打开原始源码 IR')
    if not isinstance(interpreter, str) or not interpreter.strip():
        raise ValueError('请显式指定 Python 解释器')
    if not isinstance(source_root, str) or not source_root.strip():
        raise ValueError('请显式指定源码根目录')
    if type(timeout) is not int or not 1 <= timeout <= 90:
        raise ValueError('每个探针进程超时应为 1–90 秒')
    spec = normalize_spec(spec)
    if spec.get('constructor', {}) != ir['entry'].get('constructor', {}):
        raise ValueError('探针构造参数必须与当前静态 IR 一致；修改参数请先重新解析')
    root = Path(source_root).expanduser().resolve()
    source = check_source(ir, root)
    before = source_graph_digest(ir)
    receipt = observe(source, ir['entry']['class'], spec,
                      str(Path(interpreter).expanduser()), str(root), timeout)
    # Never attach observations to stale source, including helper definitions.
    check_source(ir, root)
    result = merge(deepcopy(ir), receipt)
    if source_graph_digest(result) != before:
        raise ValueError('运行补证改变了静态事实，结果未采用')
    boundaries = []
    for node in result['nodes']:
        if node['kind'] != 'opaque' or node['id'].startswith('runtime:'):
            continue
        observations = [v for v in node.get('runtime_evidence', []) if 'event' in v]
        boundaries.append({'node': node['id'], 'label': node['label'],
                           'status': 'source-line-associated' if observations else 'not-associated',
                           'observations': observations,
                           'resolved': False})
    summary = {'schema': 'archcanvas-probe-assistance/1', 'status': receipt['status'],
               'source_ir_digest': ir['ir_digest'], 'source_graph_digest': before,
               'reason': receipt.get('reason'), 'model_executed': receipt.get('model_executed'),
               'runs': [{'case': r['case'], 'mode': r['mode'], 'status': r['status'],
                         'operators': len(r.get('events', [])),
                         'module_calls': sum(e['event'] == 'enter' for e in r.get('module_events', [])),
                         'truncated': bool(r.get('truncated')), 'replay': r.get('replay'),
                         'reason': r.get('reason')} for r in receipt.get('runs', [])],
               'boundaries': boundaries, 'coverage': result['coverage'],
               'scope': 'declared inputs and modes only; source-line association is not operator equivalence',
               'static_unknowns_preserved': True}
    result['probe_assistance'] = summary
    seal(result)
    validation = validate_ir(result)
    if not validation['ok']:
        raise ValueError('补证结果校验失败：' + str(validation['errors']))
    return {'ir': result, 'summary': summary}
