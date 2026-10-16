"""Source-preserving copies for graphs with unresolved control flow.

This never lowers the displayed source inspection tree into tensor operations.
It copies the frozen corpus, optionally replacing independently anchored literal
constructor arguments or bounded call/return expressions, then independently
analyzes the resulting corpus.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile

from archcanvas_python import analyze_project
from archcanvas_python.frontend import CONTRACTS, Corpus, load_project_corpus
from .draft import DraftError, _diagnostic


def _unsupported(message, node_id=None):
    raise DraftError(message, diagnostics=[_diagnostic(
        "unsupported-source-preserving-edit",
        "此模型保留原始分支与循环源码；改动需要明确的构造参数、调用参数或返回值源码锚点。未知语法关系、跨作用域连接与未定位的改动不能生成。",
        message, **({"nodeId": node_id} if node_id else {}))])


def _facts(architecture):
    """All semantic facts except evidence spelling and source versions."""
    value = deepcopy({key: architecture[key] for key in ("schemaVersion", "id", "label", "entry", "nodes", "edges")})
    for node in value["nodes"]:
        node.pop("source", None)
        if "parameterOrigins" in node:
            node["parameterOrigins"] = {
                name: {key: item for key, item in origin.items()
                       if key in ("kind", "path") or key == "expression" and origin.get("kind") != "literal"}
                for name, origin in node["parameterOrigins"].items()}
    if "sourceRelations" in architecture:
        value["sourceRelations"] = deepcopy([{key: item for key, item in relation.items() if key != "source"}
                                             for relation in architecture["sourceRelations"]])
    # Inspection IDs hash authored syntax, so an allowed constructor literal
    # can change an inspection card's ID and every descendant's prefix. Compare
    # the exact tree position instead. Added/reordered cards, parents, relations
    # and every other parameter remain part of the oracle.
    nodes = {node["id"]: node for node in architecture["nodes"]}
    identities = {}
    def identity(key):
        if key in identities:
            return identities[key]
        node = nodes[key]
        if not node.get("sourceStructure"):
            identities[key] = key
        else:
            parent = node.get("parentId")
            ordinal = nodes[parent]["children"].index(key) if parent else [item["id"] for item in architecture["nodes"] if not item.get("parentId")].index(key)
            identities[key] = f"inspection:{identity(parent) if parent else 'root'}:{ordinal}"
        return identities[key]
    for key in nodes:
        identity(key)
    for node in value["nodes"]:
        node["id"] = identities[node["id"]]
        if "parentId" in node:
            node["parentId"] = identities[node["parentId"]]
        node["children"] = [identities[key] for key in node["children"]]
        if node.get("sourceStructure") and "definitionReference" in node["parameters"]:
            node["parameters"]["definitionReference"] = identities.get(node["parameters"]["definitionReference"], node["parameters"]["definitionReference"])
    for relation in value.get("sourceRelations", []):
        relation["sourceId"], relation["targetId"] = identities[relation["sourceId"]], identities[relation["targetId"]]
        if "boundary" in relation:
            relation["boundary"]["nodeIds"] = [identities[key] for key in relation["boundary"]["nodeIds"]]
        relation.pop("id", None)  # A deterministic hash of the retained endpoints.
    return value


def _raw(source):
    raw = source["content"].encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != source["digest"]:
        raw = b"\xef\xbb\xbf" + raw
    if hashlib.sha256(raw).hexdigest() != source["digest"]:
        raise DraftError("Frozen source bytes do not match their digest.")
    return raw


def preservation_options(draft):
    """Cheap UI preflight; generation still replays source independently."""
    provenance = draft["sourceProvenance"]
    original = {node["id"]: node for node in provenance["originalGraph"]["nodes"]}
    current = {node["id"]: node for node in draft["nodes"]}
    reasons = []
    from .source_surgery import structural_delta, plan_surgery
    structural = structural_delta(draft)
    if structural:
        try:
            plan_surgery(draft)
        except DraftError as exc:
            reasons.append(str(exc))
    cache = draft.get("sourceCache", {})
    if not structural and (cache.get("removedNodeIds") or cache.get("removedCanonicalEdgeIds") or cache.get("edges")):
        reasons.append("Hidden structural edits need a separate generation contract.")
    refs = provenance["nodeRefs"]
    facts = {node["id"]: node for node in provenance["architecture"]["nodes"]}
    candidates = {node["id"]: node for node in cache.get("nodes", [])}
    candidates.update(current)
    for identity, node in candidates.items():
        ref = refs.get(identity)
        if not ref:
            if not structural:
                reasons.append("Added nodes have no preserved source identity.")
            continue
        fact = facts[ref["nodeId"]]
        for parameter, value in node["parameters"].items():
            before = ref["originalParameters"].get(parameter)
            if type(value) is type(before) and value == before:
                continue
            origin = fact.get("parameterOrigins", {}).get(parameter, {})
            if fact.get("evidence") != "contract" or fact["kind"] not in CONTRACTS or origin.get("kind") != "literal" or type(value) not in (str, bool, int, float):
                reasons.append("A changed parameter needs an explicit registered constructor literal.")
    return {"mode": "source-preserved-copy", "supported": not reasons, "topology": "anchored-edits" if structural else "preserved",
            "limitations": list(dict.fromkeys(reasons)) + [
                "Original branches, loops and unresolved regions are copied as source; displayed inspection arrows are not tensor lowering.",
                "Literal parameters and bounded unary insertions, bypass deletions and rewires require exact AST anchors; independent source reanalysis is mandatory.",
                "Static validation does not establish runtime shape or numerical correctness."]}


def _literal_edit(source, origin, kind, parameter, before, after, corpus):
    """Re-locate one explicit constructor argument using AST byte coordinates."""
    unit = next((unit for unit in corpus.units.values() if unit.path == source["path"]), None)
    if unit is None or kind not in CONTRACTS or not corpus.framework_is_unshadowed():
        _unsupported("The external constructor is not independently resolved.")
    coordinates = tuple(origin.get(key) for key in ("line", "column", "endLine", "endColumn"))
    atoms = [item for item in ast.walk(unit.tree) if isinstance(item, ast.Constant)
             and (item.lineno, item.col_offset, item.end_lineno, item.end_col_offset) == coordinates]
    if len(atoms) != 1 or type(atoms[0].value) is not type(before) or atoms[0].value != before:
        _unsupported("The original literal argument no longer matches the frozen source.")
    atom = atoms[0]
    parents = {child: parent for parent in ast.walk(unit.tree) for child in ast.iter_child_nodes(parent)}
    owner = parents.get(atom)
    if isinstance(owner, ast.keyword):
        if owner.arg != parameter:
            _unsupported("The source anchor is a different constructor keyword.")
        call = parents.get(owner)
    else:
        call = owner
        position = CONTRACTS[kind][0].index(parameter) if parameter in CONTRACTS[kind][0] else -1
        if not isinstance(call, ast.Call) or position < 0 or len(call.args) <= position or call.args[position] is not atom:
            _unsupported("The source anchor is not the registered positional constructor argument.")
    if (not isinstance(call, ast.Call) or any(isinstance(item, ast.Starred) for item in call.args)
            or any(item.arg is None for item in call.keywords)):
        _unsupported("Unpacked constructor arguments have no source-preserving edit contract.")
    positional_names = CONTRACTS[kind][0][:len(call.args)]
    named = [item.arg for item in call.keywords]
    if len(set(named)) != len(named) or set(named) & set(positional_names):
        _unsupported("Duplicated constructor arguments cannot be edited.")
    function = parents.get(call)
    while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        function = parents.get(function)
    if not isinstance(function, ast.FunctionDef) or function.name != "__init__" or function.decorator_list:
        _unsupported("Only ordinary directly authored initializer arguments are editable.")
    shadowed = dict.fromkeys([item.arg for item in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]]
                            + [item.id for item in ast.walk(function) if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del))])
    if unit.resolve(call.func, shadowed) != f"torch.nn.{kind}":
        _unsupported("The constructor symbol is shadowed or is not external PyTorch.")
    replacement = repr(after)
    parsed = ast.parse(replacement, mode="eval").body
    if not isinstance(parsed, ast.Constant) or type(parsed.value) is not type(after) or parsed.value != after:
        _unsupported("Only finite primitive literal replacements are supported.")
    raw = _raw(source)
    bom = 3 if raw.startswith(b"\xef\xbb\xbf") else 0
    lines = source["content"].splitlines(keepends=True)
    start = bom + sum(len(line.encode("utf-8")) for line in lines[:atom.lineno - 1]) + atom.col_offset
    end = bom + sum(len(line.encode("utf-8")) for line in lines[:atom.end_lineno - 1]) + atom.end_col_offset
    if raw[start:end].decode("utf-8") != unit.expression(atom):
        _unsupported("The source span does not match the exact literal bytes.")
    return start, end, replacement.encode("utf-8")


def generate_preserved_source(draft, validated):
    from .source_surgery import structural_delta, generate_surgery
    if structural_delta(draft):
        return generate_surgery(draft, validated)
    from .source_import import _analyze_sources
    provenance = draft["sourceProvenance"]
    original = _analyze_sources(provenance["architecture"])
    refs = provenance["nodeRefs"]
    original_nodes = {node["id"]: node for node in provenance["originalGraph"]["nodes"]}
    actual_nodes = {node["id"]: node for node in draft["nodes"]}
    if set(actual_nodes) != set(original_nodes):
        _unsupported("Source-preserving generation cannot add, delete or substitute graph modules.")
    if {edge["id"]: edge for edge in draft["edges"]} != {edge["id"]: edge for edge in provenance["originalGraph"]["edges"]}:
        _unsupported("Source-preserving generation cannot alter tensor or source relations.")
    cache = draft.get("sourceCache", {})
    if cache.get("removedNodeIds") or cache.get("removedCanonicalEdgeIds") or cache.get("edges"):
        _unsupported("A hidden structural edit cannot be discarded during source-preserving generation.")
    candidates = {node["id"]: node for node in cache.get("nodes", [])}
    candidates.update(actual_nodes)
    facts = {node["id"]: node for node in original["nodes"]}
    expected = _facts(original)
    desired = {}
    edits = {}
    with tempfile.TemporaryDirectory(prefix="archcanvas-preserved-source-") as temporary:
        root = Path(temporary)
        for item in original["sources"]:
            path = root / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_raw(item))
        corpus = load_project_corpus(root)
        corpus.load(original["entry"].split(":", 1)[0])
        sources = {item["path"]: item for item in original["sources"]}
        for identity, node in candidates.items():
            ref = refs.get(identity)
            if not ref or node["kind"] != "Source_" + identity[2:]:
                _unsupported("A hidden node has no immutable source identity.", identity)
            before = ref["originalParameters"]
            params = node["parameters"]
            if set(params) != set(before):
                _unsupported("Parameters cannot be added or omitted on a retained source module.", identity)
            fact = facts[ref["nodeId"]]
            for parameter, after in params.items():
                if after == before[parameter] and type(after) is type(before[parameter]):
                    continue
                origin = fact.get("parameterOrigins", {}).get(parameter)
                if (fact.get("evidence") != "contract" or fact["kind"] not in CONTRACTS
                        or not origin or origin.get("kind") != "literal"
                        or type(after) not in (str, bool, int, float)):
                    _unsupported("The changed parameter has no explicit registered literal source anchor.", identity)
                key = tuple(origin.get(name) for name in ("path", "line", "column", "endLine", "endColumn"))
                if key in desired and (type(desired[key]) is not type(after) or desired[key] != after):
                    _unsupported("Shared calls request conflicting values for the same constructor literal.", identity)
                desired[key] = after
                span = _literal_edit(sources[origin["path"]], origin, fact["kind"], parameter, before[parameter], after, corpus)
                edits[key] = {"path": origin["path"], "start": span[0], "end": span[1], "replacement": span[2],
                              "kind": fact["kind"], "parameter": parameter, "before": before[parameter], "after": after}
        # A constructor can feed several invocation nodes. One literal edits
        # all of them; contradictory edits above are rejected, never last-wins.
        affected = []
        for fact, actual in zip(expected["nodes"], original["nodes"]):
            for parameter, origin in actual.get("parameterOrigins", {}).items():
                key = tuple(origin.get(name) for name in ("path", "line", "column", "endLine", "endColumn"))
                if key in desired:
                    fact["parameters"][parameter] = deepcopy(desired[key])
                    affected.append({"nodeId": fact["id"], "parameter": parameter})
            # Source inspection may show the same constructor that supplied a
            # proven call. Update only its exact anchored AST literal spelling;
            # arbitrary sourceStructure edits remain unsupported above.
            if actual.get("sourceStructure") and "construction" in fact["parameters"]:
                source = actual.get("source", {})
                unit = next((own for own in corpus.units.values() if own.path == source.get("path")), None)
                candidates = [part for part in ast.walk(unit.tree) if isinstance(part, ast.Call)
                              and part.lineno == source.get("line") and part.end_lineno == source.get("endLine")
                              and unit.expression(part) == source.get("expression")] if unit else []
                if len(candidates) == 1:
                    constructor = deepcopy(candidates[0])
                    for atom in ast.walk(constructor):
                        if not isinstance(atom, ast.Constant):
                            continue
                        key = source["path"], atom.lineno, atom.col_offset, atom.end_lineno, atom.end_col_offset
                        if key in desired:
                            atom.value = desired[key]
                    fact["parameters"]["construction"] = ast.unparse(constructor)
        for path in sources:
            raw = _raw(sources[path])
            ordered = sorted((edit for edit in edits.values() if edit["path"] == path), key=lambda edit: edit["start"], reverse=True)
            previous = len(raw) + 1
            for edit in ordered:
                if edit["end"] > previous:
                    _unsupported("Overlapping source edits cannot be composed.")
                raw = raw[:edit["start"]] + edit["replacement"] + raw[edit["end"]:]
                previous = edit["start"]
            (root / path).write_bytes(raw)
        architecture = analyze_project(root, original["entry"])
        if _facts(architecture) != expected:
            _unsupported("Independent reanalysis changed facts outside the declared literal edits; source copy refused.")
    # Syntax-derived inspection IDs can change after an allowed literal edit.
    # The exact normalized-tree oracle above established this positional map;
    # never return a stale original ID for the new canvas.
    canonical_mapping = {before["id"]: after["id"] for before, after in zip(original["nodes"], architecture["nodes"])}
    nodes, containers = {}, {}
    for node in draft["nodes"]:
        canonical = refs[node["id"]]["nodeId"]
        (containers if facts[canonical].get("children") else nodes)[node["id"]] = canonical_mapping[canonical]
    edge_bindings = {edge["id"]: deepcopy(provenance["edgeRefs"][edge["id"]]) for edge in draft["edges"]}
    entry_module = architecture["entry"].split(":", 1)[0]
    entry_paths = (entry_module.replace(".", "/") + ".py", entry_module.replace(".", "/") + "/__init__.py")
    source = next(item["content"] for item in architecture["sources"] if item["path"] in entry_paths)
    return {"draft": deepcopy(draft), "draftDigest": validated["draftDigest"], "entry": architecture["entry"],
            "source": source, "architecture": architecture, "nodeBindings": nodes, "containerBindings": containers,
            "edgeBindings": edge_bindings, "portBindings": {}, "tensors": {},
            "sourceEdits": [{key: value for key, value in edit.items() if key not in ("replacement", "start", "end")}
                            for edit in edits.values()],
            "verification": {"status": "passed", "scope": "source-preserved-literal-edit-copy", "topology": "preserved",
                             "modelExecution": "not_run", "sourceProvenanceDigest": provenance["digest"],
                             "literalEdits": len(edits), "affectedOperations": affected,
                             "limitations": ["Original branches, loops, helpers and unresolved regions are preserved as source bytes; they are not lowered from visual arrows.",
                                             "This copy preserves topology and changes only explicit registered constructor literals, if requested; eligible graph edits use the separate anchored-expression verification path.",
                                             "No model was imported or executed; shapes, runtime branches and numerical behavior remain unverified."]}}
