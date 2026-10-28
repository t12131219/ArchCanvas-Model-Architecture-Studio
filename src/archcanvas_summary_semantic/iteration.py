"""Source name bindings for normal loop completion, never a time-axis proof."""
import ast


VERSION = 'iteration-bindings/1'


def loop_names(statement, bound):
    """Admit control flow whose reaching definitions the lowerer represents.

    Exit statements, nested scopes/loops, implicit writes and short-circuit
    expressions need their own control-flow contracts. Calls are inspected after
    lowering; opaque/effectful bodies must not receive this contract.
    """
    if statement.orelse:
        return None
    forbidden = (ast.Break, ast.Continue, ast.Return, ast.Raise, ast.Try, ast.With,
                 ast.AsyncWith, ast.AsyncFor, ast.FunctionDef, ast.AsyncFunctionDef,
                 ast.ClassDef, ast.Global, ast.Nonlocal, ast.Delete, ast.AugAssign,
                 ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await, ast.BoolOp,
                 ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
                 ast.Match, ast.Import, ast.ImportFrom)
    for node in ast.walk(statement):
        if isinstance(node, forbidden) or node is not statement and isinstance(node, (ast.For, ast.While)):
            return None
        if isinstance(node, ast.Starred):
            return None
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, ast.Store):
            return None
    assigned = {n.id for child in statement.body for n in ast.walk(child)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    iterator = {n.id for n in ast.walk(statement.target) if isinstance(n, ast.Name)} if isinstance(statement, ast.For) else set()
    # Loop targets have separate item/possibly-empty exit semantics. Rebinding
    # the same name in the body needs a richer item/entry selection contract.
    if assigned & iterator:
        return None
    return sorted((assigned - iterator) & bound.keys())


def validate_contracts(nodes, edges):
    """Check contracts against actual edges, including body reads and guards."""
    by = {n['id']: n for n in nodes}
    es = {e['id']: e for e in edges}
    errors = []
    claimed = set()

    def inside(node, frame):
        seen = set()
        while node in by and node not in seen:
            if node == frame:
                return True
            seen.add(node)
            node = by[node].get('parent')
        return False

    for loop in nodes:
        contract = loop.get('iteration_contract')
        if not contract:
            continue
        prefix = 'invalid iteration contract: ' + loop['id']
        frame = contract.get('body')
        guard = es.get(contract.get('guard_edge'), {})
        if (contract.get('rule_version') != VERSION or loop.get('operator') != 'loop'
                or by.get(frame, {}).get('semantic_type') != 'loop-template'
                or by.get(frame, {}).get('parent') != loop.get('parent')
                or by.get(contract.get('region'), {}).get('semantic_type') != 'iteration-region'
                or contract.get('region') != loop.get('parent')
                or contract.get('scope') != 'source-name-bindings; normal-completion; zero-or-more-iterations'
                or guard.get('target') != loop['id'] or guard.get('kind') != 'control'):
            errors.append(prefix)
            continue
        for row in contract.get('bindings', []):
            entry, exit_node = by.get(row.get('entry'), {}), by.get(row.get('exit'), {})
            initial, back, result = (es.get(row.get(k), {}) for k in ('initial_edge', 'backedge', 'exit_edge'))
            expected = [(initial, row.get('initial'), row.get('entry'), 'initial'),
                        (back, row.get('body_value'), row.get('entry'), 'backedge'),
                        (result, row.get('entry'), row.get('exit'), 'value')]
            valid = all(e.get('source') == s and e.get('target') == t and e.get('target_port') == p
                        and e.get('source_port') == 'out' and e.get('iteration', {}).get('loop') == loop['id']
                        for e, s, t, p in expected)
            valid = valid and entry.get('role') == 'iteration-entry' and entry.get('operator') == 'iteration-phi'
            valid = valid and entry.get('parent') == contract.get('region')
            valid = valid and exit_node.get('role') == 'iteration-exit' and exit_node.get('operator') == 'iteration-result'
            completion = es.get(row.get('completion_edge'), {})
            valid = valid and (completion.get('source'), completion.get('target'), completion.get('kind'), completion.get('target_port')) == (loop['id'], row.get('exit'), 'control', 'completion')
            valid = valid and inside(row.get('body_value'), frame)
            actual_reads = {e['id'] for e in edges if e['source'] == row.get('entry')
                            and (inside(e['target'], frame) or e['target'] in contract.get('guard_nodes', [])
                                 or e['id'] == contract.get('guard_edge'))}
            valid = valid and set(row.get('read_edges', [])) == actual_reads
            valid = valid and all(by.get(n, {}).get('iteration', {}).get('loop') == loop['id']
                                  for n in (row.get('entry'), row.get('exit')))
            valid = valid and all(by.get(n, {}).get('iteration', {}).get('name') == row.get('name')
                                  for n in (row.get('entry'), row.get('exit')))
            valid = valid and not claimed.intersection({row.get('entry'), row.get('exit')})
            claimed.update({row.get('entry'), row.get('exit')})
            if not valid:
                errors.append(prefix + ':' + str(row.get('name')))
        if any(n.get('kind') == 'opaque' or n.get('mutable') for n in nodes if inside(n['id'], frame)):
            errors.append(prefix + ':opaque-or-effectful-body')
    for node in nodes:
        if node.get('role') in {'iteration-entry', 'iteration-exit'} and node['id'] not in claimed:
            errors.append('unclaimed iteration binding: ' + node['id'])
    return errors
