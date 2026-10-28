"""Tiny decidable value language for construction paths; no eval or imports."""
import ast
import operator

UNKNOWN = object()


def value(node, constants, objects=None):
    objects = objects or {}
    if node is None:
        return UNKNOWN
    name = ast.unparse(node)
    if name in constants:
        result = constants[name]
        return UNKNOWN if isinstance(result, dict) and 'unresolved' in result else result
    if isinstance(node, ast.Constant) and type(node.value) in (bool, int, float, str, type(None)):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        result = [value(n, constants, objects) for n in node.elts]
        return result if len(result) <= 64 and all(v is not UNKNOWN for v in result) else UNKNOWN
    if isinstance(node, ast.Subscript):
        base, index = value(node.value, constants, objects), value(node.slice, constants, objects)
        if type(base) in (dict, list, tuple, str) and type(index) in (str, int):
            try:
                return base[index]
            except (KeyError, IndexError, TypeError):
                pass
    if isinstance(node, ast.UnaryOp):
        operand = value(node.operand, constants, objects)
        if operand is not UNKNOWN:
            if isinstance(node.op, ast.Not): return not operand
            if isinstance(node.op, ast.USub) and type(operand) in (int, float): return -operand
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        a, b = value(node.left, constants, objects), value(node.comparators[0], constants, objects)
        op = node.ops[0]
        if isinstance(op, (ast.Is, ast.IsNot)) and b is None and name not in constants:
            # Proven constructed modules/collections are non-None. Do not use
            # structural/dataclass equality as Python object identity.
            if ast.unparse(node.left) in objects:
                return isinstance(op, ast.IsNot)
        if a is not UNKNOWN and b is not UNKNOWN:
            if isinstance(op, (ast.Is, ast.IsNot)):
                if a is not None and b is not None and type(a) is not bool and type(b) is not bool:
                    return UNKNOWN
                return (a is b) if isinstance(op, ast.Is) else (a is not b)
            functions = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                         ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                         ast.In: lambda x,y: x in y, ast.NotIn: lambda x,y: x not in y}
            if type(op) in functions:
                try: return functions[type(op)](a,b)
                except (TypeError, ValueError): pass
    return UNKNOWN
