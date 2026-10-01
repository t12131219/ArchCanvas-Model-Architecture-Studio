from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

import libcst as cst
from libcst.helpers import get_full_name_for_node

from archcanvas_core.architecture_v2 import (
    SEMANTIC_GRAPH_DIGEST_DOMAIN,
    ArchitectureCall,
    CallArgumentBinding,
    CallOutputBinding,
    ConstructorArgument,
    ControlRegion,
    ModuleInstance,
    ParameterGroup,
    PythonSemanticGraph,
    SemanticDefinition,
    SemanticRepeat,
    SemanticValue,
    SourceEvidenceV2,
    semantic_graph_payload,
)
from archcanvas_core.builtin_registry import BuiltinModuleRegistry
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_core.models import Confidence, Diagnostic, RepeatKind
from archcanvas_core.module_contract import ModuleDefinition
from archcanvas_core.source_v2 import AnalysisBudget, SourceCorpus

from .cst_frontend import ParsedRepository, ParsedSourceUnit
from .pyright_client import ResolverFact, lsp_utf16_column


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.")
    return normalized if normalized and normalized[0].isalpha() else f"id-{normalized or 'unknown'}"


def _attribute_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return ".".join([current.id, *reversed(parts)])


def _relative_import(module_name: str, imported: str | None, level: int) -> str:
    if level == 0:
        return imported or ""
    package = module_name.split(".")[:-1]
    keep = max(0, len(package) - level + 1)
    prefix = ".".join(package[:keep])
    return ".".join(part for part in (prefix, imported or "") if part)


@dataclass(frozen=True)
class _ModuleIndex:
    unit: ParsedSourceUnit
    lowered_tree: ast.Module
    parents: dict[ast.AST, tuple[ast.AST, str, int | None]]
    imports: dict[str, tuple[str, ...]]
    classes: dict[str, ast.ClassDef]
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]


@dataclass
class _EvalResult:
    primary: str | None
    outputs: dict[str, str] = field(default_factory=dict)


