"""A bounded AST view-rule interpreter, independent of SourceStructure.

Rules are JSON patterns and selectors, never Python hooks. Their selected source
facts and narrowly proven syntax relations add inspection structure only. They
cannot replace conservative tensor boundaries or grant generation authority.
"""
from __future__ import annotations

import ast
import copy
import re

from .registry import (
    AdapterError, _canonical, _sha, _checked_files, _corpus, _entry, _source,
    _interfaces, _graph_checked, _presentation, MAX_DEFINITION_BYTES,
)

RULE_SCHEMA = 'archcanvas-source-rule/1'
ADAPTER_SCHEMA = 'archcanvas-source-adapter/2'
GENERATOR_REVISION = 'source-rules/1'
AUTHORITY = 'source-structure-only; no execution path, tensor ports, shapes, or source-generation authority'
MAX_RULE_BYTES = 64_000
MAX_RULES = 16
MAX_RULE_NODES = 64
MAX_RULE_RELATIONS = 128
MAX_PATTERN_DEPTH = 12
MAX_PATTERN_ITEMS = 512
MAX_PATH_DEPTH = 16
MAX_AST_NODES = 100_000
MAX_MATCHES = 480
MAX_CHILDREN = 480
MAX_RELATIONS = 1440
_KEY = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
_RULE_ID = re.compile(r'rule-[a-f0-9]{24}\Z')
_KINDS = frozenset({'SourceExpression', 'SourceCall', 'SourceLoop', 'SourceBranch', 'SourceStatement'})
_PROOFS = frozenset({'expression-input', 'comprehension-iteration'})
_AST_TYPES = {name: value for name, value in vars(ast).items()
              if isinstance(value, type) and issubclass(value, ast.AST)}


def _object(value, required, optional=(), what='Rule object'):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise AdapterError(f'{what} contains missing or unsupported fields.')


def _text(value, maximum, what):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or any(ord(char) < 32 for char in value):
        raise AdapterError(f'{what} must be bounded plain text.')
    return value


def _pattern(value, depth=0, budget=None, *, root=False):
    if budget is None:
        budget = [MAX_PATTERN_ITEMS]
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_PATTERN_DEPTH:
        raise AdapterError('AST pattern exceeds its depth or item budget.')
    if isinstance(value, dict):
        _object(value, ('type',), ('fields',), 'AST pattern')
        name = value['type']
        if not isinstance(name, str) or name not in _AST_TYPES or name == 'AST':
            raise AdapterError('AST pattern type must name a built-in concrete AST class.')
        cls = _AST_TYPES[name]
        if root and 'lineno' not in cls._attributes:
            raise AdapterError('A match pattern must select a locatable AST node.')
        fields = value.get('fields', {})
        if not isinstance(fields, dict) or set(fields) - set(cls._fields):
            raise AdapterError('AST pattern fields must be actual fields of its AST type.')
        return {'type': name, 'fields': {key: _pattern(item, depth + 1, budget) for key, item in sorted(fields.items())}}
    if isinstance(value, list):
        return [_pattern(item, depth + 1, budget) for item in value]
    if value is None or type(value) in (str, bool, int, float):
        # _canonical rejects NaN/infinity and other non-JSON values globally.
        return value
    raise AdapterError('AST pattern values must be AST patterns or JSON literals/lists.')


