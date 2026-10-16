"""Source-bound inspection instances and reusable, declarative source rules.

The v1 inspector and v2 rule evaluator independently reconstruct their facts.
Neither accepts Python hooks, tensor contracts or source-generation authority.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from collections import deque
from functools import lru_cache
from pathlib import Path, PurePosixPath

SCHEMA = 'archcanvas-source-adapter/1'
MAX_FILES, MAX_BYTES, MAX_NODES, MAX_EDGES = 80, 2_000_000, 480, 1440
MAX_DEFINITION_BYTES = 2_000_000
_ID = re.compile(r'adapter-[a-f0-9]{24}')


class AdapterError(ValueError):
    """A safe, actionable adapter validation or stale-source error."""


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise AdapterError('Adapter data must contain finite JSON values only.') from exc


def _sha(value):
    return hashlib.sha256((value if isinstance(value, bytes) else value.encode('utf-8'))).hexdigest()


def merge_rules(*groups):
    """Validate and deduplicate user and registry templates by canonical ID."""
    from .source_rules import validate_rule, MAX_RULES
    merged = {}
    for group in groups:
        if group is None:
            continue
        if isinstance(group, dict):
            group = [group]
        if not isinstance(group, (list, tuple)):
            raise AdapterError('Rules must be a rule object or array of templates.')
        for payload in group:
            definition = validate_rule(payload)
            merged[definition['id']] = definition
            if len(merged) > MAX_RULES:
                raise AdapterError('A rule adapter accepts at most 16 distinct source rule templates.')
    return [merged[identity] for identity in sorted(merged)]


def _checked_files(files):
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise AdapterError('Adapter source needs 1–80 Python files.')
    result = {}
    for name, text in files.items():
        if not isinstance(name, str) or '\\' in name:
            raise AdapterError('Source paths must use relative POSIX paths.')
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or path.suffix != '.py' or str(path) != name or not isinstance(text, str):
            raise AdapterError('Only normalized relative .py paths are accepted.')
        if any(not part.isidentifier() for part in path.with_suffix('').parts):
            raise AdapterError('Source paths must correspond to Python module names.')
        result[name] = text
    if sum(len(text.encode('utf-8')) for text in result.values()) > MAX_BYTES:
        raise AdapterError('Adapter source exceeds the 2 MB source budget.')
    return result


def _root_files(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise AdapterError('Project root is not a directory.')
    paths = [path for path in sorted(root.rglob('*.py')) if not path.is_symlink()
             and not any(part in {'.git', '.venv', 'venv', '__pycache__'} for part in path.relative_to(root).parts)]
    if len(paths) > MAX_FILES:
        raise AdapterError('Adapter source exceeds 80 files; choose a smaller source root.')
    files = {}
    try:
        for path in paths:
            if not path.resolve().is_relative_to(root) or path.stat().st_size > MAX_BYTES:
                raise AdapterError('Source escapes its root or exceeds the source budget.')
            files[path.relative_to(root).as_posix()] = path.read_bytes().decode('utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise AdapterError(f'Cannot read selected source: {exc}') from exc
    return _checked_files(files)


def _corpus(files):
    from archcanvas_python.frontend import Corpus, AnalysisError
    corpus = Corpus()
    try:
        for path, text in sorted(files.items()):
            module = path[:-3].replace('/', '.')
            if module.endswith('.__init__'):
                module = module[:-9]
            elif module == '__init__':
                module = ''
            corpus.add(module, path, text)
    except (AnalysisError, RecursionError, MemoryError) as exc:
        raise AdapterError(f'Source cannot be statically inspected: {exc}') from exc
    return corpus


def _entry(corpus, entry, method):
    if not isinstance(entry, str) or entry.count(':') != 1:
        raise AdapterError('Adapter entry must be module:Class or module:function.')
    module, name = entry.split(':')
    if not module or any(not part.isidentifier() for part in module.split('.')) or not name.isidentifier():
        raise AdapterError('Adapter entry must name a local Python symbol.')
    unit = corpus.units.get(module)
    if unit is None:
        raise AdapterError('Adapter entry module is absent from supplied source.')
    matches = [node for node in unit.tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
    if len(matches) != 1:
        raise AdapterError('Adapter entry must identify exactly one directly authored local symbol.')
    symbol = matches[0]
    method_unit = unit
    definition = symbol if isinstance(symbol, ast.ClassDef) else None
    if isinstance(symbol, ast.ClassDef):
        if method is None:
            resolved = corpus.entry_method(unit, symbol)
        else:
            if not isinstance(method, str) or not method.isidentifier():
                raise AdapterError('Adapter method must be a Python identifier.')
            from archcanvas_python.discovery import ModelIndex
            index = ModelIndex({own.path: own.content for own in corpus.units.values()})
            located = index.method(entry, method)
            resolved = None
            if located and isinstance(located[1], ast.FunctionDef) and not located[1].decorator_list:
                own = next((own for own in corpus.units.values() if own.path == located[0]), None)
                if own:
                    # Use the matching AST object from the formal Corpus.
                    matching = [node for node in ast.walk(own.tree) if isinstance(node, ast.FunctionDef)
                                and node.lineno == located[1].lineno and node.name == located[1].name]
                    if len(matching) == 1:
                        resolved = own, matching[0]
        if not resolved:
            raise AdapterError('No unambiguous directly authored local method resolves through this class hierarchy.')
        method_unit, function = resolved
        method = function.name
        definition = next((candidate for candidate in method_unit.classes.values()
                           if candidate.lineno <= function.lineno <= candidate.end_lineno), symbol)
    else:
        if method not in (None, name):
            raise AdapterError('A function adapter method must match the function name.')
        method, function = name, symbol
    return unit, symbol, function, method, method_unit, definition


def _source(unit, node):
    return {'path': unit.path, 'line': node.lineno, 'endLine': node.end_lineno,
            'column': node.col_offset, 'endColumn': node.end_col_offset,
            'expression': ast.get_source_segment(unit.content, node) or ast.unparse(node)}


def _interfaces(unit, symbol, function):
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    if isinstance(symbol, ast.ClassDef):
        positional = positional[1:]
    defaults = dict(zip([item.arg for item in positional][-len(args.defaults):], args.defaults)) if args.defaults else {}
    defaults.update({item.arg: value for item, value in zip(args.kwonlyargs, args.kw_defaults) if value is not None})
    inputs = []
    for index, arg in enumerate([*positional, *args.kwonlyargs]):
        item = {'id': f'input-{index}', 'name': arg.arg, 'kind': 'source-parameter',
                'required': arg.arg not in defaults, 'source': _source(unit, arg)}
        if arg in args.posonlyargs:
            item['parameterKind'] = 'positional-only'
        elif arg in args.kwonlyargs:
            item['parameterKind'] = 'keyword-only'
        else:
            item['parameterKind'] = 'positional-or-keyword'
        if arg.arg in defaults:
            item['defaultSource'] = _source(unit, defaults[arg.arg])
        inputs.append(item)
    for prefix, arg in (('varargs', args.vararg), ('kwargs', args.kwarg)):
        if arg:
            inputs.append({'id': prefix, 'name': arg.arg, 'kind': 'variadic-source-parameter', 'required': False, 'source': _source(unit, arg)})
    outputs = []
    def slots(node, path):
        if isinstance(node, (ast.Tuple, ast.List)):
            for index, value in enumerate(node.elts):
                yield from slots(value, [*path, {'kind': 'index', 'index': index}])
        elif isinstance(node, ast.Dict) and all(isinstance(key, ast.Constant) and type(key.value) in (str, int, bool, type(None)) for key in node.keys):
            for key, value in zip(node.keys, node.values):
                yield from slots(value, [*path, {'kind': 'key', 'key': key.value}])
        elif node is not None:
            yield node, path
    class Returns(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is function:
                for statement in node.body:
                    self.visit(statement)
        def visit_AsyncFunctionDef(self, node):
            pass
        def visit_ClassDef(self, node):
            pass
        def visit_Return(self, node):
            for expression, path in slots(node.value, []):
                outputs.append({'id': f'return-{node.lineno}-{node.col_offset}-{len(outputs)}',
                                'path': path, 'kind': 'source-return-slot', 'source': _source(unit, expression)})
    Returns().visit(function)
    return inputs, outputs


def _presentation(value, child_ids):
    if not isinstance(value, dict) or set(value) != {'labels', 'notes'} or not isinstance(value['labels'], dict) or not isinstance(value['notes'], list):
        raise AdapterError('presentation must contain labels and notes only.')
    if set(value['labels']) - child_ids:
        raise AdapterError('Presentation labels must refer to existing source facts.')
    texts = [*value['labels'].values(), *value['notes']]
    if len(value['notes']) > 32 or any(not isinstance(item, str) or not 1 <= len(item) <= 240 or any(ord(char) < 32 for char in item) for item in texts):
        raise AdapterError('Adapter labels/notes require bounded plain text.')
    return copy.deepcopy(value)


def _graph_checked(children, dependencies):
    if not isinstance(children, list) or not isinstance(dependencies, list) or len(children) > MAX_NODES or len(dependencies) > MAX_EDGES:
        raise AdapterError('Adapter exceeds its 480-child/1440-relation budget.')
    ids = {node['id'] for node in children}
    if len(ids) != len(children):
        raise AdapterError('Adapter child identities must be unique.')
    parents = {node['id']: node.get('parentId') for node in children}
    for identity in ids:
        seen, cursor = set(), identity
        while cursor is not None:
            if cursor not in parents or cursor in seen:
                raise AdapterError('Adapter containment is cyclic or refers to an unknown child.')
            seen.add(cursor)
            cursor = parents[cursor]
            if len(seen) > 12:
                raise AdapterError('Adapter source hierarchy exceeds depth 12.')
    adjacency = {identity: set() for identity in ids}
    for edge in dependencies:
        if edge['sourceId'] not in ids or edge['targetId'] not in ids or edge['sourceId'] == edge['targetId']:
            raise AdapterError('Adapter dependency refers to invalid source facts.')
        adjacency[edge['sourceId']].add(edge['targetId'])
    visiting, done = set(), set()
    def visit(identity):
        if identity in visiting:
            raise AdapterError('Adapter dependencies form a cycle; retain an opaque boundary instead.')
        if identity not in done:
            visiting.add(identity)
            for target in adjacency[identity]:
                visit(target)
            visiting.remove(identity); done.add(identity)
    for identity in ids:
        visit(identity)


def _scaffold_adapter_files(files, entry, method=None, config=None):
    """Produce reproducible source facts using the shared formal AST inspector."""
    from archcanvas_python.frontend import Analyzer, AnalysisError
    from archcanvas_python.source_structure import SourceStructure
    files = _checked_files(files)
    config = {} if config is None else config
    if not isinstance(config, dict) or len(_canonical(config).encode()) > 32_000:
        raise AdapterError('Adapter config must be a JSON object of at most 32 KB.')
    corpus = _corpus(files)
    unit, symbol, function, method, method_unit, definition = _entry(corpus, entry, method)
    class EvidenceAnalyzer(Analyzer):
        def source(self, own_unit, node):
            return _source(own_unit, node)
    analyzer = EvidenceAnalyzer(corpus)
    root = analyzer.node('adapter-root', symbol.name, 'SourceAdapter', 'container', None, method_unit, function)
    structure = SourceStructure(analyzer, MAX_NODES)
    structure.flow_roots.append((function.body, method_unit, root['id']))
    structure.flow_functions[root['id']] = function
    try:
        structure.block(function.body, method_unit, definition, root['id'], 0, ())
        relations = structure.populate([])
    except (AnalysisError, RecursionError, AttributeError, TypeError) as exc:
        raise AdapterError(f'Source inspection exceeded its supported subset: {exc}') from exc
    children = copy.deepcopy(analyzer.nodes[1:])
    # A module card points to its construction in __init__, while its call can
    # live inside a different method/opaque region. Preserve both locations in
    # the inspection instance so selecting a region cannot lose real modules.
    # This metadata belongs to the adapter, not the formal tensor graph.
    by_id = {child['id']: child for child in children}
    calls = {id(call): (own, call) for body, own, _ in structure.flow_roots
             for statement in body for call in ast.walk(statement) if isinstance(call, ast.Call)}
    for (_, call_id), targets in structure.call_nodes.items():
        if call_id not in calls:
            continue
        own, call = calls[call_id]
        source = _source(own, call)
        for target in targets:
            child = by_id.get(target)
            if child and child['kind'] == 'SourceModule':
                sites = child['parameters'].setdefault('callSites', [])
                if source not in sites:
                    sites.append(source)
    for child in children:
        if child.get('parentId') == root['id']:
            child['parentId'] = None
        child['ports'] = []
    # SourceStructure's logical inspection depth counts branch bodies once;
    # the portable preview counts both condition and branch cards. Trim the
    # actual containment tree to its stricter 12-level contract explicitly.
    allowed, pending = set(), list(children)
    depths = {}
    while pending:
        progressed = False
        for child in list(pending):
            parent = child.get('parentId')
            if parent is not None and parent not in depths:
                continue
            pending.remove(child); progressed = True
            depths[child['id']] = depths.get(parent, 0) + 1
            if depths[child['id']] <= 12 and (parent is None or parent in allowed):
                allowed.add(child['id'])
        if not progressed:
            break
    if len(allowed) < len(children):
        analyzer.warn('Portable adapter containment reached its 12-level budget; omitted descendants remain in the original source.')
        children = [child for child in children if child['id'] in allowed]
    ids = {node['id'] for node in children}
    dependencies = [item for item in relations if item['sourceId'] in ids and item['targetId'] in ids][:MAX_EDGES]
    # Shared definition cards can induce a cycle even when individual calls do
    # not. Keep that ambiguity explicit instead of exporting an invented DAG.
    kept = []
    for relation in dependencies:
        try:
            _graph_checked(children, [*kept, relation])
        except AdapterError:
            analyzer.warn('An ambiguous cyclic dependency between shared definition cards was retained in source only.')
        else:
            kept.append(relation)
    inputs, outputs = _interfaces(method_unit, symbol, function)
    binding = {'entry': entry, 'method': method, 'sourceFiles': [{'path': path, 'sha256': _sha(text)} for path, text in sorted(files.items())],
               'symbol': {**_source(unit, symbol), 'qualifiedName': entry},
               'methodSpan': {**_source(method_unit, function), 'sha256': _sha(method_unit.expression(function))}}
    core = {'schema': SCHEMA, 'generatorRevision': 'source-inspection/3', 'binding': binding, 'config': copy.deepcopy(config), 'inputs': inputs, 'outputs': outputs,
            'children': children, 'dependencies': kept, 'diagnostics': analyzer.diagnostics,
            'generationContract': None, 'authority': 'source-structure-only; no execution path, tensor ports, shapes, or source-generation authority'}
    encoded = _canonical(core)
    if len(encoded.encode('utf-8')) > MAX_DEFINITION_BYTES - 1024:
        raise AdapterError('Adapter source evidence exceeds the 2 MB definition budget; choose a smaller local symbol.')
    identity = 'adapter-' + _sha(encoded)[:24]
    return {**core, 'id': identity, 'presentation': {'labels': {}, 'notes': []}}



@lru_cache(maxsize=8)
def _cached_scaffold(encoded_files, entry, method, encoded_config):
    return _scaffold_adapter_files(json.loads(encoded_files), entry, method, json.loads(encoded_config))


def scaffold_adapter_files(files, entry, method=None, config=None, rules=None):
    if rules is not None:
        return copy.deepcopy(_cached_rule_scaffold(_canonical(_checked_files(files)), entry, method,
                                                  _canonical({} if config is None else config), _canonical(rules)))
    files = _checked_files(files)
    config = {} if config is None else config
    # Cache is keyed by complete source bytes/config, and callers receive a
    # deep copy. A mutated template cannot poison later validation or reuse.
    return copy.deepcopy(_cached_scaffold(_canonical(files), entry, method, _canonical(config)))


def scaffold_adapter(root, entry, method=None, config=None, rules=None):
    return scaffold_adapter_files(_root_files(root), entry, method, config, rules)


@lru_cache(maxsize=8)
def _cached_rule_scaffold(encoded_files, entry, method, encoded_config, encoded_rules):
    from .source_rules import compile_rule_adapter_files
    return compile_rule_adapter_files(json.loads(encoded_files), entry, method=method,
                                     config=json.loads(encoded_config), rules=json.loads(encoded_rules))


def validate_adapter_files(payload, files):
    if not isinstance(payload, dict) or len(_canonical(payload).encode()) > MAX_DEFINITION_BYTES:
        raise AdapterError('Adapter definition must be a bounded JSON object.')
    if payload.get('schema') == 'archcanvas-source-adapter/2':
        from .source_rules import validate_rule_adapter_files
        return validate_rule_adapter_files(payload, files)
    if payload.get('generatorRevision') != 'source-inspection/3':
        raise AdapterError('Adapter is stale: source inspection rules changed; scaffold and review a new adapter.')
    binding = payload.get('binding')
    if not isinstance(binding, dict) or not all(key in binding for key in ('entry', 'method', 'sourceFiles')):
        raise AdapterError('Adapter lacks a source binding.')
    actual = [{'path': path, 'sha256': _sha(text)} for path, text in sorted(_checked_files(files).items())]
    if binding['sourceFiles'] != actual:
        raise AdapterError('Adapter is stale: source files or source hashes changed; scaffold and review a new adapter.')
    try:
        _graph_checked(payload['children'], payload['dependencies'])
        expected = scaffold_adapter_files(files, binding['entry'], binding['method'], payload.get('config'))
        presentation = _presentation(payload.get('presentation'), {node['id'] for node in expected['children']})
    except (KeyError, TypeError, RecursionError) as exc:
        raise AdapterError('Adapter facts, ports, containment or dependencies are invalid.') from exc
    submitted = {key: value for key, value in payload.items() if key != 'presentation'}
    canonical = {key: value for key, value in expected.items() if key != 'presentation'}
    if submitted != canonical:
        raise AdapterError('Adapter source evidence, facts, ports or generation contract were changed; regenerate from current source.')
    return {**expected, 'presentation': presentation}


def validate_adapter(payload, root):
    return validate_adapter_files(payload, _root_files(root))


class AdapterRegistry:
    """Project-local JSON store; no discovery or loading of executable plugins."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self._write_lock = threading.RLock()

    def _rule_records(self):
        from .source_rules import validate_rule
        directory = self.directory / 'rules'
        if directory.is_symlink() or directory.exists() and not directory.is_dir():
            raise AdapterError('Rule registry must be a real directory.')
        records = []
        for path in sorted(directory.glob('rule-*.json')):
            try:
                if path.is_symlink() or path.stat().st_size > MAX_DEFINITION_BYTES:
                    raise AdapterError('Rule record is a symlink or oversized.')
                definition = validate_rule(json.loads(path.read_text(encoding='utf-8')))
                if path.stem != definition['id']:
                    raise AdapterError('Rule registry filename and identity disagree.')
                records.append((path, definition, None))
            except (OSError, ValueError, TypeError, RecursionError) as exc:
                records.append((path, None, str(exc)))
        return records

    def rules(self):
        """List source-independent templates, including explicit invalid records."""
        return [{'id': path.stem, 'path': str(path.resolve()),
                 'status': 'invalid' if error else 'valid',
                 **({'message': error} if error else {'definition': definition})}
                for path, definition, error in self._rule_records()]

    def rule_definitions(self):
        return [definition for _, definition, error in self._rule_records() if not error]

    def _commit_records(self, records):
        """Stage every record, then roll back all ordinary commit failures.

        This is a local filesystem transaction, not a crash-recovery journal.
        The service supports one process per data directory. Existing file
        bytes and metadata are preserved in private backups until success.
        """
        with self._write_lock:
            if self.directory.is_symlink() or self.directory.exists() and not self.directory.is_dir():
                raise AdapterError('Adapter registry must be a real directory, not a symbolic link.')
            parents = {self.directory, *(target.parent for target, _ in records)}
            # Check every destination before creating or overwriting any
            # record. Directories, FIFOs and links are not registry records.
            for parent in parents:
                if parent.is_symlink() or parent.exists() and not parent.is_dir():
                    raise AdapterError('Adapter and rule registry paths must be real directories.')
            for target, _ in records:
                if target.is_symlink() or target.exists() and not target.is_file():
                    raise AdapterError('Adapter and rule records must be regular files, not symbolic links or directories.')
                if target.exists() and target.stat().st_size > MAX_DEFINITION_BYTES:
                    raise AdapterError('An existing registry record exceeds the record budget.')
            for parent in sorted(parents, key=lambda path: len(path.parts)):
                parent.mkdir(parents=True, exist_ok=True)
            staged, committed, temporary_paths, recovery_backups = [], [], [], set()
            try:
                for target, definition in records:
                    descriptor, temporary = tempfile.mkstemp(prefix='.registration-', suffix='.tmp', dir=target.parent)
                    temporary = Path(temporary); temporary_paths.append(temporary)
                    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                        output.write(json.dumps(definition, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n')
                    backup = None
                    if target.exists():
                        descriptor, backup_name = tempfile.mkstemp(prefix='.registration-backup-', suffix='.tmp', dir=target.parent)
                        os.close(descriptor)
                        backup = Path(backup_name); temporary_paths.append(backup)
                        shutil.copy2(target, backup, follow_symlinks=False)
                    staged.append((target, temporary, backup))
                for target, temporary, backup in staged:
                    os.replace(temporary, target)
                    committed.append((target, backup))
            except Exception as exc:
                rollback_errors = []
                for target, backup in reversed(committed):
                    try:
                        if backup is None:
                            target.unlink(missing_ok=True)
                        else:
                            os.replace(backup, target)
                    except OSError as rollback_exc:
                        if backup is not None:
                            recovery_backups.add(backup)
                        rollback_errors.append(str(rollback_exc) + (f'; recovery backup: {backup}' if backup else ''))
                if rollback_errors:
                    raise AdapterError('Registration failed; filesystem errors also prevented complete rollback: ' + '; '.join(rollback_errors)) from exc
                raise AdapterError(f'Registration failed; all record changes were rolled back: {exc}') from exc
            finally:
                for temporary in temporary_paths:
                    if temporary not in recovery_backups:
                        try:
                            temporary.unlink(missing_ok=True)
                        except OSError:
                            # A private staging file is not a registry record;
                            # cleanup must not misreport a successful commit as
                            # a failed registration or hide the original error.
                            pass

    def _save_rules(self, definitions):
        checked = merge_rules(definitions)
        records = [(self.directory / 'rules' / (rule['id'] + '.json'), rule) for rule in checked]
        self._commit_records(records)
        return [{'id': rule['id'], 'path': str(target.resolve())} for target, rule in records]

    def _records(self):
        if not self.directory.exists():
            return []
        if not self.directory.is_dir():
            raise AdapterError('Adapter registry path is not a directory.')
        records = []
        for path in sorted(self.directory.glob('adapter-*.json')):
            try:
                if path.is_symlink() or path.stat().st_size > MAX_DEFINITION_BYTES:
                    raise AdapterError('Registry record is a symlink or oversized.')
                payload = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(payload, dict) or not _ID.fullmatch(payload.get('id', '')) or path.stem != payload['id']:
                    raise AdapterError('Registry filename and adapter identity disagree.')
                binding = payload.get('binding')
                if not isinstance(binding, dict) or not isinstance(binding.get('entry'), str) or not isinstance(binding.get('method'), str):
                    raise AdapterError('Registry record lacks a valid entry/method source binding.')
                records.append((path, payload, None))
            except (OSError, ValueError, TypeError, RecursionError) as exc:
                records.append((path, None, str(exc)))
        return records

    def register_files(self, payload, files):
        definition = validate_adapter_files(payload, files)
        if definition.get('schema') == 'archcanvas-source-adapter/2' and not definition.get('applications'):
            raise AdapterError('A new rule must have at least one independently verified source match before registration.')
        target = self.directory / (definition['id'] + '.json')
        templates = merge_rules(definition['rules']) if definition.get('schema') == 'archcanvas-source-adapter/2' else []
        rule_records = [(self.directory / 'rules' / (rule['id'] + '.json'), rule) for rule in templates]
        # Commit templates and their checked instance as one ordinary-failure
        # transaction, rather than exposing a saved instance after rule failure.
        self._commit_records([*rule_records, (target, definition)])
        rules = [{'id': rule['id'], 'path': str(path.resolve())} for path, rule in rule_records]
        return {'id': definition['id'], 'path': str(target.resolve()), 'status': 'registered', 'definition': definition,
                **({'rules': rules} if rules else {})}

    def register(self, payload, root):
        return self.register_files(payload, _root_files(root))

    def list_files(self, files=None):
        if files is not None:
            files = _checked_files(files)
        result = []
        for path, payload, error in self._records():
            item = {'id': path.stem, 'path': str(path.resolve()), 'status': 'invalid' if error else 'unchecked'}
            if payload:
                item.update({'entry': payload.get('binding', {}).get('entry'), 'method': payload.get('binding', {}).get('method')})
                if files is not None:
                    try:
                        validate_adapter_files(payload, files)
                    except AdapterError as exc:
                        error = str(exc)
                        item['status'] = 'stale' if 'stale:' in error else 'invalid'
                    else:
                        item['status'] = 'valid'
            if error:
                item['message'] = error
            result.append(item)
        return result

    def list(self, root=None):
        return self.list_files(_root_files(root) if root is not None else None)

    def matching_files(self, files):
        files = _checked_files(files)
        result = []
        for _, payload, error in self._records():
            if not error:
                try:
                    result.append(validate_adapter_files(payload, files))
                except AdapterError:
                    pass
        return result

    def preview(self, bundle, files):
        """Rebind saved templates to this corpus; never reuse stale instance facts."""
        files = _checked_files(files)
        exact = self.matching_files(files)
        rules = self.rule_definitions()
        if rules:
            corpus = _corpus(files)
            entries = {bundle['entry']}
            for boundary in bundle['ir']['nodes']:
                if boundary.get('kind') == 'opaque' or boundary.get('sourceStructure'):
                    entries.update(_local_call_entries(boundary, bundle, corpus))
                    entries.update(_local_owner_entries(boundary, bundle, corpus))
            if len(entries) > 16:
                bundle = copy.deepcopy(bundle)
                bundle.setdefault('ruleDiagnostics', []).append({'message': 'Rule rebinding reached the 16-local-entry budget; use an explicit scaffold for additional local definitions.', 'truncated': True})
            seen = {definition['id'] for definition in exact}
            ordered_entries = [bundle['entry'], *sorted(entries - {bundle['entry']})]
            for entry in ordered_entries[:16]:
                try:
                    _, _, function, method, unit, _ = _entry(corpus, entry, None)
                    method_span = {**_source(unit, function), 'sha256': _sha(unit.expression(function))}
                except AdapterError:
                    method, method_span = None, None
                # An exact source record may target another configuration or
                # an explicitly selected helper. Neither has facts bound to
                # this preview's default entry, so its template must rebind.
                bound_rules = {rule['id'] for definition in exact
                               if definition['binding']['entry'] == entry
                               and definition['config'] == bundle.get('config', {})
                               and definition['binding']['method'] == method
                               and definition['binding']['methodSpan'] == method_span
                               for rule in definition.get('rules', [])}
                for rule in rules:
                    if rule['id'] in bound_rules:
                        continue
                    try:
                        definition = scaffold_adapter_files(files, entry, config=bundle.get('config', {}), rules=[rule])
                    except AdapterError as exc:
                        # Failure in one template must not suppress other
                        # verified templates or the original inspection tree.
                        bundle = copy.deepcopy(bundle)
                        bundle.setdefault('ruleDiagnostics', []).append({'entry': entry, 'ruleId': rule['id'], 'message': str(exc)})
                        continue
                    if definition['children'] and definition['id'] not in seen:
                        exact.append(definition); seen.add(definition['id'])
        result = apply_preview_adapters(bundle, files, exact)
        if rules:
            result['availableSourceRules'] = [rule['id'] for rule in rules]
        return result

    def resolve_files(self, files, entry, method=None, config=None):
        files = _checked_files(files)
        matches = []
        errors = []
        for _, payload, error in self._records():
            if error or payload.get('binding', {}).get('entry') != entry:
                continue
            if method is not None and payload['binding']['method'] != method or payload.get('config') != (config or {}):
                continue
            try:
                matches.append(validate_adapter_files(payload, files))
            except AdapterError as exc:
                errors.append(str(exc))
        if len(matches) != 1:
            raise AdapterError(errors[0] if errors else 'No unique registered adapter matches this source, entry, method and config.')
        return matches[0]

    def resolve(self, root, entry, method=None, config=None):
        return self.resolve_files(_root_files(root), entry, method, config)


def _preview_evidence(source):
    return {'file': source['path'], 'line': source['line'], 'endLine': source['endLine'],
            'column': source['column'], 'endColumn': source['endColumn'], 'expression': source['expression']}


def _selected_children(adapter, boundary, bundle, whole=False):
    children = adapter['children']
    by_id = {node['id']: node for node in children}
    evidence = [bundle['evidence'][key] for key in boundary.get('source_evidence', []) if key in bundle['evidence']]
    root_match = boundary.get('parent') is None and adapter['binding']['entry'] == bundle.get('entry')
    def overlaps(source, item):
        return source['path'] == item['file'] and source['line'] <= item['endLine'] and source['endLine'] >= item['line']
    selected = {node['id'] for node in children
                if whole or root_match or any(overlaps(source, item) for source in
                    [node['source'], *node.get('parameters', {}).get('callSites', [])] for item in evidence)}
    # Def/use spans also locate callers whose card lives in a constructor or a
    # different local file. These remain syntax dependencies, never tensor flow.
    for relation in adapter['dependencies']:
        if any(overlaps(relation['source'], item) for item in evidence):
            selected.update((relation['sourceId'], relation['targetId']))
    if not selected:
        return []
    for identity in list(selected):
        parent = by_id[identity].get('parentId')
        while parent is not None:
            selected.add(parent)
            parent = by_id[parent].get('parentId')
    # Include complete definition descendants, even when their authored source
    # lives in a different local file. No runtime instance count is inferred.
    for _ in range(12):
        before = len(selected)
        selected.update(node['id'] for node in children if node.get('parentId') in selected)
        if before == len(selected):
            break
    # Spend a bounded view budget on shallow siblings before deeply inspecting
    # the first one. The original order remains deterministic within a level.
    siblings = {}
    for node in children:
        if node['id'] in selected:
            siblings.setdefault(node.get('parentId'), []).append(node)
    pending = deque(siblings.get(None, []))
    ordered = []
    while pending:
        node = pending.popleft()
        ordered.append(node)
        pending.extend(siblings.get(node['id'], []))
    return ordered


def _inspection_allowances(demands, budget):
    """Distribute a bounded card budget fairly, returning unused small shares.

    A small region receives only the cards it actually needs. Its remaining
    share can inspect a larger sibling instead of causing avoidable truncation.
    Equal shares and their final remainder follow the authored boundary order.
    """
    allowances = [0] * len(demands)
    ordered = sorted(range(len(demands)), key=lambda index: (demands[index], index))
    for offset, index in enumerate(ordered):
        active = ordered[offset:]
        share, extra = divmod(budget, len(active))
        if demands[index] <= share:
            allowances[index] = demands[index]
            budget -= demands[index]
        else:
            for position, remaining in enumerate(sorted(active)):
                allowances[remaining] = share + (position < extra)
            break
    return allowances


def apply_preview_adapters(bundle, files, adapters, *, automatic=False):
    """Append inspection-only subtrees while preserving every original binding."""
    files = _checked_files(files)
    manifest = bundle.get('files', [])
    if {item.get('path'): item.get('text') for item in manifest} != files or any(item.get('sha256') != _sha(item.get('text', '')) for item in manifest):
        raise AdapterError('Preview bundle source does not match adapter source; reanalyze the original files.')
    definitions = [validate_adapter_files(payload, files) for payload in adapters]
    rule_definitions = [definition for definition in definitions if definition['schema'] == 'archcanvas-source-adapter/2']
    definitions = [definition for definition in definitions if definition['schema'] == SCHEMA]
    corpus = _corpus(files) if any(adapter['binding']['entry'] != bundle.get('entry') for adapter in definitions) else None
    result = copy.deepcopy(bundle)
    ir = result['ir']
    definitions.sort(key=lambda adapter: adapter['binding']['entry'] == result.get('entry'))
    added, applied = 0, []
    boundaries = list(ir['nodes'])
    plans = {}
    by_original = {node['id']: node for node in ir['nodes']}
    # Select actual source facts first. Counting every opaque call as an equal
    # demand wastes most of the view budget when later calls have tiny trees.
    for boundary in boundaries:
        inspection = boundary.get('sourceInspection')
        if boundary.get('kind') != 'opaque' or inspection and automatic:
            continue
        for adapter in definitions:
            if adapter['config'] != result.get('config', {}):
                continue
            if inspection and inspection.get('origin') == 'registered' and inspection.get('adapterId') == adapter['id'] and inspection.get('presentationSha256') == _sha(_canonical(adapter['presentation'])):
                break
            whole = adapter['binding']['entry'] in _local_call_entries(boundary, result, corpus) if corpus else False
            owned = adapter['binding']['entry'] in _local_owner_entries(boundary, result, corpus) if corpus else False
            if adapter['binding']['entry'] != result.get('entry') and not whole and not owned:
                continue
            facts = _selected_children(adapter, boundary, result, whole)
            if not facts:
                continue
            parent_depth, cursor = 0, boundary
            while cursor.get('parent'):
                parent_depth += 1; cursor = by_original[cursor['parent']]
            depths = {}
            for fact in facts:
                depths[fact['id']] = depths.get(fact.get('parentId'), 0) + 1
            demand = sum(parent_depth + depth <= 12 for depth in depths.values())
            if not demand:
                continue
            removed = {node['id'] for node in ir['nodes'] if inspection
                       and node['id'].startswith(boundary['id'] + '/adapter-') and node.get('sourceStructure')}
            plans[boundary['id']] = {'adapter': adapter, 'facts': facts, 'demand': demand,
                                     'removed': removed, 'parentDepth': parent_depth}
            break
    removed = set().union(*(plan['removed'] for plan in plans.values())) if plans else set()
    budget = max(0, MAX_NODES - len(ir['nodes']) + len(removed))
    # An existing inspection being refreshed must retain at least one card;
    # otherwise its freed cards could fund new regions while hiding that tree.
    minimums = [int(bool(plan['removed'])) for plan in plans.values()]
    allowances = _inspection_allowances([plan['demand'] - minimum for plan, minimum in zip(plans.values(), minimums)],
                                        budget - sum(minimums))
    for plan, allowance, minimum in zip(plans.values(), allowances, minimums):
        plan['allowance'] = allowance + minimum
    if removed:
        ir['nodes'] = [node for node in ir['nodes'] if node['id'] not in removed]
        ir['edges'] = [edge for edge in ir['edges'] if edge['source'] not in removed and edge['target'] not in removed]
        result['sourceAdapters'] = [record for record in result.get('sourceAdapters', [])
                                    if record['boundary'] not in plans]
    remaining = MAX_NODES - len(ir['nodes'])
    for boundary in boundaries:
        plan = plans.get(boundary['id'])
        if not plan or not plan['allowance']:
            continue
        adapter, facts = plan['adapter'], plan['facts']
        parent_depth = plan['parentDepth']
        mapping, pending = {}, list(facts)
        omitted = 0
        allowance = plan['allowance']
        while pending and remaining > 0 and len(mapping) < allowance:
            progressed = False
            for fact in list(pending):
                parent = fact.get('parentId')
                if parent is not None and parent not in mapping:
                    continue
                depth = 1
                ancestor = parent
                while ancestor is not None:
                    depth += 1
                    ancestor = next((node.get('parentId') for node in facts if node['id'] == ancestor), None)
                pending.remove(fact); progressed = True
                if parent_depth + depth > 12:
                    omitted += 1
                    continue
                identity = boundary['id'] + '/adapter-' + _sha(adapter['id'] + fact['id'])[:16]
                source = _preview_evidence(fact['source'])
                evidence_id = 'e-' + _sha(_canonical(source))[:16]
                result['evidence'][evidence_id] = source
                label = adapter['presentation']['labels'].get(fact['id'], fact['label'])
                source_type = fact.get('parameters', {}).get('sourceType')
                if source_type and fact['id'] not in adapter['presentation']['labels'] and source_type != fact['label']:
                    label = label + ' · ' + source_type
                node = {'id': identity, 'parent': mapping.get(parent, boundary['id']), 'kind': 'source_structure',
                        'label': label, 'sourceParameters': copy.deepcopy(fact.get('parameters', {})),
                        'source_evidence': [evidence_id], 'expression': source['expression'],
                        'certainty': 'syntax', 'sourceStructure': True, 'sourceKind': fact['kind'],
                        'sourceAdapterId': adapter['id'], 'generationContract': None}
                ir['nodes'].append(node); mapping[fact['id']] = identity
                remaining -= 1; added += 1
                if remaining <= 0 or len(mapping) >= allowance:
                    break
            if not progressed:
                break
        for node in ir['nodes']:
            if node['id'] not in mapping.values():
                continue
            parameters = node.get('sourceParameters', {})
            reference = parameters.get('definitionReference')
            if reference:
                parameters['definitionReferenceSourceId'] = reference
                if reference in mapping:
                    parameters['definitionReference'] = mapping[reference]
                    node['sourceDefinitionReference'] = mapping[reference]
                else:
                    parameters['definitionReferenceVisible'] = False
        for relation in adapter['dependencies']:
            if relation['sourceId'] not in mapping or relation['targetId'] not in mapping or len(ir['edges']) >= 3600:
                continue
            source = _preview_evidence(relation['source'])
            evidence_id = 'e-' + _sha(_canonical(source))[:16]
            result['evidence'][evidence_id] = source
            producer, consumer = mapping[relation['sourceId']], mapping[relation['targetId']]
            ir['edges'].append({'id': 'adapter-edge-' + _sha(boundary['id'] + relation['id'])[:20],
                                'source': producer, 'target': consumer, 'sourcePort': 'out', 'targetPort': 'source-dependency',
                                'wire': producer + ':out', 'role': 'source_dependency', 'source_evidence': [evidence_id],
                                'syntaxOnly': True, 'sourceAdapterId': adapter['id']})
        if mapping:
            truncated = bool(pending or omitted or any('budget' in item.get('message', '') for item in adapter['diagnostics']))
            applied.append({'boundary': boundary['id'], 'adapter': adapter['id'], 'nodes': len(mapping), 'truncated': truncated})
            boundary['sourceInspection'] = {'adapterId': adapter['id'], 'authority': 'source-structure-only', 'truncated': truncated,
                                            'origin': 'automatic' if automatic else 'registered', 'presentationSha256': _sha(_canonical(adapter['presentation']))}
    if added:
        result['diagnostics'].append({'node': ir['nodes'][0]['id'], 'evidence': ir['nodes'][0]['source_evidence'][0],
                                      'message': f'Added {added} source inspection cards. Source arrows describe authored dependencies; execution paths, tensor ports and generation authority remain unresolved.'})
        result['sourceAdapters'] = result.get('sourceAdapters', []) + applied
        result['canonicalIR'] = _canonical(ir)
        result['irSha256'] = _sha(result['canonicalIR'])
        result['id'] = 'source-' + _sha(result['entry'] + result['sourceSha256'] + result['canonicalIR'])[:16]
    if rule_definitions:
        from .rule_preview import apply_rule_adapters
        result = apply_rule_adapters(result, files, rule_definitions)
    return _adaptation_coverage(result, files)


def _local_call_entries(boundary, bundle, corpus):
    if corpus is None:
        return set()
    result = set()
    for key in boundary.get('source_evidence', []):
        evidence = bundle.get('evidence', {}).get(key, {})
        unit = next((unit for unit in corpus.units.values() if unit.path == evidence.get('file')), None)
        if unit is None:
            continue
        for call in ast.walk(unit.tree):
            if not isinstance(call, ast.Call) or call.lineno != evidence.get('line') or call.col_offset != evidence.get('column'):
                continue
            if ast.get_source_segment(unit.content, call) != evidence.get('expression'):
                continue
            qualified = unit.resolve(call.func)
            module, _, name = qualified.rpartition('.')
            own = corpus.units.get(module)
            if own and (name in own.classes or name in own.functions):
                result.add(module + ':' + name)
    return result



def _local_owner_entries(boundary, bundle, corpus):
    """Recover the actual callee method owning an opaque source region."""
    if corpus is None:
        return set()
    result = set()
    for key in boundary.get('source_evidence', []):
        evidence = bundle.get('evidence', {}).get(key, {})
        unit = next((unit for unit in corpus.units.values() if unit.path == evidence.get('file')), None)
        if unit is None:
            continue
        line, end_line = evidence.get('line', -1), evidence.get('endLine', -1)
        for symbol in unit.tree.body:
            if isinstance(symbol, ast.ClassDef):
                methods = [node for node in symbol.body if isinstance(node, ast.FunctionDef)]
                if any(node.lineno <= line <= end_line <= node.end_lineno for node in methods):
                    result.add(unit.module + ':' + symbol.name)
            elif isinstance(symbol, ast.FunctionDef) and symbol.lineno <= line <= end_line <= symbol.end_lineno:
                result.add(unit.module + ':' + symbol.name)
    return result


def automatic_preview_adapters(bundle, files):
    """Inspect available local method/helper syntax without registration."""
    corpus = _corpus(_checked_files(files))
    entries = {bundle['entry']}
    for boundary in bundle['ir']['nodes']:
        if boundary.get('kind') == 'opaque' and not boundary.get('sourceInspection'):
            entries.update(_local_call_entries(boundary, bundle, corpus))
            entries.update(_local_owner_entries(boundary, bundle, corpus))
    adapters = []
    for entry in sorted(entries)[:16]:
        try:
            adapters.append(scaffold_adapter_files(files, entry, config=bundle.get('config', {})))
        except AdapterError:
            continue
    return apply_preview_adapters(bundle, files, adapters, automatic=True) if adapters else copy.deepcopy(bundle)


def _adaptation_coverage(bundle, files):
    corpus = _corpus(files)
    requests = []
    for node in bundle['ir']['nodes']:
        if node.get('kind') != 'opaque':
            continue
        candidates = sorted(_local_call_entries(node, bundle, corpus) | _local_owner_entries(node, bundle, corpus))
        if not candidates:
            candidates = [bundle['entry']]
        inspection = node.get('sourceInspection')
        requests.append({'nodeId': node['id'], 'sourceEvidence': list(node.get('source_evidence', [])),
                         'sourceSymbols': candidates,
                         'status': 'source-inspected' if inspection else 'needs-source-adapter',
                         'generationContract': 'unresolved',
                         'truncated': bool(inspection and inspection.get('truncated')),
                         'next': {'command': 'adapter scaffold', 'entry': candidates[0],
                                  'workflow': ['scaffold', 'review-source-evidence', 'validate', 'register', 'preview'],
                                  'format': SCHEMA,
                                  'ruleFormat': 'archcanvas-source-rule/1',
                                  'ruleWorkflow': ['read-source', 'author-rule', 'rule-validate', 'scaffold --rules', 'validate', 'register', 'preview'],
                                  'ruleApplications': [application for application in bundle.get('sourceRuleApplications', [])
                                                       if application['boundary'] == node['id']]}})
    bundle['adaptationRequests'] = requests
    bundle['coverage'] = {'scope': 'static-source-and-source-inspection',
                          'opaqueBoundaries': len(requests),
                          'inspectedOpaqueBoundaries': sum(item['status'] == 'source-inspected' for item in requests),
                          'truncatedInspections': sum(item['truncated'] for item in requests),
                          'tensorExecutionVerified': False, 'modelExecuted': False,
                          'agentAuthoredSourceRules': True,
                          'sourceRuleApplications': len(bundle.get('sourceRuleApplications', [])),
                          'generationAuthority': 'Adapters do not authorize structural generation; use independently checked source-preserving generation when eligible.'}
    return bundle


def enrich_preview(bundle, files, adapters=()):
    explicit = list(adapters)
    if explicit:
        bundle = apply_preview_adapters(bundle, files, explicit)
    # Registered presentation takes priority; avoid adding a second tree.
    if any(node.get('kind') == 'opaque' and not node.get('sourceInspection') for node in bundle['ir']['nodes']):
        bundle = automatic_preview_adapters(bundle, files)
    return _adaptation_coverage(bundle, _checked_files(files))