class _RepositoryIndexVisitor(cst.CSTVisitor):
    """Collect module-visible symbols from the authoritative LibCST tree."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.imports: dict[str, set[str]] = {}
        self.class_names: set[str] = set()
        self.function_names: set[str] = set()
        self._scope_depth = 0

    def _add_import(self, local_name: str, qualified_name: str) -> None:
        self.imports.setdefault(local_name, set()).add(qualified_name)

    def visit_Import(self, node: cst.Import) -> None:
        if self._scope_depth:
            return
        for alias in node.names:
            qualified_name = get_full_name_for_node(alias.name)
            if qualified_name is None:
                continue
            local_name = (
                alias.asname.name.value
                if alias.asname is not None
                else qualified_name.split(".", 1)[0]
            )
            self._add_import(local_name, qualified_name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if self._scope_depth or isinstance(node.names, cst.ImportStar):
            return
        imported = get_full_name_for_node(node.module) if node.module is not None else None
        base = _relative_import(self.module_name, imported, len(node.relative))
        for alias in node.names:
            imported_name = get_full_name_for_node(alias.name)
            if imported_name is None:
                continue
            local_name = alias.asname.name.value if alias.asname is not None else imported_name
            qualified_name = ".".join(part for part in (base, imported_name) if part)
            self._add_import(local_name, qualified_name)

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        if self._scope_depth == 0:
            self.class_names.add(node.name.value)
        self._scope_depth += 1
        return False

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self._scope_depth -= 1

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        if self._scope_depth == 0:
            self.function_names.add(node.name.value)
        self._scope_depth += 1
        return False

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self._scope_depth -= 1


class SemanticGraphBuilder:
    def __init__(
        self,
        corpus: SourceCorpus,
        repository: ParsedRepository,
        registry: BuiltinModuleRegistry,
        entrypoint: str,
        budget: AnalysisBudget | None = None,
        resolver_budget_exceeded: bool = False,
        resolver_facts: tuple[ResolverFact, ...] = (),
    ) -> None:
        self.corpus = corpus
        self.repository = repository
        self.registry = registry
        self.entrypoint = entrypoint
        self.budget = budget or AnalysisBudget()
        self.resolver_budget_exceeded = resolver_budget_exceeded
        self.resolver_facts = {
            (
                fact.query.logical_path,
                fact.query.line,
                fact.query.column,
            ): fact
            for fact in resolver_facts
        }
        self.modules = self._index_modules()
        self.classes = {
            f"{module.unit.module_name}.{name}": (module, node)
            for module in self.modules.values()
            for name, node in module.classes.items()
        }
        self.functions = {
            f"{module.unit.module_name}.{name}": (module, node)
            for module in self.modules.values()
            for name, node in module.functions.items()
        }
        self.definitions: dict[str, SemanticDefinition] = {}
        self.instances: dict[str, ModuleInstance] = {}
        self.instance_classes: dict[str, tuple[_ModuleIndex, ast.ClassDef]] = {}
        self.instance_functions: dict[
            str,
            tuple[_ModuleIndex, ast.FunctionDef | ast.AsyncFunctionDef],
        ] = {}
        self.calls: dict[str, ArchitectureCall] = {}
        self.values: dict[str, SemanticValue] = {}
        self.control_regions: dict[str, ControlRegion] = {}
        self.parameter_groups: dict[str, ParameterGroup] = {}
        self.repeats: dict[str, SemanticRepeat] = {}
        self.evidence: dict[str, SourceEvidenceV2] = {}
        self.diagnostics: list[Diagnostic] = []
        self.collection_instances: dict[tuple[str, str], str] = {}
        self.loop_aliases: dict[tuple[str, str], ModuleInstance] = {}
        self.active_functions: set[str] = set()
        self.call_depth = 0
        self.resolver_bound_instances: set[str] = set()

    def _index_modules(self) -> dict[str, _ModuleIndex]:
        result: dict[str, _ModuleIndex] = {}
        for unit in self.repository.units.values():
            index = _RepositoryIndexVisitor(unit.module_name)
            unit.module.visit(index)

            # The evaluator currently consumes a compact stdlib-AST lowering. Symbol
            # identity, imports, anchors and scopes are all taken from the frozen CST.
            tree = ast.parse(unit.module.code, filename=unit.logical_path)
            parents = {
                child: (parent, field, child_index)
                for parent in ast.walk(tree)
                for field, value in ast.iter_fields(parent)
                for child_index, child in (
                    enumerate(value) if isinstance(value, list) else [(None, value)]
                )
                if isinstance(child, ast.AST)
            }

            def is_module_visible(
                node: ast.AST,
                index_parents: dict[ast.AST, tuple[ast.AST, str, int | None]] = parents,
            ) -> bool:
                current = node
                while current in index_parents:
                    parent = index_parents[current][0]
                    if isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        return False
                    current = parent
                return True

            classes = {
                node.name: node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                and node.name in index.class_names
                and is_module_visible(node)
            }
            functions = {
                node.name: node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in index.function_names
                and is_module_visible(node)
            }
            result[unit.module_name] = _ModuleIndex(
                unit=unit,
                lowered_tree=tree,
                parents=parents,
                imports={
                    name: tuple(sorted(candidates))
                    for name, candidates in sorted(index.imports.items())
                },
                classes=classes,
                functions=functions,
            )
        return result

    def _qualified_name_candidates(
        self,
        module: _ModuleIndex,
        expression: ast.AST,
    ) -> tuple[str, ...]:
        name = _attribute_name(expression)
        if name is None:
            return ()
        root, _, suffix = name.partition(".")
        if root in module.imports:
            candidates = [
                imported + (f".{suffix}" if suffix else "")
                for imported in module.imports[root]
            ]
            return tuple(
                sorted(
                    {
                        resolved
                        for candidate in candidates
                        for resolved in self._resolve_reexport_candidates(candidate)
                    }
                )
            )
        local = f"{module.unit.module_name}.{name}"
        if local in self.classes or local in self.functions:
            return (local,)
        return self._resolve_reexport_candidates(name)

    def _qualified_name(self, module: _ModuleIndex, expression: ast.AST) -> str | None:
        candidates = self._qualified_name_candidates(module, expression)
        return candidates[0] if len(candidates) == 1 else None

    def _find_class_method(
        self,
        module: _ModuleIndex,
        class_node: ast.ClassDef,
        names: set[str],
        seen: set[str] | None = None,
    ) -> tuple[_ModuleIndex, ast.ClassDef, ast.FunctionDef | ast.AsyncFunctionDef] | None:
        qualified_class = f"{module.unit.module_name}.{class_node.name}"
        seen = set() if seen is None else seen
        if qualified_class in seen:
            return None
        seen.add(qualified_class)
        local = next(
            (
                item
                for item in class_node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name in names
            ),
            None,
        )
        if local is not None:
            return module, class_node, local
        for base in class_node.bases:
            candidates = self._qualified_name_candidates(module, base)
            if len(candidates) != 1:
                continue
            binding = self.classes.get(candidates[0])
            if binding is None:
                continue
            inherited = self._find_class_method(binding[0], binding[1], names, seen)
            if inherited is not None:
                return inherited
        return None

    @staticmethod
    def _resolver_type_names(value: Any) -> set[str]:
        if isinstance(value, str):
            return set(re.findall(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", value))
        if isinstance(value, list):
            return {
                name
                for item in value
                for name in SemanticGraphBuilder._resolver_type_names(item)
            }
        if not isinstance(value, dict):
            return set()
        type_keys = {
            "type",
            "typeName",
            "fullName",
            "declaredType",
            "computedType",
            "returnType",
        }
        return {
            name
            for key, item in value.items()
            if key in type_keys
            for name in SemanticGraphBuilder._resolver_type_names(item)
        }

    def _resolver_definition_candidates(
        self,
        module: _ModuleIndex,
        expression: ast.AST,
    ) -> list[tuple[ModuleDefinition, ResolverFact]]:
        line = getattr(expression, "lineno", 0) - 1
        column = getattr(expression, "col_offset", 0)
        fact = self.resolver_facts.get(
            (
                module.unit.logical_path,
                line,
                lsp_utf16_column(module.unit.module.code, line, column),
            )
        )
        if fact is None:
            return []
        matches: dict[str, ModuleDefinition] = {}
        for name in sorted(self._resolver_type_names(fact.result)):
            definition = self.registry.resolve_qualified_name(name)
            if definition is not None:
                matches[definition.definition_id] = definition
        return [(matches[key], fact) for key in sorted(matches)]

    def _resolve_reexport_candidates(self, qualified_name: str) -> tuple[str, ...]:
        pending = [qualified_name]
        seen: set[str] = set()
        resolved: set[str] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if (
                self.registry.resolve_qualified_name(current) is not None
                or current in self.classes
                or current in self.functions
            ):
                resolved.add(current)
                continue
            owner = next(
                (
                    module
                    for module_name, module in sorted(
                        self.modules.items(), key=lambda item: len(item[0]), reverse=True
                    )
                    if current.startswith(f"{module_name}.")
                ),
                None,
            )
            if owner is None:
                resolved.add(current)
                continue
            symbol = current.removeprefix(f"{owner.unit.module_name}.")
            root, _, suffix = symbol.partition(".")
            targets = owner.imports.get(root)
            if targets is None:
                resolved.add(current)
                continue
            pending.extend(
                target + (f".{suffix}" if suffix else "") for target in targets
            )
        return tuple(sorted(resolved or {qualified_name}))

    @staticmethod
    def _call_identity_suffix(module: _ModuleIndex, call: ast.Call) -> str:
        current: ast.AST = call
        path: list[str] = []
        statement: ast.stmt | None = None
        while current in module.parents:
            parent, field, index = module.parents[current]
            if index is not None and field not in {"body", "orelse", "finalbody"}:
                path.append(f"{field}[{index}]")
            else:
                path.append(field)
            if isinstance(parent, ast.stmt):
                statement = parent
                break
            current = parent
        callee = _attribute_name(call.func) or ast.dump(
            call.func, annotate_fields=True, include_attributes=False
        )
        context = type(statement).__name__ if statement is not None else "Expression"
        if isinstance(statement, ast.Assign):
            targets = ",".join(
                ast.dump(item, annotate_fields=True, include_attributes=False)
                for item in statement.targets
            )
            context = f"Assign:{targets}"
        elif isinstance(statement, ast.AnnAssign):
            context = (
                "AnnAssign:"
                + ast.dump(statement.target, annotate_fields=True, include_attributes=False)
            )
        elif isinstance(statement, (ast.For, ast.AsyncFor)):
            context = (
                "For:"
                + ast.dump(statement.target, annotate_fields=True, include_attributes=False)
            )
        payload = f"{module.unit.module_name}:{context}:{'/'.join(reversed(path))}:{callee}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _definition_id(self, qualified_name: str) -> str:
        return _identifier(f"definition:local.{qualified_name}")

    def _add_evidence(
        self,
        anchor: Any,
        claim: str,
        confidence: Confidence = Confidence.EXACT,
    ) -> str:
        seed = (
            f"{self.corpus.source_corpus_digest}:{anchor.logical_path}:"
            f"{anchor.byte_start}:{anchor.byte_length}:{anchor.semantic_role}"
        )
        evidence_id = f"evidence:v2.{hashlib.sha256(seed.encode()).hexdigest()[:24]}"
        self.evidence.setdefault(
            evidence_id,
            SourceEvidenceV2(
                evidence_id=evidence_id,
                source_corpus_digest=self.corpus.source_corpus_digest,
                anchor=anchor,
                claim=claim,
                confidence=confidence,
            ),
        )
        return evidence_id

    def _ensure_local_definition(
        self,
        module: _ModuleIndex,
        class_node: ast.ClassDef,
    ) -> str:
        qualified_name = f"{module.unit.module_name}.{class_node.name}"
        definition_id = self._definition_id(qualified_name)
        if definition_id not in self.definitions:
            anchor = module.unit.source_anchor(
                class_node,
                qualified_symbol=qualified_name,
                semantic_role="module-definition",
            )
            self._add_evidence(anchor, f"Defines module class {qualified_name}.")
            self.definitions[definition_id] = SemanticDefinition(
                definition_id=definition_id,
                qualified_name=qualified_name,
                kind="class",
                anchor=anchor,
            )
        return definition_id

    def _ensure_local_function_definition(
        self,
        module: _ModuleIndex,
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str:
        qualified_name = f"{module.unit.module_name}.{function_node.name}"
        definition_id = self._definition_id(qualified_name)
        if definition_id not in self.definitions:
            anchor = module.unit.source_anchor(
                function_node,
                qualified_symbol=qualified_name,
                semantic_role="function-definition",
            )
            self._add_evidence(anchor, f"Defines local function {qualified_name}.")
            self.definitions[definition_id] = SemanticDefinition(
                definition_id=definition_id,
                qualified_name=qualified_name,
                kind="function",
                anchor=anchor,
            )
        return definition_id

    def _create_function_scope(
        self,
        module: _ModuleIndex,
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
        instance_path: str,
    ) -> str:
        instance_id = _identifier(f"instance:{instance_path}")
        definition_id = self._ensure_local_function_definition(module, function_node)
        anchor = module.unit.source_anchor(
            function_node,
            qualified_symbol=f"{module.unit.module_name}.{function_node.name}",
            semantic_role="function-scope",
        )
        self.instances[instance_id] = ModuleInstance(
            instance_id=instance_id,
            instance_path=instance_path,
            local_definition_id=definition_id,
            anchor=anchor,
        )
        self.instance_functions[instance_id] = (module, function_node)
        self._add_evidence(anchor, f"Analyzes function scope {instance_path}.")
        return instance_id

    @staticmethod
    def _literal(expression: ast.AST) -> Any:
        try:
            return ast.literal_eval(expression)
        except (ValueError, TypeError):
            return ast.unparse(expression)

    def _constructor_arguments(
        self,
        module: _ModuleIndex,
        call: ast.Call,
        definition: ModuleDefinition | None,
        qualified_symbol: str,
    ) -> list[ConstructorArgument]:
        positional_names = {
            item.positional_index: item.parameter_id
            for item in (definition.parameters if definition is not None else [])
            if item.positional_index is not None
        }
        result: list[ConstructorArgument] = []
        for index, argument in enumerate(call.args):
            anchor = module.unit.source_anchor(
                argument,
                qualified_symbol=qualified_symbol,
                semantic_role="constructor-argument",
            )
            result.append(
                ConstructorArgument(
                    parameter_name=positional_names.get(index, f"arg{index}"),
                    source_expression=ast.unparse(argument),
                    value=self._literal(argument),
                    anchor=anchor,
                )
            )
        for keyword in call.keywords:
            if keyword.arg is None:
                continue
            anchor = module.unit.source_anchor(
                keyword.value,
                qualified_symbol=qualified_symbol,
                semantic_role="constructor-argument",
            )
            result.append(
                ConstructorArgument(
                    parameter_name=keyword.arg,
                    source_expression=ast.unparse(keyword.value),
                    value=self._literal(keyword.value),
                    anchor=anchor,
                )
            )
        return result

    def _create_instance(
        self,
        *,
        module: _ModuleIndex,
        class_node: ast.ClassDef | None,
        registry_definition: ModuleDefinition | None,
        instance_path: str,
        parent_instance_id: str | None,
        anchor_node: ast.AST,
        constructor_call: ast.Call | None,
        binding_confidence: Confidence = Confidence.EXACT,
    ) -> str:
        instance_id = _identifier(f"instance:{instance_path}")
        if instance_id in self.instances:
            return instance_id
        if class_node is not None:
            local_definition_id = self._ensure_local_definition(module, class_node)
            qualified_symbol = f"{module.unit.module_name}.{class_node.name}"
        elif registry_definition is not None:
            local_definition_id = None
            qualified_symbol = registry_definition.qualified_names[0]
        else:
            raise ValueError("instance requires a local class or registry definition")
        anchor = module.unit.source_anchor(
            anchor_node,
            qualified_symbol=qualified_symbol,
            semantic_role="module-instance",
        )
        self._add_evidence(
            anchor,
            f"Constructs module instance {instance_path}.",
            binding_confidence,
        )
        arguments = (
            self._constructor_arguments(
                module,
                constructor_call,
                registry_definition,
                qualified_symbol,
            )
            if constructor_call is not None
            else []
        )
        instance = ModuleInstance(
            instance_id=instance_id,
            instance_path=instance_path,
            parent_instance_id=parent_instance_id,
            local_definition_id=local_definition_id,
            definition_ref=registry_definition.ref if registry_definition else None,
            constructor_arguments=arguments,
            anchor=anchor,
        )
        self.instances[instance_id] = instance
        if binding_confidence is Confidence.INFERRED:
            self.resolver_bound_instances.add(instance_id)
        if class_node is not None:
            self.instance_classes[instance_id] = (module, class_node)
            self._discover_children(instance, module, class_node)
        else:
            group_id = _identifier(f"parameter-group:{instance_path}")
            self.parameter_groups[group_id] = ParameterGroup(
                parameter_group_id=group_id,
                owner_instance_id=instance_id,
                member_instance_ids=[instance_id],
                anchor=anchor,
            )
        return instance_id

    @staticmethod
    def _repeat_count(expression: ast.AST) -> tuple[int | None, str | None]:
        if isinstance(expression, ast.ListComp) and len(expression.generators) == 1:
            iterator = expression.generators[0].iter
            if (
                isinstance(iterator, ast.Call)
                and _attribute_name(iterator.func) == "range"
                and len(iterator.args) == 1
            ):
                value = SemanticGraphBuilder._literal(iterator.args[0])
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value, None
                return None, ast.unparse(iterator.args[0])
        if isinstance(expression, (ast.List, ast.Tuple)) and expression.elts:
            return len(expression.elts), None
        return None, "dynamic-count"

    def _discover_collection(
        self,
        parent: ModuleInstance,
        module: _ModuleIndex,
        statement: ast.Assign | ast.AnnAssign,
        target_name: str,
        call: ast.Call,
    ) -> bool:
        candidates = self._qualified_name_candidates(module, call.func)
        qualified_name = candidates[0] if len(candidates) == 1 else None
        if qualified_name not in {
            "torch.nn.ModuleList",
            "torch.nn.modules.container.ModuleList",
            "torch.nn.Sequential",
            "torch.nn.modules.container.Sequential",
        } or not call.args:
            return False
        contents = call.args[0]
        if isinstance(contents, ast.ListComp):
            element = contents.elt
        elif isinstance(contents, (ast.List, ast.Tuple)) and contents.elts:
            element = contents.elts[0]
        else:
            anchor = module.unit.source_anchor(
                call,
                qualified_symbol=qualified_name,
                semantic_role="opaque-container",
            )
            self._add_evidence(anchor, "Module container contents could not be bounded statically.")
            self.diagnostics.append(
                Diagnostic(
                    code="V2_CONTAINER_DYNAMIC",
                    severity="warning",
                    message=f"Container {parent.instance_path}.{target_name} has dynamic contents.",
                    target_ids=[parent.instance_id],
                )
            )
            return True
        if not isinstance(element, ast.Call):
            return True
        element_candidates = self._qualified_name_candidates(module, element.func)
        if len(element_candidates) > 1:
            self._record_ambiguous_reference(
                module,
                element,
                instance=parent,
                candidates=element_candidates,
                semantic_role="ambiguous-container-element",
            )
            return True
        element_name = element_candidates[0] if element_candidates else None
        local = self.classes.get(element_name or "")
        registry_definition = self.registry.resolve_qualified_name(element_name or "")
        if local is None and registry_definition is None:
            return True
        child_module, child_class = local if local is not None else (module, None)
        instance_path = f"{parent.instance_path}.{target_name}[]"
        child_id = self._create_instance(
            module=child_module,
            class_node=child_class,
            registry_definition=registry_definition,
            instance_path=instance_path,
            parent_instance_id=parent.instance_id,
            anchor_node=element,
            constructor_call=element,
        )
        self.collection_instances[(parent.instance_id, target_name)] = child_id
        count, count_symbol = self._repeat_count(contents)
        anchor = module.unit.source_anchor(
            statement,
            qualified_symbol=f"{module.unit.module_name}.{target_name}",
            semantic_role="module-repeat",
        )
        repeat_id = _identifier(f"repeat:{parent.instance_path}.{target_name}")
        self._add_evidence(anchor, f"Constructs repeated module container {target_name}.")
        self.repeats[repeat_id] = SemanticRepeat(
            repeat_id=repeat_id,
            kind=RepeatKind.STACK,
            owner_instance_id=parent.instance_id,
            container_instance_id=child_id,
            count=count,
            count_symbol=count_symbol,
            parameter_identity="distinct-per-iteration",
            anchor=anchor,
        )
        return True

    def _discover_children(
        self,
        parent: ModuleInstance,
        module: _ModuleIndex,
        class_node: ast.ClassDef,
    ) -> None:
        initializer_binding = self._find_class_method(
            module, class_node, {"__init__"}
        )
        if initializer_binding is None:
            return
        module, _initializer_owner, initializer = initializer_binding
        for statement in ast.walk(initializer):
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            call = statement.value
            if not isinstance(call, ast.Call):
                continue
            target_name = next(
                (
                    target.attr
                    for target in targets
                    if isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ),
                None,
            )
            if target_name is None:
                continue
            candidates = self._qualified_name_candidates(module, call.func)
            if len(candidates) > 1:
                self._record_ambiguous_reference(
                    module,
                    call,
                    instance=parent,
                    candidates=candidates,
                    semantic_role="ambiguous-constructor",
                )
                continue
            qualified_name = candidates[0] if candidates else None
            if self._discover_collection(
                parent, module, statement, target_name, call
            ):
                continue
            local = self.classes.get(qualified_name or "")
            registry_definition = self.registry.resolve_qualified_name(qualified_name or "")
            resolver_fact: ResolverFact | None = None
            if local is None and registry_definition is None:
                resolver_candidates = self._resolver_definition_candidates(
                    module, call.func
                )
                if len(resolver_candidates) == 1:
                    registry_definition, resolver_fact = resolver_candidates[0]
                elif len(resolver_candidates) > 1:
                    self._record_ambiguous_reference(
                        module,
                        call,
                        instance=parent,
                        candidates=tuple(
                            item.qualified_names[0]
                            for item, _fact in resolver_candidates
                        ),
                        semantic_role="ambiguous-resolver-constructor",
                    )
                    continue
            if local is None and registry_definition is None:
                anchor = module.unit.source_anchor(
                    call,
                    qualified_symbol=qualified_name or ast.unparse(call.func),
                    semantic_role="opaque-constructor",
                )
                self._add_evidence(anchor, "Constructor target could not be bound exactly.")
                self.diagnostics.append(
                    Diagnostic(
                        code="V2_CONSTRUCTOR_UNRESOLVED",
                        severity="warning",
                        message=f"Unresolved constructor: {qualified_name or ast.unparse(call.func)}",
                        target_ids=[parent.instance_id],
                    )
                )
                continue
            child_module, child_class = local if local is not None else (module, None)
            child_id = self._create_instance(
                module=child_module,
                class_node=child_class,
                registry_definition=registry_definition,
                instance_path=f"{parent.instance_path}.{target_name}",
                parent_instance_id=parent.instance_id,
                anchor_node=statement,
                constructor_call=call,
                binding_confidence=(
                    Confidence.INFERRED
                    if resolver_fact is not None
                    else Confidence.EXACT
                ),
            )
            if resolver_fact is not None and registry_definition is not None:
                resolver_anchor = module.unit.source_anchor(
                    call.func,
                    qualified_symbol=registry_definition.qualified_names[0],
                    semantic_role="resolver-type-binding",
                )
                self._add_evidence(
                    resolver_anchor,
                    "Pyright snapshot "
                    f"{resolver_fact.snapshot} resolved {ast.unparse(call.func)} to "
                    f"{registry_definition.qualified_names[0]}.",
                    Confidence.INFERRED,
                )
                self.resolver_bound_instances.add(child_id)

    def _child_instance(self, parent: ModuleInstance, attribute: str) -> ModuleInstance | None:
        path = f"{parent.instance_path}.{attribute}"
        return next((item for item in self.instances.values() if item.instance_path == path), None)

    def _instance_for_parameter_attribute(
        self,
        owner: ModuleInstance,
        expression: ast.AST,
    ) -> tuple[ModuleInstance, str] | None:
        name = _attribute_name(expression)
        if name is None or not name.startswith("self.") or name.count(".") < 2:
            return None
        relative, attribute = name.removeprefix("self.").rsplit(".", 1)
        path = f"{owner.instance_path}.{relative}"
        instance = next(
            (item for item in self.instances.values() if item.instance_path == path),
            None,
        )
        return (instance, attribute) if instance is not None else None

    def _discover_parameter_aliases(self) -> None:
        for owner_id, (module, class_node) in self.instance_classes.items():
            owner = self.instances[owner_id]
            initializer_binding = self._find_class_method(
                module, class_node, {"__init__"}
            )
            if initializer_binding is None:
                continue
            module, _initializer_owner, initializer = initializer_binding
            for statement in ast.walk(initializer):
                if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                    continue
                target = self._instance_for_parameter_attribute(owner, statement.targets[0])
                source = self._instance_for_parameter_attribute(owner, statement.value)
                if target is None or source is None or target[1] != source[1]:
                    continue
                target_instance, attribute = target
                source_instance, _ = source
                if target_instance.instance_id == source_instance.instance_id:
                    continue
                target_group = next(
                    (
                        item
                        for item in self.parameter_groups.values()
                        if target_instance.instance_id in item.member_instance_ids
                    ),
                    None,
                )
                source_group = next(
                    (
                        item
                        for item in self.parameter_groups.values()
                        if source_instance.instance_id in item.member_instance_ids
                    ),
                    None,
                )
                if target_group is None or source_group is None:
                    continue
                anchor = module.unit.source_anchor(
                    statement,
                    qualified_symbol=f"{module.unit.module_name}.{class_node.name}.__init__",
                    semantic_role="parameter-sharing",
                )
                self._add_evidence(
                    anchor,
                    f"Ties parameter {attribute} across {target_instance.instance_path} and "
                    f"{source_instance.instance_path}.",
                )
                if target_group.parameter_group_id == source_group.parameter_group_id:
                    continue
                members = sorted(
                    set(target_group.member_instance_ids)
                    | set(source_group.member_instance_ids)
                )
                calls = sorted(set(target_group.call_ids) | set(source_group.call_ids))
                merged = source_group.model_copy(
                    update={
                        "member_instance_ids": members,
                        "call_ids": calls,
                        "binding_kind": "tied",
                        "shared_attribute": attribute,
                        "anchor": anchor,
                    }
                )
                self.parameter_groups[source_group.parameter_group_id] = merged
                self.parameter_groups.pop(target_group.parameter_group_id, None)

    def _new_value(
        self,
        value_id: str,
        semantic_name: str,
        anchor: Any,
        *,
        producer_call_id: str | None = None,
        producer_port_id: str | None = None,
    ) -> str:
        normalized = _identifier(value_id)
        self.values.setdefault(
            normalized,
            SemanticValue(
                value_id=normalized,
                semantic_name=semantic_name,
                producer_call_id=producer_call_id,
                producer_port_id=producer_port_id,
                anchor=anchor,
            ),
        )
        return normalized

    def _record_ambiguous_reference(
        self,
        module: _ModuleIndex,
        node: ast.AST,
        *,
        instance: ModuleInstance,
        candidates: tuple[str, ...],
        semantic_role: str,
    ) -> str:
        display = " | ".join(candidates)
        anchor = module.unit.source_anchor(
            node,
            qualified_symbol=display,
            semantic_role=semantic_role,
        )
        evidence_id = self._add_evidence(
            anchor,
            f"Static resolution retained multiple candidates: {display}.",
        )
        self.diagnostics.append(
            Diagnostic(
                code="V2_CALL_AMBIGUOUS",
                severity="warning",
                message=f"Ambiguous static target: {display}",
                target_ids=[instance.instance_id, evidence_id],
            )
        )
        return evidence_id

    def _record_opaque_call(
        self,
        module: _ModuleIndex,
        call: ast.Call,
        parent_instance: ModuleInstance,
        environment: dict[str, str],
        control_region_id: str,
        *,
        diagnostic_code: str,
        reason: str,
        qualified_symbol: str,
    ) -> _EvalResult:
        anchor = module.unit.source_anchor(
            call,
            qualified_symbol=qualified_symbol,
            semantic_role="opaque-call",
        )
        identity_suffix = self._call_identity_suffix(module, call)
        definition_id = _identifier(
            f"definition:opaque.{diagnostic_code}.{qualified_symbol}.{identity_suffix}"
        )
        self.definitions.setdefault(
            definition_id,
            SemanticDefinition(
                definition_id=definition_id,
                qualified_name=qualified_symbol,
                kind="function",
                anchor=anchor,
            ),
        )
        opaque_region_id = _identifier(f"control:opaque.{definition_id}.{identity_suffix}")
        self.control_regions.setdefault(
            opaque_region_id,
            ControlRegion(
                control_region_id=opaque_region_id,
                kind="opaque",
                owner_definition_id=definition_id,
                parent_region_id=control_region_id,
                anchor=anchor,
            ),
        )
        inputs: list[CallArgumentBinding] = []
        expressions: list[tuple[str, str, ast.AST]] = [
            (f"input{index}", "positional", argument)
            for index, argument in enumerate(call.args)
        ]
        expressions.extend(
            (keyword.arg or f"keyword{index}", "keyword", keyword.value)
            for index, keyword in enumerate(call.keywords)
        )
        for argument_name, argument_kind, expression in expressions:
            evaluated = self._evaluate_expression(
                module,
                expression,
                parent_instance,
                environment,
                control_region_id,
            )
            if evaluated.primary is None:
                continue
            inputs.append(
                CallArgumentBinding(
                    port_id=_identifier(argument_name),
                    value_id=evaluated.primary,
                    argument_name=argument_name,
                    argument_kind=argument_kind,
                    ordinal=len(inputs),
                    anchor=module.unit.source_anchor(
                        expression,
                        qualified_symbol=qualified_symbol,
                        semantic_role=f"opaque-input:{argument_name}",
                    ),
                )
            )
        call_id = _identifier(
            f"call:opaque.{parent_instance.instance_path}.{identity_suffix}"
        )
        output_id = self._new_value(
            f"value:{call_id}.output",
            "opaque-output",
            anchor,
            producer_call_id=call_id,
            producer_port_id="output",
        )
        self.calls[call_id] = ArchitectureCall(
            call_id=call_id,
            local_definition_id=definition_id,
            parent_module_id=parent_instance.instance_id,
            input_bindings=inputs,
            output_bindings=[
                CallOutputBinding(port_id="output", value_id=output_id, ordinal=0)
            ],
            control_region_id=opaque_region_id,
            anchor=anchor,
            confidence=Confidence.UNRESOLVED,
        )
        evidence_id = self._add_evidence(anchor, reason)
        self.diagnostics.append(
            Diagnostic(
                code=diagnostic_code,
                severity="warning",
                message=reason,
                target_ids=[call_id, evidence_id],
            )
        )
        return _EvalResult(primary=output_id, outputs={"output": output_id})

    def _record_analysis_budget_boundary(
        self,
        module: _ModuleIndex,
        anchor_node: ast.AST,
        root_instance: ModuleInstance,
        *,
        budget_kind: str,
        detail: str,
    ) -> None:
        qualified_symbol = f"analysis-budget:{budget_kind}"
        anchor = module.unit.source_anchor(
            anchor_node,
            qualified_symbol=qualified_symbol,
            semantic_role="opaque-analysis-budget",
        )
        definition_id = _identifier(f"definition:opaque.analysis-budget.{budget_kind}")
        self.definitions.setdefault(
            definition_id,
            SemanticDefinition(
                definition_id=definition_id,
                qualified_name=qualified_symbol,
                kind="function",
                anchor=anchor,
            ),
        )
        call_id = _identifier(
            f"call:opaque.analysis-budget.{root_instance.instance_path}.{budget_kind}"
        )
        region_id = _identifier(f"control:opaque.analysis-budget.{budget_kind}")
        parent_region_id = next(iter(sorted(self.control_regions)), None)
        self.control_regions[region_id] = ControlRegion(
            control_region_id=region_id,
            kind="opaque",
            owner_definition_id=definition_id,
            parent_region_id=parent_region_id,
            anchor=anchor,
        )
        input_values = sorted(
            (
                value
                for value in self.values.values()
                if value.producer_call_id is None
            ),
            key=lambda value: value.value_id,
        )
        input_bindings = [
            CallArgumentBinding(
                port_id=_identifier(value.semantic_name),
                value_id=value.value_id,
                argument_name=value.semantic_name,
                argument_kind="implicit",
                ordinal=index,
                anchor=value.anchor,
            )
            for index, value in enumerate(input_values)
        ]
        output_id = self._new_value(
            f"value:{call_id}.output",
            "opaque-output",
            anchor,
            producer_call_id=call_id,
            producer_port_id="output",
        )
        self.calls[call_id] = ArchitectureCall(
            call_id=call_id,
            local_definition_id=definition_id,
            parent_module_id=root_instance.instance_id,
            input_bindings=input_bindings,
            output_bindings=[
                CallOutputBinding(port_id="output", value_id=output_id, ordinal=0)
            ],
            control_region_id=region_id,
            anchor=anchor,
            confidence=Confidence.UNRESOLVED,
        )
        evidence_id = self._add_evidence(anchor, detail)
        self.diagnostics.append(
            Diagnostic(
                code="ANALYSIS_BUDGET_EXCEEDED",
                severity="warning",
                message=detail,
                target_ids=[call_id, evidence_id],
            )
        )

    def _call_arguments(
        self,
        module: _ModuleIndex,
        call: ast.Call,
        definition: ModuleDefinition,
        instance: ModuleInstance,
        environment: dict[str, str],
        control_region_id: str,
    ) -> list[CallArgumentBinding]:
        input_ports = [item for item in definition.ports if item.direction == "input"]
        aliases = {"attn_mask": "attention_mask", "key_padding_mask": "key_padding_mask"}
        bindings: list[CallArgumentBinding] = []
        for ordinal, argument in enumerate(call.args):
            if ordinal >= len(input_ports):
                break
            evaluated = self._evaluate_expression(
                module, argument, instance, environment, control_region_id
            )
            if evaluated.primary is None:
                continue
            port_id = input_ports[ordinal].port_id
            anchor = module.unit.source_anchor(
                argument,
                qualified_symbol=definition.qualified_names[0],
                semantic_role=f"call-input:{port_id}",
            )
            bindings.append(
                CallArgumentBinding(
                    port_id=port_id,
                    value_id=evaluated.primary,
                    argument_name=port_id,
                    argument_kind="positional",
                    ordinal=ordinal,
                    anchor=anchor,
                )
            )
        for keyword in call.keywords:
            if keyword.arg is None:
                continue
            port_id = aliases.get(keyword.arg, keyword.arg)
            if not any(item.port_id == port_id for item in input_ports):
                continue
            evaluated = self._evaluate_expression(
                module, keyword.value, instance, environment, control_region_id
            )
            if evaluated.primary is None:
                continue
            anchor = module.unit.source_anchor(
                keyword.value,
                qualified_symbol=definition.qualified_names[0],
                semantic_role=f"call-input:{port_id}",
            )
            bindings.append(
                CallArgumentBinding(
                    port_id=port_id,
                    value_id=evaluated.primary,
                    argument_name=keyword.arg,
                    argument_kind="keyword",
                    ordinal=len(bindings),
                    anchor=anchor,
                )
            )
        port_order = {port.port_id: index for index, port in enumerate(input_ports)}
        ordered = sorted(
            bindings,
            key=lambda item: (port_order[item.port_id], item.argument_kind, item.argument_name),
        )
        return [item.model_copy(update={"ordinal": index}) for index, item in enumerate(ordered)]

    @staticmethod
    def _bind_assignment_target(
        target: ast.AST,
        output_values: Any,
        environment: dict[str, str],
    ) -> None:
        if isinstance(target, ast.Name):
            value = next(output_values, None)
            if value is not None:
                environment[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                SemanticGraphBuilder._bind_assignment_target(
                    element,
                    output_values,
                    environment,
                )

    def _local_function_arguments(
        self,
        module: _ModuleIndex,
        call: ast.Call,
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
        instance: ModuleInstance,
        environment: dict[str, str],
        control_region_id: str,
    ) -> tuple[list[CallArgumentBinding], dict[str, str]]:
        parameters = [
            *function_node.args.posonlyargs,
            *function_node.args.args,
            *function_node.args.kwonlyargs,
        ]
        parameters = [item for item in parameters if item.arg not in {"self", "cls"}]
        supplied: dict[str, str] = {}
        bindings: list[CallArgumentBinding] = []
        for ordinal, argument in enumerate(call.args):
            if ordinal >= len(parameters):
                break
            evaluated = self._evaluate_expression(
                module,
                argument,
                instance,
                environment,
                control_region_id,
            )
            if evaluated.primary is None:
                continue
            parameter_name = parameters[ordinal].arg
            supplied[parameter_name] = evaluated.primary
            bindings.append(
                CallArgumentBinding(
                    port_id=_identifier(parameter_name),
                    value_id=evaluated.primary,
                    argument_name=parameter_name,
                    argument_kind="positional",
                    ordinal=ordinal,
                    anchor=module.unit.source_anchor(
                        argument,
                        qualified_symbol=function_node.name,
                        semantic_role=f"call-input:{parameter_name}",
                    ),
                )
            )
        parameter_order = {item.arg: index for index, item in enumerate(parameters)}
        for keyword in call.keywords:
            if keyword.arg is None or keyword.arg not in parameter_order:
                continue
            evaluated = self._evaluate_expression(
                module,
                keyword.value,
                instance,
                environment,
                control_region_id,
            )
            if evaluated.primary is None:
                continue
            supplied[keyword.arg] = evaluated.primary
            bindings.append(
                CallArgumentBinding(
                    port_id=_identifier(keyword.arg),
                    value_id=evaluated.primary,
                    argument_name=keyword.arg,
                    argument_kind="keyword",
                    ordinal=parameter_order[keyword.arg],
                    anchor=module.unit.source_anchor(
                        keyword.value,
                        qualified_symbol=function_node.name,
                        semantic_role=f"call-input:{keyword.arg}",
                    ),
                )
            )
        bindings.sort(key=lambda item: (parameter_order[item.argument_name], item.argument_kind))
        return (
            [item.model_copy(update={"ordinal": index}) for index, item in enumerate(bindings)],
            supplied,
        )

    def _record_local_function_call(
        self,
        caller_module: _ModuleIndex,
        call: ast.Call,
        parent_instance: ModuleInstance,
        function_module: _ModuleIndex,
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
        environment: dict[str, str],
        control_region_id: str,
    ) -> _EvalResult:
        qualified_name = f"{function_module.unit.module_name}.{function_node.name}"
        definition_id = self._ensure_local_function_definition(function_module, function_node)
        anchor = caller_module.unit.source_anchor(
            call,
            qualified_symbol=qualified_name,
            semantic_role="function-call",
        )
        call_id = _identifier(
            f"call:{parent_instance.instance_path}.{qualified_name}."
            f"{self._call_identity_suffix(caller_module, call)}"
        )
        bindings, supplied = self._local_function_arguments(
            caller_module,
            call,
            function_node,
            parent_instance,
            environment,
            control_region_id,
        )
        if self.call_depth >= self.budget.max_call_depth:
            return self._record_opaque_call(
                caller_module,
                call,
                parent_instance,
                environment,
                control_region_id,
                diagnostic_code="ANALYSIS_BUDGET_EXCEEDED",
                reason=(
                    "Call expansion stopped at the configured call-depth budget "
                    f"({self.budget.max_call_depth}): {qualified_name}"
                ),
                qualified_symbol=qualified_name,
            )
        self.call_depth += 1
        try:
            result = self._analyze_function_body(
                parent_instance,
                function_module,
                function_node,
                supplied,
                invocation_key=call_id,
                owner_definition_id=definition_id,
            )
        finally:
            self.call_depth -= 1
        result_values = list(result.outputs.values()) or (
            [result.primary] if result.primary is not None else []
        )
        outputs = [
            CallOutputBinding(
                port_id="output" if len(result_values) == 1 else f"output{index}",
                value_id=value_id,
                ordinal=index,
            )
            for index, value_id in enumerate(result_values)
        ]
        self.calls[call_id] = ArchitectureCall(
            call_id=call_id,
            local_definition_id=definition_id,
            parent_module_id=parent_instance.instance_id,
            input_bindings=bindings,
            output_bindings=outputs,
            control_region_id=control_region_id,
            anchor=anchor,
            confidence=Confidence.EXACT,
        )
        self._add_evidence(anchor, f"Calls local function {qualified_name}.")
        return _EvalResult(
            primary=result_values[0] if result_values else None,
            outputs={item.port_id: item.value_id for item in outputs},
        )

    def _evaluate_expression(
        self,
        module: _ModuleIndex,
        expression: ast.AST,
        instance: ModuleInstance,
        environment: dict[str, str],
        control_region_id: str,
    ) -> _EvalResult:
        if isinstance(expression, ast.Name):
            return _EvalResult(primary=environment.get(expression.id))
        if isinstance(expression, (ast.Tuple, ast.List)):
            values = [
                result.primary
                for item in expression.elts
                if (result := self._evaluate_expression(
                    module,
                    item,
                    instance,
                    environment,
                    control_region_id,
                )).primary
                is not None
            ]
            return _EvalResult(
                primary=values[0] if values else None,
                outputs={f"output{index}": value for index, value in enumerate(values)},
            )
        if isinstance(expression, ast.Call):
            callee = _attribute_name(expression.func)
            child = None
            if callee and callee.startswith("self.") and callee.count(".") == 1:
                child = self._child_instance(instance, callee.split(".", 1)[1])
            if child is None:
                child = self.loop_aliases.get((control_region_id, callee or ""))
            if child is None:
                candidates = self._qualified_name_candidates(module, expression.func)
                if len(candidates) > 1:
                    return self._record_opaque_call(
                        module,
                        expression,
                        instance,
                        environment,
                        control_region_id,
                        diagnostic_code="V2_CALL_AMBIGUOUS",
                        reason=(
                            "Conditional or competing imports left multiple static call "
                            f"targets: {' | '.join(candidates)}"
                        ),
                        qualified_symbol="ambiguous:" + "|".join(candidates),
                    )
                qualified_name = candidates[0] if candidates else None
                local_function = self.functions.get(qualified_name or "")
                if local_function is not None:
                    return self._record_local_function_call(
                        module,
                        expression,
                        instance,
                        local_function[0],
                        local_function[1],
                        environment,
                        control_region_id,
                    )
                definition = self.registry.resolve_qualified_name(qualified_name or "")
                if definition is None:
                    unresolved = qualified_name or ast.unparse(expression.func)
                    return self._record_opaque_call(
                        module,
                        expression,
                        instance,
                        environment,
                        control_region_id,
                        diagnostic_code="V2_CALL_UNRESOLVED",
                        reason=f"Unresolved call retained as an opaque boundary: {unresolved}",
                        qualified_symbol=unresolved,
                    )
                return self._record_registry_call(
                    module,
                    expression,
                    instance,
                    None,
                    definition,
                    environment,
                    control_region_id,
                )
            if child.definition_ref is not None:
                definition = self.registry.resolve_ref(
                    child.definition_ref.definition_id,
                    child.definition_ref.version,
                    child.definition_ref.digest,
                )
                if definition is None:
                    return _EvalResult(primary=None)
                return self._record_registry_call(
                    module,
                    expression,
                    instance,
                    child,
                    definition,
                    environment,
                    control_region_id,
                )
            if self.call_depth >= self.budget.max_call_depth:
                return self._record_opaque_call(
                    module,
                    expression,
                    instance,
                    environment,
                    control_region_id,
                    diagnostic_code="ANALYSIS_BUDGET_EXCEEDED",
                    reason=(
                        "Composite expansion stopped at the configured call-depth budget "
                        f"({self.budget.max_call_depth}): {child.instance_path}"
                    ),
                    qualified_symbol=child.instance_path,
                )
            input_values = [
                result.primary
                for argument in expression.args
                if (result := self._evaluate_expression(
                    module, argument, instance, environment, control_region_id
                )).primary
                is not None
            ]
            self.call_depth += 1
            try:
                nested_result = self._analyze_forward(child, input_values)
            finally:
                self.call_depth -= 1
            anchor = module.unit.source_anchor(
                expression,
                qualified_symbol=callee or child.instance_path,
                semantic_role="module-call",
            )
            call_id = _identifier(
                f"call:{instance.instance_path}.{self._call_identity_suffix(module, expression)}"
            )
            bindings = [
                CallArgumentBinding(
                    port_id=f"input{index}",
                    value_id=value_id,
                    argument_name=f"input{index}",
                    argument_kind="positional",
                    ordinal=index,
                    anchor=anchor,
                )
                for index, value_id in enumerate(input_values)
            ]
            outputs = (
                [CallOutputBinding(port_id="output", value_id=nested_result, ordinal=0)]
                if nested_result
                else []
            )
            self.calls[call_id] = ArchitectureCall(
                call_id=call_id,
                instance_id=child.instance_id,
                local_definition_id=child.local_definition_id,
                parent_module_id=instance.instance_id,
                input_bindings=bindings,
                output_bindings=outputs,
                control_region_id=control_region_id,
                anchor=anchor,
                confidence=Confidence.EXACT,
            )
            self._add_evidence(anchor, f"Calls composite module {child.instance_path}.")
            return _EvalResult(primary=nested_result)
        if isinstance(expression, ast.Attribute):
            return _EvalResult(primary=environment.get(ast.unparse(expression)))
        return _EvalResult(primary=None)

    def _record_registry_call(
        self,
        module: _ModuleIndex,
        call: ast.Call,
        parent_instance: ModuleInstance,
        called_instance: ModuleInstance | None,
        definition: ModuleDefinition,
        environment: dict[str, str],
        control_region_id: str,
    ) -> _EvalResult:
        anchor = module.unit.source_anchor(
            call,
            qualified_symbol=definition.qualified_names[0],
            semantic_role="module-call",
        )
        identity = called_instance.instance_path if called_instance else definition.definition_id
        call_id = _identifier(
            f"call:{identity}.{self._call_identity_suffix(module, call)}"
        )
        bindings = self._call_arguments(
            module,
            call,
            definition,
            parent_instance,
            environment,
            control_region_id,
        )
        outputs: dict[str, str] = {}
        output_bindings: list[CallOutputBinding] = []
        for ordinal, port in enumerate(item for item in definition.ports if item.direction == "output"):
            value_id = self._new_value(
                f"value:{call_id.removeprefix('call:')}.{port.port_id}",
                port.port_id,
                anchor,
                producer_call_id=call_id,
                producer_port_id=port.port_id,
            )
            outputs[port.port_id] = value_id
            output_bindings.append(
                CallOutputBinding(port_id=port.port_id, value_id=value_id, ordinal=ordinal)
            )
        self.calls[call_id] = ArchitectureCall(
            call_id=call_id,
            instance_id=called_instance.instance_id if called_instance else None,
            definition_ref=definition.ref,
            parent_module_id=parent_instance.instance_id,
            input_bindings=bindings,
            output_bindings=output_bindings,
            control_region_id=control_region_id,
            anchor=anchor,
            confidence=(
                Confidence.INFERRED
                if called_instance is not None
                and called_instance.instance_id in self.resolver_bound_instances
                else Confidence.EXACT
            ),
        )
        self._add_evidence(
            anchor,
            f"Calls registered module {definition.definition_id}.",
            (
                Confidence.INFERRED
                if called_instance is not None
                and called_instance.instance_id in self.resolver_bound_instances
                else Confidence.EXACT
            ),
        )
        if called_instance is not None:
            group = next(
                (
                    item
                    for item in self.parameter_groups.values()
                    if called_instance.instance_id in item.member_instance_ids
                ),
                None,
            )
            if group is not None and call_id not in group.call_ids:
                self.parameter_groups[group.parameter_group_id] = group.model_copy(
                    update={"call_ids": [*group.call_ids, call_id]}
                )
        primary = next(iter(outputs.values()), None)
        return _EvalResult(primary=primary, outputs=outputs)

    def _analyze_function_body(
        self,
        instance: ModuleInstance,
        module: _ModuleIndex,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        supplied_inputs: dict[str, str] | None = None,
        *,
        invocation_key: str,
        owner_definition_id: str,
        qualified_symbol: str | None = None,
    ) -> _EvalResult:
        qualified_symbol = qualified_symbol or f"{module.unit.module_name}.{function.name}"
        control_region_id = _identifier(f"control:{invocation_key}.{function.name}")
        if control_region_id in self.active_functions:
            anchor = module.unit.source_anchor(
                function,
                qualified_symbol=qualified_symbol,
                semantic_role="opaque-recursion",
            )
            self._add_evidence(anchor, f"Recursive function boundary at {qualified_symbol}.")
            self.diagnostics.append(
                Diagnostic(
                    code="V2_RECURSIVE_CALL_OPAQUE",
                    severity="warning",
                    message=f"Recursive function call was not expanded: {qualified_symbol}",
                    target_ids=[instance.instance_id],
                )
            )
            return _EvalResult(primary=None)
        anchor = module.unit.source_anchor(
            function,
            qualified_symbol=qualified_symbol,
            semantic_role="control-region",
        )
        self.control_regions.setdefault(
            control_region_id,
            ControlRegion(
                control_region_id=control_region_id,
                kind="function",
                owner_definition_id=owner_definition_id,
                anchor=anchor,
            ),
        )
        environment: dict[str, str] = {}
        arguments = [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
        arguments = [item for item in arguments if item.arg not in {"self", "cls"}]
        for argument in arguments:
            if supplied_inputs and argument.arg in supplied_inputs:
                environment[argument.arg] = supplied_inputs[argument.arg]
                continue
            value_anchor = module.unit.source_anchor(
                function,
                qualified_symbol=qualified_symbol,
                semantic_role=f"function-input:{argument.arg}",
            )
            environment[argument.arg] = self._new_value(
                f"value:{control_region_id}.{argument.arg}",
                argument.arg,
                value_anchor,
            )
        result = _EvalResult(primary=None)

        def process(statements: list[ast.stmt], region_id: str) -> None:
            nonlocal result
            for statement in statements:
                if isinstance(statement, ast.Assign):
                    evaluated = self._evaluate_expression(
                        module, statement.value, instance, environment, region_id
                    )
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and evaluated.primary:
                            environment[target.id] = evaluated.primary
                        elif isinstance(target, (ast.Tuple, ast.List)):
                            self._bind_assignment_target(
                                target, iter(evaluated.outputs.values()), environment
                            )
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                    evaluated = self._evaluate_expression(
                        module, statement.value, instance, environment, region_id
                    )
                    if isinstance(statement.target, ast.Name) and evaluated.primary:
                        environment[statement.target.id] = evaluated.primary
                elif isinstance(statement, ast.Expr):
                    self._evaluate_expression(
                        module, statement.value, instance, environment, region_id
                    )
                elif isinstance(statement, ast.Return) and statement.value is not None:
                    result = self._evaluate_expression(
                        module, statement.value, instance, environment, region_id
                    )
                elif isinstance(statement, ast.For):
                    iterator = _attribute_name(statement.iter)
                    target = statement.target.id if isinstance(statement.target, ast.Name) else None
                    if not iterator or not iterator.startswith("self.") or target is None:
                        continue
                    collection_name = iterator.split(".", 1)[1]
                    child_id = self.collection_instances.get(
                        (instance.instance_id, collection_name)
                    )
                    if child_id is None:
                        continue
                    loop_anchor = module.unit.source_anchor(
                        statement,
                        qualified_symbol=qualified_symbol,
                        semantic_role="repeat-loop",
                    )
                    loop_region_id = _identifier(
                        f"{region_id}.{collection_name}.loop"
                    )
                    self.control_regions[loop_region_id] = ControlRegion(
                        control_region_id=loop_region_id,
                        kind="loop",
                        owner_definition_id=owner_definition_id,
                        parent_region_id=region_id,
                        anchor=loop_anchor,
                    )
                    self._add_evidence(loop_anchor, f"Iterates module container {collection_name}.")
                    before = set(self.calls)
                    self.loop_aliases[(loop_region_id, target)] = self.instances[child_id]
                    process(statement.body, loop_region_id)
                    self.loop_aliases.pop((loop_region_id, target), None)
                    body_calls = sorted(set(self.calls) - before)
                    repeat_id = _identifier(
                        f"repeat:{instance.instance_path}.{collection_name}"
                    )
                    repeat = self.repeats.get(repeat_id)
                    if repeat is not None:
                        self.repeats[repeat_id] = repeat.model_copy(
                            update={"body_call_ids": body_calls}
                        )

        self.active_functions.add(control_region_id)
        try:
            process(function.body, control_region_id)
        finally:
            self.active_functions.remove(control_region_id)
        return result

    def _analyze_forward(
        self,
        instance: ModuleInstance,
        supplied_inputs: list[str] | None = None,
    ) -> str | None:
        class_binding = self.instance_classes.get(instance.instance_id)
        if class_binding is None:
            return None
        module, class_node = class_binding
        forward_binding = self._find_class_method(
            module, class_node, {"forward", "call", "__call__"}
        )
        if forward_binding is None:
            return None
        module, forward_owner, forward = forward_binding
        arguments = [
            item
            for item in [*forward.args.posonlyargs, *forward.args.args, *forward.args.kwonlyargs]
            if item.arg not in {"self", "cls"}
        ]
        supplied = {
            argument.arg: supplied_inputs[index]
            for index, argument in enumerate(arguments)
            if supplied_inputs and index < len(supplied_inputs)
        }
        result = self._analyze_function_body(
            instance,
            module,
            forward,
            supplied,
            invocation_key=f"{instance.instance_path}.{forward.name}",
            owner_definition_id=instance.local_definition_id or "definition:unknown",
            qualified_symbol=f"{module.unit.module_name}.{forward_owner.name}.{forward.name}",
        )
        return result.primary

    def build(self) -> PythonSemanticGraph:
        if ":" not in self.entrypoint:
            raise ValueError("v2 entrypoint must use module:Symbol syntax")
        module_name, symbol_name = self.entrypoint.split(":", 1)
        module = self.modules.get(module_name)
        class_node = module.classes.get(symbol_name) if module else None
        function_node = module.functions.get(symbol_name) if module else None
        if module is None or (class_node is None and function_node is None):
            raise ValueError(f"v2 entrypoint cannot be resolved: {self.entrypoint}")
        root_path = _identifier(symbol_name).removeprefix("id-")
        if class_node is not None:
            root_id = self._create_instance(
                module=module,
                class_node=class_node,
                registry_definition=None,
                instance_path=root_path,
                parent_instance_id=None,
                anchor_node=class_node,
                constructor_call=None,
            )
            self._discover_parameter_aliases()
            self._analyze_forward(self.instances[root_id])
        else:
            assert function_node is not None
            root_id = self._create_function_scope(module, function_node, root_path)
            self._analyze_function_body(
                self.instances[root_id],
                module,
                function_node,
                invocation_key=f"{root_path}.entrypoint",
                owner_definition_id=self.instances[root_id].local_definition_id
                or "definition:unknown",
            )

        budget_exclusions = [
            item.logical_path
            for item in self.corpus.excluded
            if item.reason in {"budget-exhausted", "file-too-large"}
        ]
        if budget_exclusions:
            self._record_analysis_budget_boundary(
                module,
                class_node or function_node,
                self.instances[root_id],
                budget_kind="source-capture",
                detail=(
                    "Source capture exceeded the configured file/byte budget; retained "
                    "an opaque boundary for: " + ", ".join(sorted(budget_exclusions))
                ),
            )
        if self.resolver_budget_exceeded:
            self._record_analysis_budget_boundary(
                module,
                class_node or function_node,
                self.instances[root_id],
                budget_kind="resolver-query",
                detail=(
                    "Resolver query count exceeded the configured budget; local LibCST "
                    "analysis continued with an opaque resolver boundary."
                ),
            )

        consumers: dict[str, list[str]] = {}
        for call in self.calls.values():
            for binding in call.input_bindings:
                consumers.setdefault(binding.value_id, []).append(call.call_id)
        for value_id, value in list(self.values.items()):
            self.values[value_id] = value.model_copy(
                update={"consumer_call_ids": sorted(set(consumers.get(value_id, [])))}
            )
        seed = hashlib.sha256(
            f"{self.corpus.source_corpus_digest}:{self.entrypoint}".encode()
        ).hexdigest()[:24]
        values: dict[str, Any] = {
            "graph_id": f"semantic-graph:{seed}",
            "source_corpus_digest": self.corpus.source_corpus_digest,
            "entrypoint": self.entrypoint,
            "definitions": list(self.definitions.values()),
            "instances": list(self.instances.values()),
            "calls": list(self.calls.values()),
            "values": list(self.values.values()),
            "control_regions": list(self.control_regions.values()),
            "parameter_groups": list(self.parameter_groups.values()),
            "repeats": list(self.repeats.values()),
            "pattern_bindings": [],
            "evidence": list(self.evidence.values()),
            "diagnostics": self.diagnostics,
        }
        prototype = PythonSemanticGraph.model_construct(
            semantic_graph_digest="0" * 64,
            **values,
        )
        digest = domain_digest(SEMANTIC_GRAPH_DIGEST_DOMAIN, semantic_graph_payload(prototype))
        return PythonSemanticGraph(semantic_graph_digest=digest, **values)


def build_semantic_graph(
    corpus: SourceCorpus,
    repository: ParsedRepository,
    registry: BuiltinModuleRegistry,
    entrypoint: str,
    *,
    budget: AnalysisBudget | None = None,
    resolver_budget_exceeded: bool = False,
    resolver_facts: tuple[ResolverFact, ...] = (),
) -> PythonSemanticGraph:
    return SemanticGraphBuilder(
        corpus,
        repository,
        registry,
        entrypoint,
        budget,
        resolver_budget_exceeded,
        resolver_facts,
    ).build()