def validate_rule(payload):
    """Validate and canonicalize one portable template, adding its content ID."""
    if not isinstance(payload, dict) or len(_canonical(payload).encode('utf-8')) > MAX_RULE_BYTES:
        raise AdapterError('Source rule must be a JSON object of at most 64 KB.')
    _object(payload, ('schema', 'name', 'match', 'nodes', 'relations'), ('id',), 'Source rule')
    if payload['schema'] != RULE_SCHEMA:
        raise AdapterError('Unsupported source rule schema.')
    name = _text(payload['name'], 120, 'Rule name')
    if not isinstance(payload['match'], dict):
        raise AdapterError('Rule match must be an AST pattern.')
    match = _pattern(payload['match'], root=True)
    raw_nodes = payload['nodes']
    if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= MAX_RULE_NODES:
        raise AdapterError('A source rule needs 1–64 selected nodes.')
    nodes = []
    for raw in raw_nodes:
        _object(raw, ('key', 'at', 'parent', 'kind'), ('label',), 'Rule node')
        key, path, parent = raw['key'], raw['at'], raw['parent']
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise AdapterError('Rule node keys must be short identifiers.')
        if not isinstance(path, list) or len(path) > MAX_PATH_DEPTH or any(
                not (isinstance(item, str) and item.isidentifier() and not item.startswith('_')
                     or type(item) is int and item >= 0) for item in path):
            raise AdapterError('Rule selectors need at most 16 AST fields or nonnegative list indices.')
        if parent is not None and (not isinstance(parent, str) or not _KEY.fullmatch(parent)):
            raise AdapterError('Rule parent must be another node key or null.')
        if not isinstance(raw['kind'], str) or raw['kind'] not in _KINDS:
            raise AdapterError('Rule node kind is not a supported source inspection kind.')
        node = {'key': key, 'at': list(path), 'parent': parent, 'kind': raw['kind']}
        if 'label' in raw:
            node['label'] = _text(raw['label'], 120, 'Rule node label')
        nodes.append(node)
    by_key = {node['key']: node for node in nodes}
    if len(by_key) != len(nodes) or len({tuple(node['at']) for node in nodes}) != len(nodes):
        raise AdapterError('Rule node keys and AST selector paths must be unique.')
    roots = [node for node in nodes if node['parent'] is None]
    if len(roots) != 1 or roots[0]['at'] != [] or any(node['at'] == [] and node is not roots[0] for node in nodes):
        raise AdapterError('Each match requires exactly one at=[] node with parent=null.')
    for node in nodes:
        seen, cursor = set(), node
        while cursor['parent'] is not None:
            if cursor['key'] in seen or cursor['parent'] not in by_key:
                raise AdapterError('Rule containment is cyclic or refers to an unknown node key.')
            seen.add(cursor['key'])
            parent = by_key[cursor['parent']]
            if not (len(parent['at']) < len(cursor['at']) and cursor['at'][:len(parent['at'])] == parent['at']):
                raise AdapterError('A rule parent selector must contain its child selector.')
            cursor = parent
    raw_relations = payload['relations']
    if not isinstance(raw_relations, list) or len(raw_relations) > MAX_RULE_RELATIONS:
        raise AdapterError('A source rule accepts at most 128 syntax relations.')
    relations = []
    seen = set()
    for raw in raw_relations:
        _object(raw, ('source', 'target', 'proof'), what='Rule relation')
        if not isinstance(raw['source'], str) or not isinstance(raw['target'], str) or raw['source'] not in by_key or raw['target'] not in by_key or raw['source'] == raw['target']:
            raise AdapterError('Rule relations require distinct selected node keys.')
        if not isinstance(raw['proof'], str) or raw['proof'] not in _PROOFS:
            raise AdapterError('Rule relation proof is not supported.')
        fingerprint = (raw['source'], raw['target'], raw['proof'])
        if fingerprint in seen:
            raise AdapterError('Rule relations must be unique.')
        seen.add(fingerprint)
        relations.append(dict(raw))
    core = {'schema': RULE_SCHEMA, 'name': name, 'match': match, 'nodes': nodes, 'relations': relations}
    identity = 'rule-' + _sha(_canonical(core))[:24]
    if 'id' in payload and (not isinstance(payload['id'], str) or not _RULE_ID.fullmatch(payload['id']) or payload['id'] != identity):
        raise AdapterError('Source rule ID disagrees with its canonical contents.')
    return {**core, 'id': identity}


def _matches(node, pattern):
    if isinstance(pattern, dict):
        return isinstance(node, ast.AST) and type(node).__name__ == pattern['type'] and all(
            _matches(getattr(node, field), value) for field, value in pattern['fields'].items())
    if isinstance(pattern, list):
        return isinstance(node, list) and len(node) == len(pattern) and all(_matches(item, expected) for item, expected in zip(node, pattern))
    return type(node) is type(pattern) and node == pattern


