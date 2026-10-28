"""Bounded, non-executing project imports. Never consult sys.path/site-packages."""
import ast
from pathlib import Path
from .sources import units


class Project:
    def __init__(self, source, root=None, max_files=128):
        source = Path(source).resolve()
        inferred = source.parent
        while (inferred / '__init__.py').is_file():
            inferred = inferred.parent
        self.root = Path(root).resolve() if root else inferred
        if not source.is_relative_to(self.root):
            raise ValueError('source must be within project root')
        self.max_files, self.loaded, self.owners, self.diagnostics = max_files, {}, {}, []

    def register(self, path, values):
        self.loaded[Path(path).resolve()] = values
        for unit in values:
            for node in ast.walk(unit['tree']):
                self.owners[id(node)] = unit

    def owner(self, node):
        return self.owners.get(id(node))

    def load(self, path):
        path = path.resolve()
        if not path.is_relative_to(self.root):
            return []
        if path not in self.loaded:
            if len(self.loaded) >= self.max_files:
                self.diagnostics.append({'file': str(path), 'kind': 'project-file-budget'})
                return []
            try:
                values, diagnostics = units(path)
                self.diagnostics.extend(diagnostics)
                self.register(path, values)
            except (OSError, ValueError) as error:
                self.diagnostics.append({'file': str(path), 'kind': 'project-source-unavailable', 'reason': str(error)})
                return []
        return self.loaded[path]

    def module(self, name, unit, level=0):
        base = Path(unit['physical']).parent if level else self.root
        for _ in range(max(0, level - 1)):
            base = base.parent
        target = base.joinpath(*(name.split('.') if name else []))
        # Ambiguous module/package or escaping symlinks are not selected.
        candidates = [p.resolve() for p in (target.with_suffix('.py'), target / '__init__.py')
                      if p.is_file() and p.resolve().is_relative_to(self.root)]
        return candidates[0] if len(candidates) == 1 else None

    def definition(self, name, unit, seen=None):
        seen = set(seen or ())
        key = (unit['path'], name)
        if key in seen or len(seen) >= 32:
            return None
        seen.add(key)
        head, *tail = name.split('.')
        tree = unit['tree']
        declarations, imports = [], []
        for statement in tree.body:
            if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name == head:
                declarations.append(statement)
            if isinstance(statement, ast.Import):
                imports.extend((statement, a) for a in statement.names if (a.asname or a.name.split('.')[0]) == head)
            if isinstance(statement, ast.ImportFrom):
                imports.extend((statement, a) for a in statement.names if a.name != '*' and (a.asname or a.name) == head)
        # Any write, conditional definition/import or star import makes lookup uncertain.
        for statement in tree.body:
            if isinstance(statement, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(statement, ast.ImportFrom) and any(a.name == '*' for a in statement.names):
                    return None
                continue
            for node in ast.walk(statement):
                if (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == head
                        or isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == head
                        or isinstance(node, ast.alias) and (node.asname or node.name.split('.')[0]) == head):
                    return None
        if len(declarations) + len(imports) != 1:
            return None
        if declarations:
            return (unit, declarations[0]) if not tail else None
        statement, alias = imports[0]
        if isinstance(statement, ast.ImportFrom):
            path = self.module(statement.module, unit, statement.level)
            if path:
                values = self.load(path)
                if len(values) == 1:
                    result = self.definition('.'.join([alias.name, *tail]), values[0], seen)
                    if result:
                        return result
            # from package import submodule
            module_name = '.'.join(filter(None, [statement.module, alias.name]))
            path = self.module(module_name, unit, statement.level)
            if path and tail:
                values = self.load(path)
                return self.definition('.'.join(tail), values[0], seen) if len(values) == 1 else None
        elif tail:
            # `import pkg.mod` binds pkg; `import pkg.mod as x` binds the full module.
            qualified = '.'.join([alias.name if alias.asname else head, *tail])
            parts = qualified.split('.')
            for split in range(len(parts)-1, 0, -1):
                path = self.module('.'.join(parts[:split]), unit)
                if path:
                    values = self.load(path)
                    return self.definition('.'.join(parts[split:]), values[0], seen) if len(values) == 1 else None
        return None
