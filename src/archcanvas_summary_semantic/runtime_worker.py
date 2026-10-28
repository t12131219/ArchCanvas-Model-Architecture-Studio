"""Executed only in the isolated, read-only source sandbox (never on import)."""
import ast
import contextlib
import hashlib
import importlib
import importlib.machinery
import inspect
import io
import json
import os
import resource
import sys
import traceback


def main(request):
    limits = request['limits']
    for key, value in [(resource.RLIMIT_AS, limits['memory_mb'] * 1024**2), (resource.RLIMIT_CPU, limits['cpu_seconds']),
                       (resource.RLIMIT_FSIZE, 8_000_000), (resource.RLIMIT_NOFILE, 96), (resource.RLIMIT_CORE, 0)]:
        resource.setrlimit(key, (value, value))
    if request.get('action') == 'probe':
        import socket
        checks = {'namespace_isolation': all(os.readlink('/proc/self/ns/' + n) != v for n, v in request['host_namespaces'].items()),
                  'host_root_hidden': not os.path.exists(request['host_root']), 'gpu_hidden': not os.path.exists('/dev/nvidia0')}
        for key, operation in [('network_denied', lambda: socket.socket()), ('process_denied', lambda: os.fork())]:
            try:
                result = operation()
                if key == 'process_denied' and result == 0: os._exit(0)
                if key == 'network_denied': result.close()
                checks[key] = False
            except OSError: checks[key] = True
        try:
            with open('/model/' + request['source_probe'], 'ab'): pass
            checks['source_readonly'] = False
        except OSError: checks['source_readonly'] = True
        return {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
                'mechanism': 'Bubblewrap namespaces + x86-64 seccomp; no network, new tasks or host HOME'}
    import torch
    from torch.utils._python_dispatch import TorchDispatchMode
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    runs, observed_branches = [], []
    branch_events = []
    def branch(file, line, column, outcome):
        result = bool(outcome)
        branch_events.append({'file': file, 'line': line, 'column': column, 'outcome': 'true' if result else 'false'})
        return result
    import builtins
    builtins.__archcanvas_branch__ = branch
    class Instrument(ast.NodeTransformer):
        def __init__(self, file): self.file = file
        def condition(self, node):
            self.generic_visit(node)
            node.test = ast.copy_location(ast.Call(func=ast.Name(id='__archcanvas_branch__', ctx=ast.Load()),
                args=[ast.Constant(self.file), ast.Constant(node.lineno), ast.Constant(node.col_offset), node.test], keywords=[]), node.test)
            return node
        visit_If = condition
        visit_IfExp = condition
    original = importlib.machinery.SourceFileLoader.get_code
    def get_code(loader, fullname):
        filename = loader.get_filename(fullname)
        if filename.startswith('/model/'):
            source = loader.get_data(filename).decode('utf-8-sig')
            tree = Instrument(filename[7:]).visit(ast.parse(source, filename=filename))
            return compile(ast.fix_missing_locations(tree), filename, 'exec')
        return original(loader, fullname)
    importlib.machinery.SourceFileLoader.get_code = get_code
    sys.path.insert(0, '/model')
    module_name, class_name = request['entry'].split(':')
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        module = importlib.import_module(module_name)
    model_class = getattr(module, class_name)
    tree_flatten = torch.utils._pytree.tree_flatten
    for case in request['cases']:
        for mode in request['modes']:
            seed = case.get('seed', 0)
            torch.manual_seed(seed)
            branch_events.clear()
            stack, events, objects, refs, module_events = [], [], {}, [], []
            truncated = [False]
            def tensors(value): return [x for x in tree_flatten(value)[0] if isinstance(x, torch.Tensor)]
            def metadata(tensor):
                return {'shape': list(tensor.shape), 'dtype': str(tensor.dtype), 'device': str(tensor.device), 'requires_grad': tensor.requires_grad}
            def register(t, producer, slot):
                identity = f't{len(refs)}'
                objects[id(t)] = {'id': identity, 'producer': producer, 'slot': slot, **metadata(t)}
                refs.append(t)  # bounded event budget prevents Python id reuse
                return dict(objects[id(t)])
            def ref(t):
                return dict(objects[id(t)]) if id(t) in objects else register(t, None, 'unresolved')
            def source_stack():
                result = []
                frame = inspect.currentframe()
                while frame:
                    if frame.f_code.co_filename.startswith('/model/'):
                        site = {'file': frame.f_code.co_filename[7:], 'line': frame.f_lineno, 'symbol': frame.f_code.co_qualname}
                        positions = getattr(inspect.getframeinfo(frame, context=0), 'positions', None)
                        if positions:
                            site.update(line=positions.lineno, end_line=positions.end_lineno,
                                        column=positions.col_offset, end_column=positions.end_col_offset)
                        result.append(site)
                        if len(result) >= 24:break
                    frame = frame.f_back
                return result
            class Recorder(TorchDispatchMode):
                def __torch_dispatch__(self, func, types, args=(), kwargs=None):
                    kwargs = kwargs or {}
                    if len(events) >= limits['max_events']:
                        truncated[0] = True
                        raise RuntimeError('runtime event budget exceeded')
                    identity = 'op' + str(len(events))
                    inputs = [ref(t) for t in tensors((args, kwargs))]
                    locations = source_stack()
                    event = {'id': identity, 'operator': str(func), 'module_path': stack[-1]['path'] if stack else '', 'module_call': stack[-1]['id'] if stack else None,
                             'source': locations[0] if locations else None, 'source_stack': locations, 'inputs': inputs, 'outputs': [],
                             'mutable': bool(func._schema.is_mutable)}
                    events.append(event)
                    result = func(*args, **kwargs)
                    event['outputs'] = [register(t, identity, i) for i, t in enumerate(tensors(result))]
                    return result
            hooks = []
            status, reason, capture = 'passed', None, {}
            try:
                with contextlib.redirect_stdout(log):
                    model = model_class(**request.get('constructor', {})).cpu()
                    model.train(mode == 'train')
                    parameter_aliases = {}
                    for name, tensor in model.named_parameters(remove_duplicate=False):
                        parameter_aliases.setdefault(id(tensor), []).append(name)
                    parameters = []
                    for name, tensor in model.named_parameters(remove_duplicate=False):
                        register(tensor, 'parameter:' + parameter_aliases[id(tensor)][0], name)
                        parameters.append({'name': name, 'aliases': parameter_aliases[id(tensor)], **metadata(tensor)})
                    buffers = []
                    for name, tensor in model.named_buffers(remove_duplicate=False):
                        register(tensor, 'buffer:' + name, name)
                        buffers.append({'name': name, **metadata(tensor)})
                    def pre(path):
                        def hook(m, args, kwargs):
                            call = {'id': 'call' + str(len(module_events)), 'path': path, 'parent_call': stack[-1]['id'] if stack else None, 'module_type': type(m).__module__ + '.' + type(m).__qualname__, 'source_stack': source_stack()}
                            bindings = []
                            for port, value in [*((f'arg:{i}', v) for i, v in enumerate(args)), *((f'kw:{k}', v) for k, v in kwargs.items())]:
                                values = tensors(value)
                                for t in values:bindings.append({**ref(t), 'port': port, 'component': not isinstance(value, torch.Tensor)})
                            stack.append(call); module_events.append({'event': 'enter', **call, 'inputs': [ref(t) for t in tensors((args, kwargs))], 'input_bindings': bindings})
                        return hook
                    def post(path):
                        def hook(m, args, output):
                            module_events.append({'event': 'exit', 'id': stack[-1]['id'] if stack else None, 'path': path, 'outputs': [ref(t) for t in tensors(output)], 'output_is_tensor': isinstance(output, torch.Tensor)})
                            if stack: stack.pop()
                        return hook
                    for path, child in model.named_modules():
                        hooks.extend([child.register_forward_pre_hook(pre(path), with_kwargs=True), child.register_forward_hook(post(path))])
                    def make_inputs(record=False):
                        values = {}
                        for name, spec in case['inputs'].items():
                            if 'value' in spec:
                                values[name] = spec['value']; continue
                            dtype = getattr(torch, spec.get('dtype', 'float32'))
                            fill = spec.get('fill', 'zeros')
                            kwargs = {'dtype': dtype, 'device': 'cpu'}
                            if fill == 'normal': value = torch.randn(spec['shape'], **kwargs)
                            elif fill == 'ones': value = torch.ones(spec['shape'], **kwargs)
                            else: value = torch.zeros(spec['shape'], **kwargs)
                            values[name] = value
                            if record: register(value, 'input:' + name, name)
                        return values
                    inputs = make_inputs(True)
                    with torch.no_grad(), Recorder():
                        output = model(**inputs)
                    flat = tensors(output)
                    outputs = [ref(t) for t in flat]
                    finite = all(bool(torch.isfinite(t).all()) for t in flat if t.is_floating_point())
                    if not finite: raise RuntimeError('nonfinite output')
                    # Capture is optional and independently diagnosed. Hooks are
                    # removed so exporter instrumentation does not pollute traces.
                    for h in hooks: h.remove()
                    hooks.clear()
                    run_branches = list(branch_events)
                    def output_digest(value):
                        result = []
                        for item in tree_flatten(value)[0]:
                            if isinstance(item, torch.Tensor):
                                tensor = item.detach().cpu().contiguous().clone()
                                result.append({'tensor': metadata(tensor), 'value_digest': hashlib.sha256(bytes(tensor.untyped_storage())).hexdigest()})
                            elif type(item) in (int, float, bool, str, type(None)):
                                result.append({'scalar': item})
                            else: raise ValueError('output type unsupported for replay verification: ' + type(item).__name__)
                        return hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
                    first_digest = output_digest(output)
                    torch.manual_seed(seed)
                    replay_model = model_class(**request.get('constructor', {})).cpu()
                    replay_model.train(mode == 'train')
                    replay_inputs = make_inputs()
                    with torch.no_grad(): replay_output = replay_model(**replay_inputs)
                    replay_digest = output_digest(replay_output)
                    if first_digest != replay_digest: raise RuntimeError('same-seed fresh-model replay output mismatch')
                    if request.get('export', False):
                        try:
                            ep = torch.export.export(model, (), kwargs=inputs)
                            capture = {'status': 'captured', 'nodes': [{'name': n.name, 'op': n.op, 'target': str(n.target),
                                'inputs': [a.name for a in n.all_input_nodes], 'module_stack': str(n.meta.get('nn_module_stack', {})),
                                'stack_trace': n.meta.get('stack_trace', '')[:1000]} for n in ep.graph.nodes],
                                'range_constraints': str(ep.range_constraints)}
                        except Exception as exc: capture = {'status': 'unsupported', 'reason': f'{type(exc).__name__}: {exc}'[:1500]}
                runs.append({'case': case['id'], 'mode': mode, 'seed': seed, 'status': status, 'events': events,
                             'module_events': module_events, 'parameters': parameters, 'buffers': buffers,
                             'outputs': outputs, 'replay': {'matched': True, 'output_digest': first_digest}, 'branches': run_branches, 'capture': capture, 'truncated': truncated[0]})
            except Exception as exc:
                runs.append({'case': case['id'], 'mode': mode, 'status': 'failed', 'reason': f'{type(exc).__name__}: {exc}',
                             'events': events, 'module_events': module_events, 'branches': list(branch_events), 'truncated': truncated[0]})
            finally:
                for h in hooks: h.remove()
    return {'schema': 'semantic-runtime/1', 'status': 'passed' if all(r['status'] == 'passed' for r in runs) else 'failed',
            'model_executed': True, 'framework': torch.__version__, 'framework_origin': torch.__file__, 'device': 'cpu', 'runs': runs,
            'instrumentation': 'AST if/ifexp outcomes + nn.Module hooks + TorchDispatchMode ATen operands',
            'limitations': ['Sample/finite-domain evidence only; not arbitrary Python verification.',
                            'Constructor/init branches observed; loops/exception/short-circuit paths not certified.',
                            'Instrumentation and model share the isolated process; receipts are not adversarial attestation.']}


if __name__ == '__main__':
    try:
        request = json.load(open(sys.argv[1]))
        result = main(request)
    except BaseException as exc:
        result = {'status': 'failed', 'model_executed': None, 'reason': f'{type(exc).__name__}: {exc}', 'traceback': traceback.format_exc()[-2000:]}
    print(json.dumps(result, allow_nan=False))