def _select(match, path):
    cursor = match
    for component in path:
        if isinstance(component, str):
            if not isinstance(cursor, ast.AST) or component not in cursor._fields:
                raise AdapterError('A rule AST selector does not resolve to a field in this match.')
            cursor = getattr(cursor, component)
        else:
            if not isinstance(cursor, list) or component >= len(cursor):
                raise AdapterError('A rule AST selector has an unavailable list index.')
            cursor = cursor[component]
    if not isinstance(cursor, ast.AST) or not all(isinstance(getattr(cursor, key, None), int)
                                                for key in ('lineno', 'end_lineno', 'col_offset', 'end_col_offset')):
        raise AdapterError('A rule AST selector must resolve to a locatable source AST node.')
    return cursor


def _read(node):
    return isinstance(node, ast.expr) and not isinstance(getattr(node, 'ctx', None), (ast.Store, ast.Del))


def _direct_inputs(node):
    """A closed list of immediate value operands, not statement-order flow."""
    if isinstance(node, ast.Call):
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        # A computed callable is itself evaluated. A bare function name is a
        # symbol reference, not an inferred tensor producer.
        if isinstance(node.func, (ast.Call, ast.Subscript, ast.Attribute)):
            values.append(node.func)
        return values
    if isinstance(node, ast.BinOp):
        return [node.left, node.right]
    if isinstance(node, ast.UnaryOp):
        return [node.operand]
    if isinstance(node, ast.BoolOp):
        return list(node.values)
    if isinstance(node, ast.Compare):
        return [node.left, *node.comparators]
    if isinstance(node, ast.Attribute) and _read(node):
        return [node.value]
    if isinstance(node, ast.Subscript) and _read(node):
        return [node.value, node.slice]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and _read(node):
        return list(node.elts)
    if isinstance(node, ast.Dict):
        return [*(key for key in node.keys if key is not None), *node.values]
    if isinstance(node, (ast.Expr, ast.Return, ast.Assign, ast.AnnAssign)):
        return [node.value] if node.value is not None else []
    if isinstance(node, ast.Starred) and _read(node):
        return [node.value]
    if isinstance(node, ast.FormattedValue):
        return [node.value, *([node.format_spec] if node.format_spec else [])]
    if isinstance(node, ast.JoinedStr):
        return list(node.values)
    # Conditional expressions, control-flow statements, stores, augmented
    # updates and comprehensions need separate evidence. They are not ordinary
    # direct-input edges, even if they happen to contain the producer AST.
    return []


def _bound_names(target):
    if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_bound_names(item) for item in target.elts)) if target.elts else set()
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    raise AdapterError('Comprehension iteration proof requires ordinary local binding targets.')


def _free_loads(node, masked=frozenset()):
    """Respect lexical shadowing in lambdas and nested comprehensions."""
    if isinstance(node, ast.Name):
        return {node.id} if isinstance(node.ctx, ast.Load) and node.id not in masked else set()
    if isinstance(node, ast.NamedExpr):
        raise AdapterError('Named-expression state changes cannot prove a comprehension iteration relation.')
    if isinstance(node, ast.Lambda):
        arguments = node.args
        names = {item.arg for item in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]}
        names.update(item.arg for item in (arguments.vararg, arguments.kwarg) if item)
        defaults = set().union(*(_free_loads(value, masked) for value in [*arguments.defaults, *arguments.kw_defaults] if value is not None))
        return defaults | _free_loads(node.body, masked | names)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        result, local = set(), set(masked)
        for generator in node.generators:
            result.update(_free_loads(generator.iter, frozenset(local)))
            local.update(_bound_names(generator.target))
            for condition in generator.ifs:
                result.update(_free_loads(condition, frozenset(local)))
        outputs = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        for output in outputs:
            result.update(_free_loads(output, frozenset(local)))
        return result
    return set().union(*(_free_loads(child, masked) for child in ast.iter_child_nodes(node))) if isinstance(node, ast.AST) else set()


