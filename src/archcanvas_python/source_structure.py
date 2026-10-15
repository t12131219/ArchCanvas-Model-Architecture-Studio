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
from .discovery import discover_files

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
        self.statement_nodes = {}
        self.branch_scopes = {}
        self.condition_scopes = {}
        self.loop_scopes = {}
        self.flow_roots = []
        self.flow_functions = {}
        self.alternatives = {}
        self.sequences = []
        self.containment = None
        self.definitions = {}

    def binding_choices(self, unit, definition, name):
        """Follow source factory/argument evidence without claiming execution.

        Inventory relationships describe possible containment across authored
        call sites. They are inspection children, never tensor graph bindings.
        """
        if self.containment is None:
            self.containment = discover_files({own.path: own.content for own in self.analyzer.corpus.units.values()})["relationships"]
        owner = f"{unit.module}:{definition.name}"
        matches = []
        for relation in self.containment:
            if relation["owner"] != owner or relation["slot"] != name:
                continue
            located = self.bound_constructor(relation)
            if located:
                own, call = located
                guards = ("source containment candidate; runtime path/configuration unverified",) if relation["certainty"] == "possible" else ()
                matches.append((call, guards, own, relation))
        direct = [(call, guards, unit, {"owner": owner, "slot": name})
                  for call, guards in self.constructors(definition, name)]
        # A factory call and its source-proven result are one containment fact,
        # not independent modules or alternative tensor producers.
        if matches:
            direct = [item for item in direct if self.analyzer.corpus.definition(item[2].resolve(item[0].func))
                      or item[2].resolve(item[0].func).startswith("torch.nn.")]
        choices, seen = [], set()
        for item in [*direct, *matches]:
            key = item[2].path, item[0].lineno, item[0].col_offset, item[0].end_lineno, item[0].end_col_offset
            if key not in seen:
                seen.add(key)
                choices.append(item)
        return choices

    def bound_constructor(self, relation):
        evidence = relation.get("targetEvidence", {})
        unit = next((own for own in self.analyzer.corpus.units.values() if own.path == evidence.get("file")), None)
        if not unit:
            return None
        calls = [call for call in ast.walk(unit.tree) if isinstance(call, ast.Call)
                 and call.lineno == evidence.get("line") and call.end_lineno == evidence.get("endLine")
                 and unit.expression(call) == evidence.get("expression")]
        return (unit, calls[0]) if len(calls) == 1 else None

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
                    for constructor, guards, own, relation in self.binding_choices(unit, definition, name) if definition and name else []:
                        self.module(constructor, own, name, loop['id'], depth, stack, guards, relation)
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
        choices = self.binding_choices(unit, definition, name) if definition and name else []
        if choices:
            holder = None
            if len(choices) > 1:
                holder = self.node(parent, unit, call, name, "SourceAlternatives")
                if not holder:
                    return
            targets = []
            for constructor, guards, own, relation in choices:
                module = self.module(constructor, own, name, holder["id"] if holder else parent, depth, stack, guards, relation)
                if module:
                    targets.append(module['id'])
            self.call_nodes[parent, id(call)] = targets
            if holder:
                self.alternatives[holder['id']] = targets
            return
        method = next((item for item in definition.body if isinstance(item, ast.FunctionDef) and item.name == name), None) if definition and name else None
        method_key = (unit.module, definition.name, name) if definition else None
        if method and not method.decorator_list and method_key not in stack and depth < MAX_STRUCTURE_DEPTH:
            method_node = self.node(parent, unit, call, unit.expression(call.func), 'SourceMethod')
            if method_node:
                self.call_nodes[parent, id(call)] = [method_node['id']]
                self.flow_roots.append((method.body, unit, method_node['id']))
                self.flow_functions[method_node['id']] = method
                self.defer(method_node['id'], self.block, method.body, unit, definition, method_node['id'], depth + 1, (*stack, method_key))
        else:
            self.leaf(parent, unit, call, unit.expression(call.func), 'SourceCall')

    def module(self, constructor, unit, name, parent, depth, stack, guards=(), relation=None):
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
        if relation and relation.get("targetEvidence"):
            parameters["bindingEvidence"] = "source containment across factory/constructor arguments; no execution path selected"
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
            # This is a source definition tree, not a runtime instance graph.
            # Preserve each call/construction card and its own arguments, but
            # inspect a shared class body once. Its referenced body includes
            # all authored branches rather than one guessed configuration.
            # Small call-site bodies retain separate dependency scopes. Large
            # repeated class bodies use an explicit source reference to keep
            # inspection bounded without conflating any runtime invocation.
            reference_body = sum(1 for _ in ast.walk(cls)) > 192
            if reference_body and key in self.definitions:
                module["parameters"]["definitionReference"] = self.definitions[key]
                module["parameters"]["definitionScope"] = "shared source body only; this construction and runtime instance remain distinct"
                return module
            if reference_body:
                self.definitions[key] = module["id"]
            method = self.analyzer.corpus.entry_method(own_unit, cls)
            if method:
                method_unit, forward = method
                method_cls = next((candidate for candidate in method_unit.classes.values()
                                   if candidate.lineno <= forward.lineno <= candidate.end_lineno), cls)
                self.flow_roots.append((forward.body, method_unit, module['id']))
                self.flow_functions[module['id']] = forward
                self.defer(module['id'], self.block, forward.body, method_unit, method_cls, module['id'], depth + 1, (*stack, key))
        elif qualified in ("torch.nn.ModuleList", "torch.nn.Sequential"):
            # A configured collection exposes one source element template per
            # authored call-site candidate. Unknown counts are never replaced
            # with a guessed unrolling count from another entry's defaults.
            templates = [item for item in self.containment or []
                         if relation and item["owner"] == relation.get("owner")
                         and item["slot"].startswith(relation.get("slot", "") + "[")
                         and item.get("targetLocal")]
            if templates:
                module["parameters"]["repeatExpression"] = "source element templates; configured collection count is unresolved"
                comprehensions = [arg for arg in constructor.args if isinstance(arg, ast.ListComp)]
                header = ("for " + ", ".join(f"{ast.unparse(generator.target)} in {ast.unparse(generator.iter)}"
                                            for generator in comprehensions[0].generators)) if comprehensions else "for configured element in " + name
                loop = self.node(module["id"], unit, comprehensions[0] if comprehensions else constructor,
                                 header, "SourceLoop", {"repeatExpression": header,
                                                        "repetitionStatus": "source template only; runtime count unverified"})
                template_parent = loop["id"] if loop else module["id"]
                used = set()
                for template in templates:
                    located = self.bound_constructor(template)
                    if not located:
                        continue
                    own, call = located
                    binding = own.path, call.lineno, call.col_offset
                    if binding in used:
                        continue
                    used.add(binding)
                    self.defer(template_parent, self.module, call, own, template["slot"], template_parent, depth + 1, stack,
                               ("source element template; runtime repetition unverified",), template)
                return module
            if qualified == 'torch.nn.Sequential':
                sequence = [None] * len(constructor.args)
                self.sequences.append((module['id'], sequence, unit, constructor))
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
        self.regions = regions
        for region, statement, spec, _ in regions:
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
            elif node and isinstance(args[2], ast.stmt):
                self.statement_nodes[args[0], id(args[2])] = [node['id']]
        if self.limited:
            self.analyzer.warn(f"Source structure inspection reached its {MAX_STRUCTURE_NODES}-node/{MAX_STRUCTURE_DEPTH}-level budget; original source expressions remain available. No execution path or tensor contract was inferred from inspection nodes.")
        return source_dependencies(self)
