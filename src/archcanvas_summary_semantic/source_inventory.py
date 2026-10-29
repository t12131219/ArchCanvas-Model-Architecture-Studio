"""Advisory Python entry discovery. Inspect AST only, including hostile top-level code."""
import ast


def inspect_source(source):
    try:
        tree = ast.parse(source, filename='source.py')
    except SyntaxError as error:
        return {'candidates': [], 'recommended': None, 'diagnostics': [{'message': error.msg, 'line': error.lineno, 'column': error.offset}], 'executed': False}
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    aliases = {'torch.nn.Module', 'nn.Module'}
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module == 'torch.nn':
            aliases.update(a.asname or a.name for a in n.names if a.name == 'Module')
        if isinstance(n, ast.ImportFrom) and n.module == 'torch':
            aliases.update((a.asname or a.name) + '.Module' for a in n.names if a.name == 'nn')
        if isinstance(n, ast.Import):
            aliases.update((a.asname or a.name) + '.Module' for a in n.names if a.name == 'torch.nn')
    accepted = set()
    for _ in classes:
        for name, cls in classes.items():
            if any(ast.unparse(base) in aliases | accepted for base in cls.bases):
                accepted.add(name)
    dependencies = {name: {n.func.id for n in ast.walk(cls) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in accepted and n.func.id != name} for name, cls in classes.items() if name in accepted}
    used = set().union(*dependencies.values()) if dependencies else set()
    roots = [name for name in classes if name in accepted and name not in used]
    candidates = []
    for name, cls in classes.items():
        if name not in accepted:
            continue
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        init, forward = methods.get('__init__'), methods.get('forward')
        constructor, required, parameters = {}, [], []
        if init:
            args = [*init.args.posonlyargs, *init.args.args]
            defaults = dict(zip([a.arg for a in args[-len(init.args.defaults):]], init.args.defaults)) if init.args.defaults else {}
            defaults.update({a.arg: v for a, v in zip(init.args.kwonlyargs, init.args.kw_defaults) if v is not None})
            for arg in [*args[1:], *init.args.kwonlyargs]:
                default = defaults.get(arg.arg)
                parameters.append({'name': arg.arg, 'default': ast.unparse(default) if default else None})
                if default is None:
                    required.append(arg.arg)
                else:
                    try:
                        import json
                        value = ast.literal_eval(default)
                        json.dumps(value, allow_nan=False)
                        constructor[arg.arg] = value
                    except (ValueError, TypeError, OverflowError):
                        pass
        calls = [n for n in ast.walk(init) if isinstance(n, ast.Call) and ast.unparse(n.func) not in {'super', 'super().__init__'}] if init else []
        composition = bool(dependencies[name]) or len(calls) > 1
        candidates.append({'entry': name, 'line': cls.lineno, 'root': name in roots,
                           'suggestedMode': 'model' if name in roots and composition else 'module',
                           'dependencies': sorted(dependencies[name]), 'constructor': constructor, 'required': required, 'parameters': parameters,
                           'inputs': [a.arg for a in forward.args.args[1:]] if forward else [],
                           'reason': 'composition-root' if name in roots and composition else 'reusable-module'})
    return {'candidates': candidates, 'recommended': roots[0] if len(roots) == 1 else None,
            'diagnostics': [], 'executed': False, 'classification': 'advisory-structure-only'}