def _iteration_proof(match, producer, consumer):
    candidates = [node for node in ast.walk(match) if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))]
    for comp in candidates:
        outputs = [comp.key, comp.value] if isinstance(comp, ast.DictComp) else [comp.elt]
        if not any(consumer is output for output in outputs):
            continue
        for index, generator in enumerate(comp.generators):
            if producer is not generator.iter:
                continue
            bound = _bound_names(generator.target)
            later_bound = set().union(*(_bound_names(item.target) for item in comp.generators[index + 1:]))
            if bound & later_bound:
                raise AdapterError('Comprehension iteration proof crosses a later generator shadowing its binding.')
            if not bound & _free_loads(consumer):
                raise AdapterError('Comprehension output does not read this generator binding in its lexical scope.')
            return
    raise AdapterError('Comprehension iteration proof requires its actual iterable and an output reading that binding.')


def _prove(match, producer, consumer, proof):
    if not _read(producer):
        raise AdapterError('Source relation producers must be read expressions, never assignment stores.')
    if proof == 'expression-input':
        if not any(producer is operand for operand in _direct_inputs(consumer)):
            raise AdapterError('expression-input requires an immediate value operand; order or branch containment is insufficient.')
    else:
        _iteration_proof(match, producer, consumer)


def _walk_with_context(function):
    """Keep authored guards without choosing their runtime truth or count."""
    pending = [(function, ())]
    count = 0
    while pending:
        node, guards = pending.pop()
        count += 1
        if count > MAX_AST_NODES:
            raise AdapterError('Entry method exceeds the 100000-AST-node inspection budget.')
        yield node, guards
        children = []
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # Iterables evaluate in the preceding generator scope; bodies and
            # filters see only bindings already introduced. Do not assign all
            # filters to the iterable or merge guards from nested alternatives.
            local = list(guards)
            for generator in node.generators:
                children.append((generator.iter, tuple(local)))
                header = ('async for ' if generator.is_async else 'for ') + ast.unparse(generator.target) + ' in ' + ast.unparse(generator.iter)
                local.append(header)
                children.append((generator.target, tuple(local)))
                for condition in generator.ifs:
                    children.append((condition, tuple(local)))
                    local.append('if ' + ast.unparse(condition))
            outputs = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            children.extend((output, tuple(local)) for output in outputs)
            pending.extend(reversed(children))
            continue
        for field, value in ast.iter_fields(node):
            values = value if isinstance(value, list) else [value]
            extra = ()
            if isinstance(node, (ast.If, ast.IfExp)) and field in ('body', 'orelse'):
                predicate = ast.unparse(node.test)
                extra = (('if ' + predicate) if field == 'body' else ('else of (' + predicate + ')'),)
            elif isinstance(node, (ast.For, ast.AsyncFor)) and field in ('body', 'orelse'):
                header = ('async for ' if isinstance(node, ast.AsyncFor) else 'for ') + ast.unparse(node.target) + ' in ' + ast.unparse(node.iter)
                extra = ((header if field == 'body' else 'loop else of (' + header + ')'),)
            elif isinstance(node, ast.While) and field in ('body', 'orelse'):
                extra = (('while ' if field == 'body' else 'while else of ') + ast.unparse(node.test),)
            for position, child in enumerate(values):
                if isinstance(child, ast.AST):
                    conditional = ()
                    if isinstance(node, ast.BoolOp) and field == 'values' and position:
                        preceding = ', '.join(ast.unparse(item) for item in node.values[:position])
                        state = 'truthy' if isinstance(node.op, ast.And) else 'falsey'
                        conditional = (f'short-circuit {type(node.op).__name__}: preceding operands ({preceding}) {state}',)
                    elif isinstance(node, ast.Compare) and field == 'comparators' and position:
                        conditional = ('chained comparison: preceding comparisons true',)
                    children.append((child, (*guards, *extra, *conditional)))
        pending.extend(reversed(children))


