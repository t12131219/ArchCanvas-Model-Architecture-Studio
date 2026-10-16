"""Bounded edits at independently located Python expression boundaries.

This is deliberately not a lowering of inspection arrows.  Existing branches,
helpers and loops remain source bytes.  A changed input must name an existing
unary call argument or a static return slot; every new operation must terminate
at one such boundary.  No model is imported or executed.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile

from archcanvas_python import analyze_project
from archcanvas_python.frontend import CONTRACTS
from .draft import DraftError


def structural_delta(draft):
    original = draft["sourceProvenance"]["originalGraph"]
    return ({node["id"] for node in draft["nodes"]} != {node["id"] for node in original["nodes"]}
            or {edge["id"]: edge for edge in draft["edges"]} != {edge["id"]: edge for edge in original["edges"]})


class Surgery:
    def __init__(self, draft, architecture=None, mapping=None):
        from .catalog import BY_KIND
        from .custom_modules import custom_spec
        self.draft = draft
        self.provenance = draft["sourceProvenance"]
        self.architecture = architecture or self.provenance["architecture"]
        self.mapping = mapping or {}
        self.facts = {node["id"]: node for node in self.architecture["nodes"]}
        self.refs = self.provenance["nodeRefs"]
        self.original = {node["id"]: node for node in self.provenance["originalGraph"]["nodes"]}
        self.nodes = {node["id"]: node for node in draft["nodes"]}
        self.added = set(self.nodes) - set(self.original)
        self.deleted = set(self.original) - set(self.nodes)
        self.original_edges = self.provenance["originalGraph"]["edges"]
        self.incoming = {(edge["target"]["nodeId"], edge["target"]["portId"]): edge for edge in draft["edges"]}
        self.before = {(edge["target"]["nodeId"], edge["target"]["portId"]): edge for edge in self.original_edges}
        self.custom = {item["kind"]: item for item in draft.get("customModules", [])}
        self.specs = {**BY_KIND, **{kind: custom_spec(item) for kind, item in self.custom.items()},
                      **{item["kind"]: item for item in self.provenance["modules"]}}
        self.sources = {item["path"]: item for item in self.architecture["sources"]}
        self.units, self.patches, self.files, self.owners, self.attributes = {}, [], {}, {}, {}
        self.used, self.deleted_calls, self.import_aliases, self.occurrences = set(), [], {}, {}

    def fail(self, message, identity=None):
        from .source_preservation import _unsupported
        _unsupported(message, identity)

    def fact(self, identity):
        if identity not in self.refs:
            self.fail("An original object lost its canonical source reference.", identity)
        canonical = self.mapping.get(identity, self.refs[identity]["nodeId"])
        if canonical not in self.facts:
            self.fail("A retained source object has no independently reanalyzed identity.", identity)
        return self.facts[canonical]

    def unit(self, path):
        if path not in self.sources:
            self.fail("The anchor file is absent from the frozen source corpus.")
        if path not in self.units:
            source = self.sources[path]["content"]
            tree = ast.parse(source)
            parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
            lines = source.splitlines(keepends=True)
            starts, offset = [], 0
            for line in lines:
                starts.append(offset); offset += len(line.encode("utf-8"))
            self.units[path] = (tree, parents, lines, starts)
        return self.units[path]

    def span(self, path, node):
        from .source_preservation import _raw
        _, _, _, starts = self.unit(path)
        raw = _raw(self.sources[path])
        bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
        return bom + starts[node.lineno-1] + node.col_offset, bom + starts[node.end_lineno-1] + node.end_col_offset

    def expression(self, path, node):
        from .source_preservation import _raw
        start, end = self.span(path, node)
        return _raw(self.sources[path])[start:end].decode("utf-8")

    def locate(self, fact, types):
        source = fact.get("source", {})
        path = source.get("path")
        if path not in self.sources:
            self.fail("The source operation has no frozen file anchor.")
        tree, _, _, _ = self.unit(path)
        matches = [node for node in ast.walk(tree) if isinstance(node, types)
                   and node.lineno == source.get("line") and node.end_lineno == source.get("endLine")
                   and self.expression(path, node) == source.get("expression")]
        if len(matches) != 1:
            self.fail("The source span does not identify one exact independently located AST operation.")
        return path, matches[0]

    def owner(self, path, expression):
        _, parents, _, _ = self.unit(path)
        function = expression
        while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            function = parents.get(function)
        cls = parents.get(function)
        if (not isinstance(function, ast.FunctionDef) or function.name not in ("forward", "__call__")
                or function.decorator_list or not isinstance(cls, ast.ClassDef) or cls.decorator_list or cls.keywords
                or not function.args.args or function.args.args[0].arg != "self"):
            self.fail("An edit needs an ordinary directly authored forward or __call__ method in one source class.")
        if any(isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(function)):
            self.fail("The source method rebinds self; its instance ownership is not stable.")
        for member in ast.walk(cls):
            if (isinstance(member, ast.Attribute) and member.attr in {"forward", "__call__"}
                    and isinstance(member.value, ast.Name) and member.value.id == "self" and isinstance(member.ctx, (ast.Store, ast.Del))):
                self.fail("The model rebinds its entry callable; editing the class method would not identify the invoked source.")
            if (isinstance(member, ast.Call) and isinstance(member.func, ast.Name) and member.func.id in {"setattr", "delattr"}
                    and member.args and isinstance(member.args[0], ast.Name) and member.args[0].id == "self"):
                if len(member.args) < 2 or not isinstance(member.args[1], ast.Constant) or member.args[1].value in {"forward", "__call__"}:
                    self.fail("Dynamic entry callable mutation cannot establish an exact invocation anchor.")
        from .custom_modules import _scope_bindings
        if _scope_bindings(cls.body).count(function.name) != 1:
            self.fail("The source class replaces or decorates its entry method binding.")
        return function, cls

    def patch(self, path, node, replacement, action, identity=None):
        start, end = self.span(path, node)
        if action == "rewrite-input":
            self.patches = [item for item in self.patches if not (item["action"] == "bypass-call" and item["path"] == path
                                                                  and start <= item["start"] and item["end"] <= end)]
        self.patches.append({"path": path, "start": start, "end": end, "replacement": replacement.encode("utf-8"),
                             "before": self.expression(path, node), "after": replacement, "action": action,
                             **({"nodeId": identity} if identity else {})})

    def edited_expression(self, path, node):
        from .source_preservation import _raw
        start, end = self.span(path, node)
        raw = _raw(self.sources[path])[start:end]
        for patch in sorted((item for item in self.patches if item["action"] == "bypass-call" and item["path"] == path
                             and start <= item["start"] and item["end"] <= end), key=lambda item: item["start"], reverse=True):
            raw = raw[:patch["start"]-start] + patch["replacement"] + raw[patch["end"]-start:]
        return raw.decode("utf-8")

    def ports(self, identity, direction, original=False):
        node = (self.original if original else self.nodes)[identity]
        return [port for port in self.specs[node["kind"]]["ports"] if port["direction"] == direction]

    def unary(self, identity, original=False):
        inputs, outputs = self.ports(identity, "in", original), self.ports(identity, "out", original)
        if len(inputs) != 1 or len(outputs) != 1:
            self.fail("Bounded source surgery requires one explicit input and one output per edited module.", identity)
        return inputs[0], outputs[0]

    def bypass(self, end):
        seen = set()
        while end["nodeId"] in self.deleted:
            identity = end["nodeId"]
            if identity in seen:
                self.fail("Deleted source modules form a cycle.")
            seen.add(identity)
            port, _ = self.unary(identity, True)
            edge = self.before.get((identity, port["id"]))
            if not edge:
                self.fail("A deleted module has no exact original input relation.", identity)
            end = edge["source"]
        return end

    def peel(self, end):
        chain, seen = [], set()
        while end["nodeId"] in self.added:
            identity = end["nodeId"]
            if identity in seen:
                self.fail("An inserted source chain forms a cycle.")
            seen.add(identity)
            port, output = self.unary(identity)
            if end["portId"] != output["id"]:
                self.fail("An inserted module output does not match its checked port contract.", identity)
            edge = self.incoming.get((identity, port["id"]))
            if not edge:
                self.fail("An inserted module needs its declared input connected.", identity)
            if sum(edge["source"]["nodeId"] == identity for edge in self.draft["edges"]) != 1:
                self.fail("A new operation must have one consumer; shared-value insertion needs an explicit assignment contract.", identity)
            chain.append(identity)
            end = edge["source"]
        return end, list(reversed(chain))

    def call_argument(self, identity, port_id):
        fact = self.fact(identity)
        # Inspection relations intentionally have no lowering contract.
        if fact.get("sourceStructure") or fact.get("children") or fact["kind"] not in CONTRACTS:
            self.fail("The target is an inspection or unresolved source relation, not an anchored module call.", identity)
        bindings = set((item["nodeId"], item["portId"]) for item in self.refs[identity]["portBindings"].get(port_id, []))
        if len(bindings) != 1:
            self.fail("A collapsed proxy input combines multiple canonical source slots; expand it first.", identity)
        inputs = [port for port in fact["ports"] if port["direction"] == "in"]
        if len(inputs) != 1:
            self.fail("Only an explicitly anchored unary call argument can be rewritten.", identity)
        path, call = self.locate(fact, ast.Call)
        if len(call.args) == 1 and not call.keywords and not isinstance(call.args[0], ast.Starred):
            argument = call.args[0]
        elif not call.args and len(call.keywords) == 1 and call.keywords[0].arg == inputs[0]["name"]:
            argument = call.keywords[0].value
        else:
            self.fail("This module call has unpacked or extra arguments without a bounded rewrite contract.", identity)
            self.owner(path, call)
        return path, call, argument

    def targets(self, identity, port_id):
        fact = self.fact(identity)
        siblings = [item for item in self.facts.values() if not item.get("sourceStructure")
                    and item["kind"] == fact["kind"] and item.get("source") == fact.get("source")
                    and (fact["kind"] != "Output" or item.get("outputPath") == fact.get("outputPath"))]
        if len(siblings) != 1:
            self.fail("This source target is reused by multiple instances; one visual occurrence cannot rewrite all of them.", identity)
        if fact["kind"] != "Output":
            path, _, argument = self.call_argument(identity, port_id)
            return [(path, argument)]
        path, function = self.locate(fact, ast.FunctionDef)
        self.owner(path, function)
        returns = []
        pending = list(function.body)
        while pending:
            node = pending.pop()
            if isinstance(node, ast.Return):
                if node.value is None:
                    self.fail("A bare return cannot be wrapped as a tensor output.", identity)
                value = node.value
                for step in fact.get("outputPath", []):
                    if step["kind"] == "index" and isinstance(value, (ast.Tuple, ast.List)) and step["index"] < len(value.elts):
                        value = value.elts[step["index"]]
                    elif step["kind"] == "key" and isinstance(value, ast.Dict):
                        choices = [item for key, item in zip(value.keys, value.values) if isinstance(key, ast.Constant) and type(key.value) is type(step["key"]) and key.value == step["key"]]
                        if len(choices) != 1:
                            self.fail("The requested output key is not present in every source return.", identity)
                        value = choices[0]
                    else:
                        self.fail("The requested output slot is not statically present in every source return.", identity)
                returns.append((path, value))
            elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                pending.extend(ast.iter_child_nodes(node))
        if not returns:
            self.fail("The source output has no explicit return expression.", identity)
        return returns

    def source_value(self, end, path, target):
        """Refer to an existing dominated value; never re-evaluate a call."""
        identity = end["nodeId"]
        fact = self.fact(identity)
        function, _ = self.owner(path, target)
        if fact["kind"] == "Input":
            own_path, own_function = self.locate(fact, ast.FunctionDef)
            if own_path != path or own_function is not function:
                self.fail("Rewiring an input across source methods is unsupported.", identity)
            value = fact["label"]
            start = function.lineno
        else:
            if fact.get("sourceStructure") or fact.get("children") or fact["kind"] not in CONTRACTS:
                self.fail("A new producer must have an explicit local value anchor, not an inspection arrow.", identity)
            own_path, call = self.locate(fact, ast.Call)
            _, parents, _, _ = self.unit(own_path)
            assignment = parents.get(call)
            if (own_path != path or not isinstance(assignment, ast.Assign) or assignment.value is not call
                    or len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name)
                    or assignment not in function.body or assignment.end_lineno >= target.lineno):
                self.fail("The producer needs a preceding, direct, single-name assignment in the consumer method.", identity)
            value, start = assignment.targets[0].id, assignment.end_lineno + 1
        # A mutated/rebound value cannot stand for the earlier source fact.
        if any(isinstance(node, ast.Name) and node.id == value and isinstance(node.ctx, (ast.Store, ast.Del))
               and start <= node.lineno <= target.lineno for node in ast.walk(function)):
            self.fail("The selected source value is rebound before this target; its data-flow identity is ambiguous.", identity)
        _, parents, _, _ = self.unit(path)
        statement = target
        ancestors = set()
        while statement in parents and not isinstance(statement, ast.stmt):
            ancestors.add(id(statement))
            statement = parents[statement]
        target_nodes = {id(node) for node in ast.walk(target)}
        if any(id(node) not in target_nodes | ancestors and isinstance(node, (ast.Call, ast.AugAssign, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom))
               for node in ast.walk(statement)):
            self.fail("Rewiring cannot cross sibling calls or mutations in the same source statement.", identity)
        # Attribute mutations, alias writes and arbitrary helper calls can
        # change a tensor without rebinding its Python name. Do not infer
        # purity across an unresolved statement interval.
        for statement in function.body:
            if statement.end_lineno < start or statement.lineno >= target.lineno:
                continue
            if (not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass))
                    or any(isinstance(node, (ast.Call, ast.Attribute, ast.Subscript, ast.AugAssign, ast.NamedExpr,
                                             ast.Yield, ast.YieldFrom, ast.Await)) for node in ast.walk(statement))):
                self.fail("Rewiring cannot cross calls, mutations or unresolved control flow; select an adjacent proven local value.", identity)
            if any(isinstance(node, ast.Name) and node.id == value and isinstance(node.ctx, ast.Load) for node in ast.walk(statement)):
                self.fail("The producer escapes into an intermediate alias or consumer before this target.", identity)
        return value

    def wrap(self, expression, chain, path, target):
        from .custom_modules import custom_output_expression
        _, cls = self.owner(path, target)
        for identity in chain:
            node = self.nodes[identity]
            kind = node["kind"]
            if kind not in CONTRACTS and kind not in self.custom:
                self.fail("The inserted module has no registered constructor or checked custom-source contract.", identity)
            owner = path, cls.name
            if identity in self.owners and self.owners[identity] != owner:
                self.fail("One inserted instance cannot be constructed in several source classes.", identity)
            self.owners[identity] = owner
            self.used.add(identity)
            attribute = "_archcanvas_" + hashlib.sha256(identity.encode()).hexdigest()[:16]
            tree, _, _, _ = self.unit(path)
            occupied = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
            if attribute in occupied:
                self.fail("The inserted module's stable attribute collides with existing source.", identity)
            self.attributes[identity] = attribute
            self.occurrences.setdefault(identity, []).append((path, self.span(path, target)))
            expression = f"self.{attribute}({expression})"
            if kind in self.custom:
                expression = custom_output_expression(self.custom[kind], self.ports(identity, "out")[0]["id"], expression)
        return expression

    def deletions(self):
        for identity in self.deleted:
            fact = self.fact(identity)
            port, _ = self.unary(identity, True)
            path, call, argument = self.call_argument(identity, port["id"])
            if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != "self":
                self.fail("Deletion requires a directly called self module attribute.", identity)
            # The exact same source call may be reused by several constructed
            # parent instances. Editing only one visual occurrence is unsafe.
            siblings = [item for item in self.facts.values() if not item.get("sourceStructure")
                        and item.get("source") == fact.get("source") and item["kind"] == fact["kind"]]
            deleted_canonical = {self.fact(key)["id"] for key in self.deleted}
            if any(item["id"] not in deleted_canonical for item in siblings):
                self.fail("The source call is shared by another retained instance; deletion would change it too.", identity)
            start, end = self.span(path, call)
            if any(item["path"] == path and item["action"] == "bypass-call"
                   and start < item["end"] and item["start"] < end for item in self.patches):
                self.fail("Nested deleted calls overlap; edit and independently reanalyze one call boundary at a time.", identity)
            self.patch(path, call, self.expression(path, argument), "bypass-call", identity)
            _, cls = self.owner(path, call)
            self.deleted_calls.append((identity, path, cls, call, call.func.attr))

    def constructors(self):
        from .custom_modules import ADAPTER, custom_filename, custom_source
        grouped, imports = {}, {}
        for identity in sorted(self.used):
            path, cls_name = self.owners[identity]
            tree, _, lines, _ = self.unit(path)
            classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls_name]
            if len(classes) != 1:
                self.fail("The source class is not a unique top-level definition.", identity)
            cls = classes[0]
            # A source-defined base or attribute hook may swallow/redirect a
            # new module assignment.  Ordinary direct nn.Module subclasses
            # have the independently registered construction contract.
            module_bases = set()
            for statement in tree.body:
                if isinstance(statement, ast.ImportFrom) and statement.module == "torch":
                    module_bases.update(f"{alias.asname or alias.name}.Module" for alias in statement.names if alias.name == "nn")
                elif isinstance(statement, ast.ImportFrom) and statement.module == "torch.nn":
                    module_bases.update(alias.asname or alias.name for alias in statement.names if alias.name == "Module")
                elif isinstance(statement, ast.Import):
                    for alias in statement.names:
                        if alias.name == "torch": module_bases.add(f"{alias.asname or alias.name}.nn.Module")
                        elif alias.name == "torch.nn": module_bases.add(f"{alias.asname}.Module" if alias.asname else "torch.nn.Module")
            from .custom_modules import _scope_bindings
            if len(cls.bases) != 1 or ast.unparse(cls.bases[0]) not in module_bases or cls.decorator_list or cls.keywords:
                self.fail("Inserted construction requires a plain direct nn.Module subclass; custom bases need a separate ownership contract.", identity)
            if set(_scope_bindings(cls.body)) & {"__setattr__", "__getattribute__", "__getattr__"}:
                self.fail("Custom instance attribute hooks have no independent inserted-module ownership contract.", identity)
            inits = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
            if len(inits) != 1 or inits[0].decorator_list:
                self.fail("An inserted module needs one directly authored ordinary initializer.", identity)
            init = inits[0]
            if (not init.args.args or init.args.args[0].arg != "self"
                    or any(isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, (ast.Store, ast.Del)) for node in ast.walk(init))):
                self.fail("The initializer must retain an ordinary self instance binding.", identity)
            if ("super" in _scope_bindings(tree.body) or "super" in _scope_bindings(init.body)
                    or "super" in [arg.arg for arg in [*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs]]):
                self.fail("The initializer's super symbol is rebound and cannot establish Module construction ownership.", identity)
            supers = [node for node in init.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                      and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "__init__"
                      and isinstance(node.value.func.value, ast.Call) and isinstance(node.value.func.value.func, ast.Name)
                      and node.value.func.value.func.id == "super"]
            if len(supers) != 1 or any(isinstance(node, (ast.Return, ast.Raise)) and node.lineno <= supers[0].end_lineno for node in ast.walk(init)):
                self.fail("The initializer needs one unconditional direct super initializer before injected construction.", identity)
            super_statement = supers[0]
            if (super_statement.value.args or super_statement.value.keywords
                    or super_statement.value.func.value.args or super_statement.value.func.value.keywords):
                self.fail("An inserted instance requires the ordinary zero-argument super().__init__() contract.", identity)
            if any(node is not super_statement and node.lineno <= super_statement.end_lineno <= node.end_lineno
                   and isinstance(node, (ast.Return, ast.Raise, ast.If, ast.For, ast.While, ast.With, ast.Try)) for node in init.body):
                self.fail("A compound initializer line cannot host an independent constructor insertion.", identity)
            if any(isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom, ast.Await)) for node in ast.walk(init)):
                self.fail("The initializer can exit before its construction tail; inserted modules need one unconditional completion boundary.", identity)
            new_line = "\r\n" if "\r\n" in self.sources[path]["content"] else "\n"
            indent = lines[super_statement.lineno-1][:super_statement.col_offset]
            if indent.strip() or not indent:
                self.fail("An inline initializer has no independent indentation anchor.", identity)
            alias_key = path, self.nodes[identity]["kind"]
            alias = "_archcanvas_import_" + hashlib.sha256((path + self.nodes[identity]["kind"]).encode()).hexdigest()[:12]
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            names.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
            names.update((node.asname or node.name.split('.')[0]) for node in ast.walk(tree) if isinstance(node, ast.alias))
            suffix = 1
            base = alias
            while alias in names:
                suffix += 1; alias = f"{base}_{suffix}"
            alias = self.import_aliases.setdefault(alias_key, alias)
            node = self.nodes[identity]
            if node["kind"] in self.custom:
                definition = self.custom[node["kind"]]
                filename = custom_filename(definition)
                content = custom_source(definition)
                if filename in self.sources and self.sources[filename]["content"] != content:
                    self.fail("A custom module file collides with different preserved source.", identity)
                self.files[filename] = content.encode("utf-8")
                imports.setdefault(path, set()).add(f"import {filename.removesuffix('.py')} as {alias}")
                constructor = f"{alias}.{ADAPTER}()"
            else:
                imports.setdefault(path, set()).add(f"from torch import nn as {alias}")
                constructor = f"{alias}.{node['kind']}({', '.join(f'{key}={value!r}' for key, value in node['parameters'].items())})"
            grouped.setdefault((path, init.end_lineno), []).append(indent + f"self.{self.attributes[identity]} = {constructor}" + new_line)
        from .source_preservation import _raw
        for (path, line), text in grouped.items():
            _, _, lines, _ = self.unit(path)
            raw = _raw(self.sources[path]); bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
            offset = bom + sum(len(item.encode("utf-8")) for item in lines[:line])
            self.patches.append({"path": path, "start": offset, "end": offset, "replacement": ''.join(text).encode(), "action": "construct-modules"})
        for path, declarations in imports.items():
            tree, _, lines, _ = self.unit(path)
            prefix = []
            for index, node in enumerate(tree.body):
                if isinstance(node, (ast.Import, ast.ImportFrom)) or index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    prefix.append(node)
                else:
                    break
            line = prefix[-1].end_lineno if prefix else 0
            if any(node not in prefix and node.lineno <= line for node in tree.body):
                self.fail("An inline module header cannot host an independent import insertion.")
            raw = _raw(self.sources[path]); bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
            offset = bom + sum(len(item.encode("utf-8")) for item in lines[:line])
            newline = "\r\n" if "\r\n" in self.sources[path]["content"] else "\n"
            self.patches.append({"path": path, "start": offset, "end": offset,
                                 "replacement": (newline.join(sorted(declarations)) + newline).encode(), "action": "import-modules"})
        # Remove a constructor only when every remaining load was an explicitly
        # deleted call. Shared calls and aliases keep their original instance.
        for identity, path, cls, call, attribute in self.deleted_calls:
            deleted = {id(item[3].func) for item in self.deleted_calls if item[1] == path and item[2] is cls and item[4] == attribute}
            uses = [node for node in ast.walk(cls) if isinstance(node, ast.Attribute) and node.attr == attribute
                    and isinstance(node.value, ast.Name) and node.value.id == "self" and isinstance(node.ctx, ast.Load)]
            if any(id(node) not in deleted for node in uses):
                continue
            _, parents, _, _ = self.unit(path)
            reflection = {"__dict__", "_modules", "__getattribute__", "__getattr__", "get_submodule", "modules", "named_modules", "children", "named_children", "state_dict"}
            if (any(isinstance(node, ast.Name) and node.id == "self" and isinstance(node.ctx, ast.Load)
                    and not (isinstance(parents.get(node), ast.Attribute) and parents[node].value is node) for node in ast.walk(cls))
                    or any(isinstance(node, ast.Attribute) and node.attr in reflection and isinstance(node.value, ast.Name)
                           and node.value.id == "self" for node in ast.walk(cls))):
                # Reflection or escaped self may still need this instance.
                # Only the selected invocation is bypassed in this case.
                continue
            initializers = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
            assignments = [node for node in initializers[0].body if isinstance(node, ast.Assign) and len(node.targets) == 1
                           and isinstance(node.targets[0], ast.Attribute) and node.targets[0].attr == attribute
                           and isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == "self"] if len(initializers) == 1 else []
            if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Call):
                self.fail("A deleted module's constructor is conditional, aliased or ambiguous.", identity)
            self.patch(path, assignments[0], "pass", "remove-constructor", identity)

    def run(self):
        cache = self.draft.get("sourceCache", {})
        # Expanding an edited source region persists its live modifications in
        # the frontier cache as well. These exact visible copies are already
        # checked below; their presence must not turn a supported edit into an
        # allegedly hidden structural change. A genuinely hidden/different
        # cached edge or unrepresented canonical tombstone still blocks.
        live_edges = {edge["id"]: edge for edge in self.draft["edges"]}
        hidden_edges = any(live_edges.get(edge["id"]) != edge for edge in cache.get("edges", []))
        canonical_frontier = {}
        for edge in self.original_edges:
            for canonical in self.provenance["edgeRefs"].get(edge["id"], []):
                canonical_frontier.setdefault(canonical, []).append(edge)
        materialized_tombstones = {canonical for canonical, edges in canonical_frontier.items()
                                   if all(live_edges.get(edge["id"]) != edge for edge in edges)}
        if (hidden_edges or set(cache.get("removedNodeIds", [])) - self.deleted
                or set(cache.get("removedCanonicalEdgeIds", [])) - materialized_tombstones):
            self.fail("Hidden structural edits must be materialized before bounded source generation.")
        for identity, node in self.nodes.items():
            if identity in self.original and node["kind"] != self.original[identity]["kind"]:
                self.fail("Retained source identities cannot be reassigned to a different module kind.", identity)
        self.deletions()
        for target, edge in self.before.items():
            if target[0] in self.deleted:
                continue
            after = self.incoming.get(target)
            if not after:
                self.fail("An original source input was disconnected without a replacement.", target[0])
            baseline = self.bypass(edge["source"])
            leaf, chain = self.peel(after["source"])
            if not chain and leaf == baseline:
                continue
            for path, expression in self.targets(*target):
                base = self.edited_expression(path, expression) if leaf == baseline else self.source_value(leaf, path, expression)
                replacement = self.wrap(base, chain, path, expression)
                self.patch(path, expression, replacement, "rewrite-input", target[0])
        for target in self.incoming:
            if target[0] not in self.added and target not in self.before:
                self.fail("A new relation has no existing source input anchor.", target[0])
        if self.added != self.used:
            self.fail("Every new module must feed an anchored existing call or output; unused visual branches cannot silently disappear.")
        self.constructors()
        # Identical deletion spans can appear through several view aliases.
        unique = {}
        for patch in self.patches:
            key = patch["path"], patch["start"], patch["end"]
            if key in unique and unique[key]["replacement"] != patch["replacement"]:
                self.fail("Conflicting edits address the same source span.")
            unique[key] = patch
        self.patches = list(unique.values())
        for path in self.sources:
            previous = -1
            for patch in sorted((item for item in self.patches if item["path"] == path), key=lambda item: (item["start"], item["end"])):
                if patch["start"] < previous:
                    self.fail("Overlapping anchored edits cannot be safely composed.")
                previous = patch["end"]
        return self


def plan_surgery(draft, architecture=None, mapping=None):
    return Surgery(draft, architecture, mapping).run()


def generate_surgery(draft, validated):
    from .source_import import validate_source_draft
    from .source_preservation import _raw, generate_preserved_source
    # First reuse the independent literal-edit oracle on the pristine topology.
    # A structural edit cannot hide an unsupported parameter mutation.
    retained = {node["id"]: node for node in draft.get("sourceCache", {}).get("nodes", [])}
    retained.update({node["id"]: node for node in draft["nodes"]})
    literal = deepcopy(draft)
    literal["nodes"] = deepcopy(draft["sourceProvenance"]["originalGraph"]["nodes"])
    literal["edges"] = deepcopy(draft["sourceProvenance"]["originalGraph"]["edges"])
    literal.pop("sourceCache", None); literal.pop("customModules", None)
    for node in literal["nodes"]:
        if node["id"] in retained:
            node["parameters"] = deepcopy(retained[node["id"]]["parameters"])
            if retained[node["id"]]["kind"] != node["kind"]:
                raise DraftError("Retained source identities cannot change module kind.")
    if any(identity not in {node["id"] for node in literal["nodes"]} and identity in draft["sourceProvenance"]["nodeRefs"]
           and node["parameters"] != draft["sourceProvenance"]["nodeRefs"][identity]["originalParameters"]
           for identity, node in retained.items()):
        raise DraftError("Materialize hidden parameter edits before combining them with structural source changes.")
    copied = generate_preserved_source(literal, validate_source_draft(literal, require_complete=True))
    mapping = {**copied["nodeBindings"], **copied["containerBindings"]}
    plan = plan_surgery(draft, copied["architecture"], mapping)
    originals = {item["path"]: item for item in copied["architecture"]["sources"]}
    written = {}
    for path, item in originals.items():
        raw = _raw(item)
        for patch in sorted((item for item in plan.patches if item["path"] == path), key=lambda item: (item["start"], item["end"]), reverse=True):
            raw = raw[:patch["start"]] + patch["replacement"] + raw[patch["end"]:]
        # Parse and compile metadata, never import or run submitted models.
        text = raw.decode("utf-8-sig")
        compile(text, path, "exec", dont_inherit=True)
        written[path] = raw
    written.update(plan.files)
    if len(written) > 80 or sum(map(len, written.values())) > 2_000_000:
        raise DraftError("The edited source corpus exceeds the standard import budget.")
    with tempfile.TemporaryDirectory(prefix="archcanvas-anchored-edit-") as temporary:
        root = Path(temporary)
        for path, raw in written.items():
            target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        architecture = analyze_project(root, copied["entry"])
    actual_sources = {item["path"]: item for item in architecture["sources"]}
    if set(actual_sources) != set(written) or any(hashlib.sha256(raw).hexdigest() != actual_sources[path]["digest"] for path, raw in written.items()):
        raise DraftError("Independent analysis did not retain the exact edited corpus.")
    facts = {node["id"]: node for node in architecture["nodes"]}
    canonical_mapping = {}
    def translated_line(path, line, end=False):
        if not line or path not in plan.sources:
            return line
        _, _, lines, _ = plan.unit(path)
        raw = _raw(plan.sources[path]); bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
        offset = bom + sum(len(item.encode("utf-8")) for item in lines[:line if end else line-1])
        return line + sum(item["replacement"].count(b"\n") - raw[item["start"]:item["end"]].count(b"\n")
                          for item in plan.patches if item["path"] == path
                          and ((item["start"] < offset if end else item["start"] <= offset)
                               if item["start"] == item["end"] else item["end"] <= offset))
    def bind_retained(canonical):
        if canonical in canonical_mapping:
            return canonical_mapping[canonical]
        old = plan.facts[canonical]
        source = old.get("source", {})
        path = source.get("path")
        parent = old.get("parentId")
        if parent in plan.facts:
            parent = bind_retained(parent)
        candidates = [fact for fact in facts.values() if fact["kind"] == old["kind"]
                      and fact["label"] == old["label"] and fact.get("sourceStructure") == old.get("sourceStructure")
                      and fact.get("parentId") == parent and fact.get("instanceId") == old.get("instanceId")
                      and fact.get("source", {}).get("path") == path
                      and fact.get("source", {}).get("line") == translated_line(path, source.get("line"))
                      and fact.get("source", {}).get("endLine") == translated_line(path, source.get("endLine"), True)]
        if len(candidates) != 1:
            plan.fail(f"A retained source object lost an unambiguous independent AST-position binding ({old['kind']}, {old['label']}).", canonical)
        canonical_mapping[canonical] = candidates[0]["id"]
        return candidates[0]["id"]
    bindings, containers, operation_occurrences, retired_inspections = {}, {}, [], []
    for node in draft["nodes"]:
        identity = node["id"]
        if identity in plan.added:
            path, _ = plan.owners[identity]; attribute = plan.attributes[identity]
            matches = [fact for fact in facts.values() if fact.get("instanceId", "").endswith("." + attribute)
                       and fact.get("source", {}).get("path") == path and fact.get("callId") == fact["id"]]
            if not matches:
                # Calls inside a preserved unknown branch are inspection facts,
                # explicitly not independently lowered tensor operations.
                matches = [fact for fact in facts.values() if fact.get("sourceStructure") and fact["kind"] == "SourceModule"
                           and fact.get("source", {}).get("path") == path and fact["label"] == attribute]
            if len(matches) > 1:
                signatures = {(item.get("source", {}).get("path"), item.get("source", {}).get("line"),
                               item.get("source", {}).get("endLine"), item.get("source", {}).get("expression")) for item in matches}
                if len(signatures) != 1 or not all(item.get("sourceStructure") for item in matches):
                    plan.fail("The new operation has ambiguous source occurrences.", identity)
            if not matches:
                plan.fail("The new operation has no unique independent source/inspection binding; generation refused.", identity)
            # A region output can denote several mutually exclusive returns.
            # Keep every inspection occurrence in the receipt; use its first
            # deterministic source card as the placement anchor only.
            operation_occurrences.append({"nodeId": identity, "canonicalIds": [item["id"] for item in matches],
                                          "binding": "source-inspection" if matches[0].get("sourceStructure") else "operation"})
            canonical = matches[0]["id"]
        else:
            old = plan.fact(identity)
            if old.get("sourceStructure") and old["kind"] == "SourceCode" and old["label"] == "return":
                path = old.get("source", {}).get("path")
                try:
                    _, statement = plan.locate(old, ast.Return)
                    start, end = plan.span(path, statement)
                    rewritten = any(item["action"] == "rewrite-input" and item["path"] == path
                                    and start <= item["start"] and item["end"] <= end for item in plan.patches)
                except DraftError:
                    rewritten = False
                if rewritten and not any(identity in (edge["source"]["nodeId"], edge["target"]["nodeId"]) for edge in draft["edges"]):
                    retired_inspections.append(identity)
                    continue
            canonical = bind_retained(old["id"])
        (containers if facts[canonical].get("children") else bindings)[identity] = canonical
    all_bindings = {**bindings, **containers}
    edge_bindings = {edge["id"]: [item["id"] for item in architecture["edges"]
                                   if item["source"]["nodeId"] == all_bindings[edge["source"]["nodeId"]]
                                   and item["target"]["nodeId"] == all_bindings[edge["target"]["nodeId"]]]
                     for edge in draft["edges"]}
    module = architecture["entry"].split(":", 1)[0].replace(".", "/")
    source = next(item["content"] for item in architecture["sources"] if item["path"] in (module + ".py", module + "/__init__.py"))
    return {"draft": deepcopy(draft), "draftDigest": validated["draftDigest"], "entry": architecture["entry"],
            "source": source, "architecture": architecture, "nodeBindings": bindings, "containerBindings": containers,
            "edgeBindings": edge_bindings, "portBindings": {}, "tensors": {},
            "sourceEdits": copied.get("sourceEdits", []) + [{key: value for key, value in item.items() if key not in ("replacement", "start", "end")} for item in plan.patches],
            "verification": {"status": "passed", "scope": "source-preserved-anchored-expression-edits", "topology": "anchored-edits",
                             "modelExecution": "not_run", "sourceProvenanceDigest": draft["sourceProvenance"]["digest"],
                             "literalEdits": copied["verification"]["literalEdits"], "insertedModules": len(plan.added),
                             "deletedCalls": len(plan.deleted), "anchoredEdits": len(plan.patches),
                             "operationOccurrences": operation_occurrences,
                             "retiredInspectionBindings": retired_inspections,
                             "limitations": ["Only declared unary call arguments and explicit static return slots were rewritten; all other original source bytes are preserved.",
                                             "Calls inside unresolved branches retain source inspection bindings; these arrows are not verified tensor lowering.",
                                             "No model was imported or executed; shapes, runtime branches and numerical behavior remain unverified."]}}
