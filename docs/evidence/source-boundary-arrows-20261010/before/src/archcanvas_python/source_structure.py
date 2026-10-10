"""Bounded source inspection beneath unresolved control-flow boundaries.

These are syntax and definition facts, not additional tensor producers. Both
paths stay visible without selecting a config, executing a module, or inventing
repeat counts. The original conservative boundary keeps its data-flow ports.
"""
from __future__ import annotations

import ast
import hashlib
from collections import deque
from .source_dependencies import source_dependencies

MAX_STRUCTURE_NODES = 480
MAX_STRUCTURE_DEPTH = 12


class SourceStructure:
    def __init__(self, analyzer, max_nodes):
        self.analyzer = analyzer
        self.remaining = min(MAX_STRUCTURE_NODES, max_nodes - len(analyzer.nodes))
        self.limited = False
        self.pending = deque()
        self.leaves = deque()
        self.modules = {}
        self.call_nodes = {}
        self.branch_scopes = {}
        self.condition_scopes = {}
        self.loop_scopes = {}
        self.flow_roots = []
        self.sequences = []

    def defer(self, parent, callback, *args):
        # Inspect shallow siblings before descending. A large first branch must
        # never consume the budget before the alternative is even represented.
        self.pending.append((parent, callback, args))

    def leaf(self, parent, unit, expression, label, kind):
        # Arithmetic/tensor expressions remain in the source span. Represent
        # them after module definitions and branch/loop structure, so simple
        # syntax cannot crowd out the available nested model architecture.
        self.leaves.append((parent, unit, expression, label, kind))

    def limit(self, parent):
        self.limited = True
        node = next(n for n in self.analyzer.nodes if n['id'] == parent)
        node['parameters']['inspectionLimit'] = 'source inspection budget; original expression retained'

    def node(self, parent, unit, expression, label, kind, parameters=None):
        if self.remaining <= 0:
            self.limit(parent)
            return None
        self.remaining -= 1
        fingerprint = hashlib.sha256(ast.dump(expression, include_attributes=False).encode()).hexdigest()[:10]
        node = self.analyzer.node(f"source:{parent}:{kind}:{fingerprint}", label[:120], kind,
                                  "container" if kind != "SourceCall" else "operator",
                                  parent, unit, expression, parameters=parameters)
        node["sourceStructure"] = True
        return node

    @staticmethod
    def self_attribute(expression):
        while isinstance(expression, (ast.Subscript, ast.Attribute)):
            if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name) and expression.value.id == "self":
                return expression.attr
            expression = expression.value
        return None

    def constructors(self, definition, name, guards=(), visited=()):
        """Retain authored alternatives and their guards, never pick a branch."""
        if name in visited or len(visited) >= MAX_STRUCTURE_DEPTH:
            return []
        init = next((item for item in definition.body if isinstance(item, ast.FunctionDef) and item.name == "__init__"), None)
        if not init:
            return []
        choices = []

        def statements(body, context):
            for statement in body:
                if isinstance(statement, ast.If):
                    predicate = ast.unparse(statement.test)
                    statements(statement.body, (*context, predicate))
                    statements(statement.orelse, (*context, f"not ({predicate})"))
                elif isinstance(statement, (ast.For, ast.While)):
                    statements(statement.body, (*context, ast.unparse(statement).split(":", 1)[0]))
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    if any(self.self_attribute(target) == name and isinstance(target, ast.Attribute) for target in targets):
                        value = statement.value
                        if isinstance(value, ast.Call):
                            choices.append((value, context))
                        elif isinstance(value, ast.Attribute) and self.self_attribute(value):
                            choices.extend(self.constructors(definition, self.self_attribute(value), context, (*visited, name)))
        statements(init.body, guards)
        return choices

    def block(self, statements, unit, definition, parent, depth, stack):
        if depth > MAX_STRUCTURE_DEPTH:
            self.limit(parent)
            return
        for statement in statements:
            if self.remaining <= 0:
                self.limit(parent)
                return
            if isinstance(statement, ast.If):
                condition = self.node(parent, unit, statement, f"if {unit.expression(statement.test)}", "SourceConditional")
                if condition:
                    self.condition_scopes[parent, id(statement)] = condition['id']
                    self.branches(statement, unit, definition, condition["id"], depth, stack)
            elif isinstance(statement, (ast.For, ast.While)):
                header = ast.unparse(statement).split(":", 1)[0]
                loop = self.node(parent, unit, statement, header, "SourceLoop", {"repeatExpression": header})
                if loop:
                    self.loop_scopes[parent, id(statement)] = loop['id']
                    # A symbolic ModuleList is still a real source definition.
                    # Show its element template without guessing its length or
                    # pretending the local iteration variable is a tensor op.
                    iterator = statement.iter if isinstance(statement, ast.For) else None
                    name = self.self_attribute(iterator)
                    for constructor, guards in self.constructors(definition, name) if definition and name else []:
                        self.module(constructor, unit, name, loop['id'], depth, stack, guards)
                    self.defer(loop['id'], self.block, statement.body, unit, definition, loop['id'], depth + 1, stack)
                    self.defer(loop['id'], self.block, statement.orelse, unit, definition, loop['id'], depth + 1, stack)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # A nested definition is source data, not an executed call.
                self.leaf(parent, unit, statement, getattr(statement, "name", "definition"), "SourceCode")
            else:
                calls = [item for item in ast.walk(statement) if isinstance(item, ast.Call)]
                if not calls and not isinstance(statement, (ast.Pass, ast.Expr)):
                    caption = "return" if isinstance(statement, ast.Return) else ast.unparse(statement).split("=", 1)[0].strip()
                    self.leaf(parent, unit, statement, caption or "statement", "SourceCode")
                for call in calls:
                    self.call(call, unit, definition, parent, depth, stack)

    def branches(self, statement, unit, definition, parent, depth, stack):
        predicate = ast.unparse(statement.test)
        scopes = []
        for label, body in ((f"if {predicate}", statement.body), ("else", statement.orelse)):
            branch = self.node(parent, unit, statement, label, "SourceBranch", {"condition": predicate if label != "else" else f"not ({predicate})"})
            if branch:
                scopes.append(branch['id'])
                self.defer(branch['id'], self.block, body, unit, definition, branch['id'], depth + 1, stack)
            else:
                scopes.append(None)
        self.branch_scopes[parent, id(statement)] = scopes

    def call(self, call, unit, definition, parent, depth, stack):
        name = self.self_attribute(call.func)
        choices = self.constructors(definition, name) if definition and name else []
        if choices:
            holder = None
            if len(choices) > 1:
                holder = self.node(parent, unit, call, name, "SourceAlternatives")
                if not holder:
                    return
            targets = []
            for constructor, guards in choices:
                module = self.module(constructor, unit, name, holder["id"] if holder else parent, depth, stack, guards)
                if module:
                    targets.append(module['id'])
            self.call_nodes[parent, id(call)] = [holder['id']] if holder else targets
            return
        method = next((item for item in definition.body if isinstance(item, ast.FunctionDef) and item.name == name), None) if definition and name else None
        method_key = (unit.module, definition.name, name) if definition else None
        if method and not method.decorator_list and method_key not in stack and depth < MAX_STRUCTURE_DEPTH:
            method_node = self.node(parent, unit, call, unit.expression(call.func), 'SourceMethod')
            if method_node:
                self.call_nodes[parent, id(call)] = [method_node['id']]
                self.flow_roots.append((method.body, unit, method_node['id']))
                self.defer(method_node['id'], self.block, method.body, unit, definition, method_node['id'], depth + 1, (*stack, method_key))
        else:
            self.leaf(parent, unit, call, unit.expression(call.func), 'SourceCall')

    def module(self, constructor, unit, name, parent, depth, stack, guards=()):
        # This hierarchy describes definitions, not invocation counts. Repeated
        # calls to one authored attribute share one definition in this scope.
        # Repeated references to one constructor share its card. Separate
        # authored constructor occurrences remain separate even with equal AST.
        identity = (parent, unit.module, name, guards, id(constructor))
        if identity in self.modules:
            return self.modules[identity]
        qualified = unit.resolve(constructor.func)
        definition = self.analyzer.corpus.definition(qualified)
        parameters = {"sourceType": ast.unparse(constructor.func), "construction": ast.unparse(constructor)}
        if guards:
            parameters["constructedWhen"] = " and ".join(f"({guard})" for guard in guards)
        module = self.node(parent, unit, constructor, name, "SourceModule", parameters)
        if not module:
            return
        self.modules[identity] = module
        if depth >= MAX_STRUCTURE_DEPTH:
            module["parameters"]["inspectionLimit"] = "definition depth limit; original construction retained"
            self.limited = True
            return module
        if definition:
            own_unit, cls = definition
            key = (own_unit.module, cls.name)
            if key in stack:
                module["parameters"]["inspectionLimit"] = "recursive definition; original construction retained"
                return module
            module["parameters"]["sourceType"] = cls.name
            module["parameters"]["definition"] = f"{own_unit.module}:{cls.name}"
            forward = next((item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == "forward"), None)
            if forward:
                self.flow_roots.append((forward.body, own_unit, module['id']))
                self.defer(module['id'], self.block, forward.body, own_unit, cls, module['id'], depth + 1, (*stack, key))
        elif qualified in ("torch.nn.ModuleList", "torch.nn.Sequential"):
            if qualified == 'torch.nn.Sequential':
                sequence = [None] * len(constructor.args)
                self.sequences.append((sequence, unit, constructor))
                def element(item, index):
                    child = self.module(item, unit, unit.expression(item.func), module['id'], depth + 1, stack)
                    if child:
                        sequence[index] = child['id']
                for index, item in enumerate(constructor.args):
                    if isinstance(item, ast.Call):
                        self.defer(module['id'], element, item, index)
                return module
            for arg in constructor.args:
                if isinstance(arg, ast.ListComp):
                    caption = "for " + ", ".join(f"{ast.unparse(g.target)} in {ast.unparse(g.iter)}" for g in arg.generators)
                    loop = self.node(module["id"], unit, arg, caption, "SourceLoop", {"repeatExpression": caption})
                    if loop and isinstance(arg.elt, ast.Call):
                        self.defer(loop['id'], self.module, arg.elt, unit, unit.expression(arg.elt.func), loop['id'], depth + 1, stack)
                else:
                    elements = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
                    for item in elements:
                        if isinstance(item, ast.Call):
                            self.defer(module['id'], self.module, item, unit, unit.expression(item.func), module['id'], depth + 1, stack)
        return module

    def populate(self, regions):
        for region, statement, spec in regions:
            self.branches(statement, spec.unit, spec.definition, region["id"], 0, ())
            self.flow_roots.append(([statement], spec.unit, region['id']))
        while self.pending:
            parent, callback, args = self.pending.popleft()
            if self.remaining > 0:
                callback(*args)
            elif args[0]:
                self.limit(parent)
        while self.leaves:
            args = self.leaves.popleft()
            node = self.node(*args)
            if node and isinstance(args[2], ast.Call):
                self.call_nodes[args[0], id(args[2])] = [node['id']]
        if self.limited:
            self.analyzer.warn(f"Source structure inspection reached its {MAX_STRUCTURE_NODES}-node/{MAX_STRUCTURE_DEPTH}-level budget; original source expressions remain available. No execution path or tensor contract was inferred from inspection nodes.")
        return source_dependencies(self)