def _guards(match, inherited):
    guards = list(inherited)
    if isinstance(match, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        for generator in match.generators:
            guards.append(('async for ' if generator.is_async else 'for ') + ast.unparse(generator.target) + ' in ' + ast.unparse(generator.iter))
            guards.extend('if ' + ast.unparse(condition) for condition in generator.ifs)
    return list(dict.fromkeys(guards))


def _label(node, root=False):
    if root:
        return type(node).__name__
    text = ast.unparse(node.func) if isinstance(node, ast.Call) else ast.unparse(node)
    text = ' '.join(text.split())
    return text[:117] + '...' if len(text) > 120 else text or type(node).__name__


def _compile_rule_adapter_files(files, entry, method=None, config=None, rules=()):
    """Instantiate templates against current AST text without old lowering."""
    files = _checked_files(files)
    config = {} if config is None else config
    if not isinstance(config, dict) or len(_canonical(config).encode('utf-8')) > 32_000:
        raise AdapterError('Adapter config must be a JSON object of at most 32 KB.')
    if not isinstance(rules, (list, tuple)) or len(rules) > MAX_RULES:
        raise AdapterError('A rule adapter accepts at most 16 source rule templates.')
    templates = sorted((validate_rule(rule) for rule in rules), key=lambda rule: rule['id'])
    if len({rule['id'] for rule in templates}) != len(templates):
        raise AdapterError('A rule adapter cannot contain duplicate templates.')
    corpus = _corpus(files)
    unit, symbol, function, method, method_unit, _ = _entry(corpus, entry, method)
    children, dependencies, applications = [], [], []
    contextual_nodes = list(_walk_with_context(function))
    contexts = {id(node): guards for node, guards in contextual_nodes}
    for occurrence, (match, inherited_guards) in enumerate(contextual_nodes):
        for rule in templates:
            if not _matches(match, rule['match']):
                continue
            if len(applications) >= MAX_MATCHES or len(children) + len(rule['nodes']) > MAX_CHILDREN or len(dependencies) + len(rule['relations']) > MAX_RELATIONS:
                raise AdapterError('Rule applications exceed the 480-match/480-child/1440-relation budget; narrow the pattern.')
            source = _source(method_unit, match)
            # Some Python AST nodes (notably f-string parts) share exactly the
            # same authored span. A deterministic AST occurrence distinguishes
            # them without assuming source spans uniquely identify objects.
            match_key = 'match-' + _sha(_canonical({'ruleId': rule['id'], 'source': source, 'astOccurrence': occurrence}))[:24]
            selected = {node['key']: _select(match, node['at']) for node in rule['nodes']}
            identities = {node['key']: 'source-rule:' + _sha(match_key + ':' + node['key'])[:24] for node in rule['nodes']}
            for node in rule['nodes']:
                own = selected[node['key']]
                parent = node['parent']
                if parent is not None and not any(own is candidate for candidate in ast.walk(selected[parent])):
                    raise AdapterError('Selected rule parent does not contain its child AST.')
                identity = identities[node['key']]
                guards = _guards(own, contexts.get(id(own), inherited_guards))
                parameters = {'sourceRuleId': rule['id'], 'sourceMatch': match_key,
                              'sourceRulePath': list(node['at']), 'guards': list(guards),
                              'inspectionAuthority': 'syntax only; runtime path and repetition unverified'}
                children.append({'id': identity, 'label': node.get('label', _label(own, root=parent is None)),
                                 'kind': node['kind'], 'category': 'operator' if node['kind'] in ('SourceCall', 'SourceExpression') else 'container',
                                 'parentId': identities[parent] if parent is not None else None,
                                 'children': [identities[item['key']] for item in rule['nodes'] if item['parent'] == node['key']],
                                 'ports': [], 'parameters': parameters, 'source': _source(method_unit, own),
                                 'evidence': 'source', 'sourceStructure': True})
            for relation in rule['relations']:
                producer, consumer = selected[relation['source']], selected[relation['target']]
                _prove(match, producer, consumer, relation['proof'])
                guards = _guards(consumer, contexts.get(id(consumer), inherited_guards))
                dependencies.append({'id': 'source-rule-relation:' + _sha(match_key + ':' + _canonical(relation))[:24],
                                     'sourceId': identities[relation['source']], 'targetId': identities[relation['target']],
                                     'kind': 'source-data-dependency', 'source': _source(method_unit, consumer),
                                     'proof': relation['proof'], 'sourceRuleId': rule['id'], 'sourceMatch': match_key,
                                     'syntaxOnly': True, 'guards': list(guards)})
            root = next(node for node in rule['nodes'] if node['parent'] is None)
            applications.append({'ruleId': rule['id'], 'matchKey': match_key, 'source': source,
                                 'rootId': identities[root['key']], 'nodeIds': [identities[node['key']] for node in rule['nodes']]})
    _graph_checked(children, dependencies)
    inputs, outputs = _interfaces(method_unit, symbol, function)
    binding = {'entry': entry, 'method': method,
               'sourceFiles': [{'path': path, 'sha256': _sha(text)} for path, text in sorted(files.items())],
               'symbol': {**_source(unit, symbol), 'qualifiedName': entry},
               'methodSpan': {**_source(method_unit, function), 'sha256': _sha(method_unit.expression(function))}}
    core = {'schema': ADAPTER_SCHEMA, 'generatorRevision': GENERATOR_REVISION, 'binding': binding,
            'config': copy.deepcopy(config), 'inputs': inputs, 'outputs': outputs,
            'rules': templates, 'applications': applications, 'children': children, 'dependencies': dependencies,
            'diagnostics': [], 'generationContract': None, 'authority': AUTHORITY}
    if len(_canonical(core).encode('utf-8')) > MAX_DEFINITION_BYTES - 1024:
        raise AdapterError('Rule adapter exceeds the 2 MB definition budget; narrow the selected source.')
    return {**core, 'id': 'adapter-' + _sha(_canonical(core))[:24], 'presentation': {'labels': {}, 'notes': []}}


def compile_rule_adapter_files(files, entry, method=None, config=None, rules=()):
    """Bound Python's own AST/unparse recursion as well as the rule budgets."""
    try:
        return _compile_rule_adapter_files(files, entry, method, config, rules)
    except (RecursionError, MemoryError) as exc:
        raise AdapterError('Source rule inspection exceeded its bounded AST recursion or memory budget; narrow the selected source.') from exc


def validate_rule_adapter_files(payload, files):
    """Rebuild all selected facts/proofs independently and compare the instance."""
    if not isinstance(payload, dict) or len(_canonical(payload).encode('utf-8')) > MAX_DEFINITION_BYTES:
        raise AdapterError('Rule adapter definition must be a bounded JSON object.')
    if payload.get('schema') != ADAPTER_SCHEMA:
        raise AdapterError('Unsupported rule adapter schema.')
    if payload.get('generatorRevision') != GENERATOR_REVISION:
        raise AdapterError('Adapter is stale: source rule interpreter changed; compile and review a new instance.')
    binding = payload.get('binding')
    if not isinstance(binding, dict) or not all(key in binding for key in ('entry', 'method', 'sourceFiles')):
        raise AdapterError('Rule adapter lacks a source binding.')
    files = _checked_files(files)
    if binding['sourceFiles'] != [{'path': path, 'sha256': _sha(text)} for path, text in sorted(files.items())]:
        raise AdapterError('Adapter is stale: source files or source hashes changed; compile a new rule instance.')
    try:
        expected = compile_rule_adapter_files(files, binding['entry'], binding['method'], payload.get('config'), payload.get('rules'))
        presentation = _presentation(payload.get('presentation'), {node['id'] for node in expected['children']})
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise AdapterError('Rule adapter facts, patterns or source binding are invalid.') from exc
    if {key: value for key, value in payload.items() if key != 'presentation'} != {key: value for key, value in expected.items() if key != 'presentation'}:
        raise AdapterError('Rule adapter source evidence, selected facts, proofs or authority were changed; recompile from current source.')
    return {**expected, 'presentation': presentation}
