"""Isolated, reviewed single-file semantic writeback with explicit profiles.

The project lock coordinates ArchCanvas clients only. The changed source uses
one filesystem atomic replace; unrelated editors remain outside that lock.
Receipts and backups are persisted before replacement. Recovery can overwrite
only the exact recorded after bytes, never a subsequent external edit.
"""

from __future__ import annotations

import copy
import difflib
import hashlib
import hmac
import json
import math
import os
import platform
import secrets
import stat
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from archcanvas_python import AnalysisError, analyze_project
from archcanvas_python.frontend import Corpus, digest

from .lowering import TRANSFORM, LoweringError, expected_delta, facts_digest, rewrite_literal, semantic_facts
from .rebind import REBIND_TRANSFORM, STRUCTURAL_TRANSFORM, expected_rebind, expected_structural_rebind, rewrite_name
from .config_activation import ACTIVATION_TRANSFORM, ACTIVATION_VERIFIED_TRANSFORM, CONFIG_TRANSFORM, expected_activation, expected_config, rewrite_registered_atom

REGISTERED_TRANSFORMS = {transform["id"]: transform for transform in (TRANSFORM, REBIND_TRANSFORM, STRUCTURAL_TRANSFORM, CONFIG_TRANSFORM, ACTIVATION_TRANSFORM, ACTIVATION_VERIFIED_TRANSFORM)}


class TransactionError(ValueError):
    """An invalid transaction request; safe for local service clients."""


_BINDING_FIELDS = ("id", "revision", "intent", "sourceDigest", "irDigest", "diff", "affectedNodeIds", "beforeArchitecture", "afterArchitecture", "sourceChanges", "checkpointImpact", "transform", "environment", "runtimeVerification", "runtimeEnvironment", "_runtimeConfig", "_runtimeReadSet", "_root", "_entry", "_readSet", "_writeSet", "_expected", "_observedDigest", "_verifiedGates")


def _environment() -> dict[str, Any]:
    return {"pythonImplementation": platform.python_implementation(), "pythonVersion": list(sys.version_info[:3]), "frontendContract": "archcanvas-stdlib-static-1", "modelExecution": "none"}


def _gate(identity: str, label: str, status: str, message: str) -> dict[str, str]:
    return {"id": identity, "label": label, "status": status, "message": message}


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy({key: value for key, value in record.items() if not key.startswith("_")})


class TransactionManager:
    def __init__(self, storeDirectory: str | Path):
        self.store = Path(storeDirectory).resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        with self._lock("approval-key"):
            key_path = self.store / "approval-key.bin"
            if key_path.is_symlink():
                raise TransactionError("The approval key must be a managed private regular file.")
            if not key_path.exists():
                self._durable_write(key_path, secrets.token_bytes(32))
            self._approval_key = key_path.read_bytes()
            if len(self._approval_key) != 32:
                raise TransactionError("The private approval key is invalid; existing approvals cannot be verified.")
        self._recover_registered()

    def _directory(self, identity: str) -> Path:
        if not isinstance(identity, str) or len(identity) != 32 or any(char not in "0123456789abcdef" for char in identity):
            raise TransactionError("Invalid transaction ID.")
        directory = self.store / identity
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.store):
            raise TransactionError("Transaction path is not managed by this store.")
        return directory

    @staticmethod
    def _fsync_directory(path: Path):
        if os.name == "posix":
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _replace(self, path: Path, data: bytes, mode: int = 0o600):
        """Durable sibling temporary file followed by a single atomic replacement."""
        temporary = path.with_name(f".{path.name}.archcanvas-{secrets.token_hex(8)}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fchmod(stream.fileno(), mode)
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            self._fsync_directory(path.parent)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _durable_write(self, path: Path, data: bytes, mode: int = 0o600):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._replace(path, data, mode)

    @contextmanager
    def _lock(self, key: str):
        directory = self.store / "locks"
        directory.mkdir(exist_ok=True)
        path = directory / f"{digest(key.encode())}.lock"
        with self._mutex, path.open("a+b") as stream:
            if os.name == "posix":
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            elif os.name == "nt":
                import msvcrt
                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if os.name == "posix":
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                elif os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def _save(self, record: dict[str, Any]):
        if "_journal" in record:
            record["_journal"]["signature"] = self._journal_signature(record)
        directory = self._directory(record["id"])
        directory.mkdir(exist_ok=True)
        self._durable_write(directory / "record.json", json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))

    def _register(self, record: dict[str, Any]):
        with self._lock("registered-transactions"):
            index = self.store / "registered.json"
            entries = json.loads(index.read_text()) if index.exists() else {}
            entries[record["id"]] = {"root": record["_root"], "entry": record["_entry"]}
            self._durable_write(index, json.dumps(entries, sort_keys=True).encode())

    def _read(self, identity: str) -> dict[str, Any]:
        path = self._directory(identity) / "record.json"
        if path.is_symlink():
            raise TransactionError("Transaction receipt is not a managed regular file.")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TransactionError("Transaction was not found or its receipt is invalid.") from exc
        if record.get("id") != identity:
            raise TransactionError("Transaction receipt ID does not match its managed directory.")
        return record

    @staticmethod
    def _source_path(root: Path, logical: str) -> Path:
        relative = Path(logical)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py":
            raise TransactionError("A transaction source path must be a relative Python path.")
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise TransactionError("A transaction source resolves outside the frozen project or is a symbolic link.")
        return path

    @staticmethod
    def _binding(record: dict[str, Any]) -> str:
        return digest({key: record.get(key) for key in _BINDING_FIELDS})

    def _approval_signature(self, approval: dict[str, Any]) -> str:
        fields = {key: approval.get(key) for key in ("id", "reviewDigest", "transactionId", "revision")}
        fields["consumed"] = bool(approval.get("consumed"))
        payload = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self._approval_key, payload, hashlib.sha256).hexdigest()

    def _journal_signature(self, record: dict[str, Any]) -> str:
        journal = {key: value for key, value in record.get("_journal", {}).items() if key != "signature"}
        payload = json.dumps({"id": record["id"], "status": record["status"], "reviewDigest": record["reviewDigest"], "journal": journal}, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self._approval_key, payload, hashlib.sha256).hexdigest()

    def _integrity(self, record: dict[str, Any]) -> str | None:
        if record.get("reviewDigest") != self._binding(record):
            return "The prepared receipt or concrete reviewed diff changed."
        registered = REGISTERED_TRANSFORMS.get(record.get("transform", {}).get("id"))
        if record.get("environment") != _environment() or registered is None or record.get("transform") != registered:
            return "The static analysis environment or registered transform version changed."
        if record["gates"][:len(record["_verifiedGates"])] != record["_verifiedGates"]:
            return "The verified gate receipts changed."
        if record["transform"]["profile"] == "structural-verified":
            try:
                self._verify_runtime_contract(record, record["runtimeVerification"])
            except (LoweringError, KeyError, TypeError, ValueError) as exc:
                return f"The structural runtime evidence no longer matches the approved contract: {exc}"
        directory = self._directory(record["id"])
        for logical, expected in record["_readSet"].items():
            path = self._source_path(directory / "staged", logical)
            expected_digest = record["_writeSet"].get(logical, {}).get("afterDigest", expected)
            if not path.is_file() or digest(path.read_bytes()) != expected_digest:
                return f"The frozen staging file changed: {logical}."
        try:
            staged = analyze_project(directory / "staged", record["_entry"])
        except (AnalysisError, OSError, UnicodeError, TransactionError) as exc:
            return f"The staged project can no longer be analyzed: {exc}"
        if staged["sourceDigest"] != record["afterArchitecture"]["sourceDigest"] or facts_digest(staged) != record["_observedDigest"] or semantic_facts(staged) != record["_expected"]:
            return "The frozen staging no longer matches its independent ExpectedDelta."
        return None

    @staticmethod
    def _verify_runtime_contract(record: dict[str, Any], report: dict[str, Any]):
        """Compare isolated observations to ORIGINAL-facts + intent expectations."""
        intent = record["intent"]
        spec = intent["inputSpec"]
        if report.get("status") != "passed" or report.get("profile") != "structural-verified" or report.get("sourceDigest") != record["afterArchitecture"]["sourceDigest"] or report.get("testedIRDigest") != record["afterArchitecture"]["irDigest"] or report.get("inputSpecDigest") != intent["inputSpecDigest"]:
            raise LoweringError("Runtime receipt does not bind the exact staged source, IR, frozen inputs and required profile.")
        manifest = report.get("manifest", {})
        if manifest.get("inputSpec") != spec or digest(manifest.get("environment")) != report.get("environmentDigest") or manifest.get("isolation", {}).get("available") is not True:
            raise LoweringError("Runtime manifest inputs/environment/isolation bindings are incomplete.")
        modes = report.get("observation", {}).get("modes", [])
        if [mode.get("mode") for mode in modes] != spec["modes"]:
            raise LoweringError("Runtime did not verify every declared mode in order.")
        expected = intent["expectedRuntimeContract"]
        expected_calls = expected["calls"]
        def tensor_matches(observed, contract):
            if contract is None:
                return isinstance(observed, dict) and observed.get("kind") == "none"
            return isinstance(observed, dict) and observed.get("kind") == "tensor" and observed.get("shape") == contract["shape"] and observed.get("dtype") == contract["dtype"] and observed.get("finite") is True
        def flatten_outputs(value):
            if isinstance(value, dict) and value.get("kind") in ("tensor", "none"):
                return [value]
            if isinstance(value, dict) and value.get("kind") in ("tuple", "list", "sequence"):
                return [item for child in value.get("items", []) for item in flatten_outputs(child)]
            if isinstance(value, list):
                return [item for child in value for item in flatten_outputs(child)]
            return []
        for mode in modes:
            if mode.get("finite") is not True or mode.get("gradients", {}).get("finite") is not True or not all(mode.get("replay", {}).get(key) is True for key in ("structureEqual", "bindingsEqual", "outputEqual", "gradientsEqual", "stateEqual")):
                raise LoweringError("Runtime forward/replay/finiteness verification did not pass.")
            if set(mode.get("inputs", {})) != set(spec["inputs"]) or any(not tensor_matches(mode["inputs"][name], contract) for name, contract in spec["inputs"].items()):
                raise LoweringError("Runtime inputs differ from the frozen specification.")
            for phase in ("before", "after"):
                entries = mode.get("state", {}).get(phase, {}).get("entries", [])
                observed_state = sorted(({key: item.get(key) for key in ("key", "shape", "dtype", "role")} for item in entries), key=lambda item: item["key"])
                if observed_state != expected["state"]:
                    raise LoweringError("Runtime parameter/buffer state differs from the independently frozen constructor contract.")
                if any(mode["state"][phase].get(key) != value for key, value in expected["stateSharing"].items()):
                    raise LoweringError("Runtime tied parameter/storage groups differ from the independently frozen constructor contract.")
            if mode.get("state", {}).get("mutatedKeys") != []:
                raise LoweringError("Unexpected model state mutation violates the structural source contract.")
            all_calls = mode.get("calls", [])
            roots = [call for call in all_calls if call.get("modulePath") == ""]
            if len(roots) != 1 or roots[0].get("callId") != "call:$root:0":
                raise LoweringError("Runtime must expose one root invocation.")
            calls = [call for call in all_calls if call.get("modulePath") != ""]
            if len(calls) != len(expected_calls):
                raise LoweringError("Observed module invocation count differs from the original intent oracle.")
            occurrences: dict[str, int] = {}
            for actual, expected_call in zip(calls, expected_calls):
                path = expected_call["modulePath"]
                occurrence = occurrences.get(path, 0); occurrences[path] = occurrence + 1
                if actual.get("modulePath") != path or actual.get("callId") != f"call:{path}:{occurrence}":
                    raise LoweringError("Observed module invocation identity/order differs from the intent oracle.")
                if not isinstance(actual.get("moduleType"), str) or actual["moduleType"].rsplit(".", 1)[-1] != expected_call["kind"]:
                    raise LoweringError("Observed framework module type differs from the independent transformation contract.")
                for name, input_contract in expected_call["inputs"].items():
                    tensor = actual.get("inputs", {}).get(name)
                    if not tensor_matches(tensor, input_contract["contract"]):
                        raise LoweringError(f"Observed named tensor input contract mismatch: {path}.{name}.")
                    binding = input_contract["binding"]
                    source = next(node for node in record["beforeArchitecture"]["nodes"] if node["id"] == binding["nodeId"])
                    if source["kind"] == "Input":
                        required = {"kind": "input", "name": source["label"]}
                    else:
                        source_call = next(call for call in expected_calls if call["nodeId"] == source["id"])
                        source_occurrence = sum(call["modulePath"] == source_call["modulePath"] for call in expected_calls[:expected_calls.index(source_call)])
                        required = {"kind": "call", "modulePath": source_call["modulePath"], "callId": f"call:{source_call['modulePath']}:{source_occurrence}", "portId": binding["portId"].rsplit(":", 1)[-1]}
                    histories = tensor.get("producerHistory", []) + ([tensor["producer"]] if isinstance(tensor.get("producer"), dict) else [])
                    if not any(all(history.get(key) == value for key, value in required.items()) for history in histories if isinstance(history, dict)):
                        raise LoweringError(f"Observed input producer history excludes the approved binding: {path}.{name}.")
                actual_output = actual.get("outputs", {})
                if set(actual_output) != set(expected_call["outputs"]) or any(not tensor_matches(actual_output[name], contract) for name, contract in expected_call["outputs"].items()):
                    raise LoweringError(f"Observed ordered output slots differ from the concrete oracle: {path}.")
            observed_outputs = flatten_outputs(mode.get("outputs"))
            if len(observed_outputs) != len(expected["outputs"]) or any(not tensor_matches(value, output["contract"]) for value, output in zip(observed_outputs, expected["outputs"])):
                raise LoweringError("Observed model output tuple shape/dtype/None slots differ from the frozen contract.")

    def _freshness(self, record: dict[str, Any]) -> str | None:
        root = Path(record["_root"])
        try:
            for path, expected in record.get("_runtimeReadSet", {}).items():
                if not Path(path).is_file() or digest(Path(path).read_bytes()) != expected:
                    return "The frozen runtime interpreter or dependency lock changed since verification."
            if record["transform"]["profile"] == "structural-verified":
                from archcanvas_runtime import fresh_binding
                current_runtime = fresh_binding(record["_runtimeConfig"])
                if current_runtime.get("available") is not True or current_runtime.get("environmentDigest") != record["runtimeVerification"]["environmentDigest"]:
                    return "The verified runtime environment or mandatory isolation binding changed since preparation."
            for logical, expected in record["_readSet"].items():
                path = self._source_path(root, logical)
                if not path.is_file() or digest(path.read_bytes()) != expected:
                    return f"Source corpus changed since preparation: {logical}."
                if logical in record["_writeSet"] and stat.S_IMODE(path.stat().st_mode) != record["_writeSet"][logical]["mode"]:
                    return f"Source file permissions changed since preparation: {logical}."
            # Re-discovery catches newly introduced local imports/shadowing as
            # well as changes to the full read-set, not only the changed file.
            current = analyze_project(root, record["_entry"])
            if current["sourceDigest"] != record["sourceDigest"] or current["irDigest"] != record["irDigest"]:
                return "The source discovery or architecture binding changed since preparation."
        except (AnalysisError, OSError, UnicodeError, TransactionError, ImportError, ValueError) as exc:
            return f"The frozen source corpus is no longer readable: {exc}"
        return None

    def prepare(self, root: Path, entry: str, nodeId: str, parameter: str, value: float, baseSourceDigest: str) -> dict[str, Any]:
        reported_value = value if type(value) in (int, float) and math.isfinite(value) else repr(value)
        def plan(before, project):
            return expected_delta(before, nodeId, parameter, value)
        def lower(raw, intent, before, corpus):
            selected = next(node for node in before["nodes"] if node["id"] == nodeId)
            return rewrite_literal(raw, intent["origin"], selected["kind"], parameter, intent["before"], intent["after"], corpus)
        return self._prepare(root, entry, baseSourceDigest, {"nodeId": nodeId, "parameter": parameter, "after": reported_value}, TRANSFORM, plan, lower)

    def prepare_rebind(self, root: Path, entry: str, nodeId: str, portId: str, producerNodeId: str, producerPortId: str, baseSourceDigest: str, *, inputSpec: dict[str, Any] | None = None, runtimeConfig: dict[str, Any] | None = None) -> dict[str, Any]:
        def plan(before, project):
            return expected_structural_rebind(before, project, entry, nodeId, portId, producerNodeId, producerPortId, inputSpec) if inputSpec is not None else expected_rebind(before, project, entry, nodeId, portId, producerNodeId, producerPortId)
        def lower(raw, intent, before, corpus):
            return rewrite_name(raw, intent["origin"], intent["before"]["variable"], intent["after"]["variable"])
        request = {"kind": "RebindInput", "nodeId": nodeId, "portId": portId, "producerNodeId": producerNodeId, "producerPortId": producerPortId}
        return self._prepare(root, entry, baseSourceDigest, request, STRUCTURAL_TRANSFORM if inputSpec is not None else REBIND_TRANSFORM, plan, lower, runtimeConfig)

    def prepare_config(self, root: Path, entry: str, nodeId: str, parameter: str, value: float, baseSourceDigest: str) -> dict[str, Any]:
        def plan(before, project):
            return expected_config(before, project, entry, nodeId, parameter, value)
        def lower(raw, intent, before, corpus):
            return rewrite_registered_atom(raw, intent["origin"], intent["before"], intent["after"], "configuration")
        reported = value if type(value) in (int, float) and math.isfinite(value) else repr(value)
        return self._prepare(root, entry, baseSourceDigest, {"kind": "UpdateConfiguration", "nodeId": nodeId, "parameter": parameter, "after": reported}, CONFIG_TRANSFORM, plan, lower)

    def prepare_activation(self, root: Path, entry: str, nodeId: str, activation: str, baseSourceDigest: str, *, inputSpec: dict[str, Any] | None = None, runtimeConfig: dict[str, Any] | None = None) -> dict[str, Any]:
        def plan(before, project):
            return expected_activation(before, project, entry, nodeId, activation, inputSpec)
        def lower(raw, intent, before, corpus):
            return rewrite_registered_atom(raw, intent["origin"], intent["before"], intent["after"], "activation")
        return self._prepare(root, entry, baseSourceDigest, {"kind": "ReplaceActivation", "nodeId": nodeId, "after": activation}, ACTIVATION_VERIFIED_TRANSFORM if inputSpec is not None else ACTIVATION_TRANSFORM, plan, lower, runtimeConfig)

    def _prepare(self, root: Path, entry: str, baseSourceDigest: str, request: dict[str, Any], transform: dict[str, Any], plan: Callable, lower: Callable, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
        project = Path(root).resolve()
        identity = secrets.token_hex(16)
        record: dict[str, Any] = {"id": identity, "revision": 1, "status": "Preparing", "intent": copy.deepcopy(request), "reviewDigest": None, "sourceDigest": baseSourceDigest, "irDigest": None, "diff": "", "affectedNodeIds": [], "gates": [], "blockers": [], "beforeArchitecture": None, "afterArchitecture": None, "sourceChanges": [], "checkpointImpact": {"status": "unknown", "message": "No supported transform has been verified."}, "transform": copy.deepcopy(transform), "_root": str(project), "_entry": entry}
        record["environment"] = _environment()
        directory = self._directory(identity)
        directory.mkdir()
        try:
            with self._lock(str(project)):
                before = analyze_project(project, entry)
                record["beforeArchitecture"] = before
                record["sourceDigest"] = before["sourceDigest"]
                record["irDigest"] = before["irDigest"]
                if before["sourceDigest"] != baseSourceDigest:
                    raise LoweringError("Source binding is stale; re-analyze before preparing a semantic change.")
                # This is intentionally BEFORE lowering or staged analysis.
                expected, affected, intent = plan(before, project)
                record.update(intent=intent, affectedNodeIds=affected, _expected=expected)
                record["_readSet"] = {source["path"]: source["digest"] for source in before["sources"]}
                original_bytes: dict[str, bytes] = {}
                for logical, source_digest in record["_readSet"].items():
                    source = self._source_path(project, logical)
                    raw = source.read_bytes()
                    if digest(raw) != source_digest:
                        raise LoweringError("Source changed while freezing the isolation snapshot.")
                    original_bytes[logical] = raw
                    self._durable_write(directory / "staged" / logical, raw)
                corpus = Corpus(project)
                corpus.load(entry.split(":", 1)[0])
                logical = intent["origin"]["path"]
                changed = lower(original_bytes[logical], intent, before, corpus)
                mode = stat.S_IMODE(self._source_path(project, logical).stat().st_mode)
                self._durable_write(directory / "staged" / logical, changed)
                after = analyze_project(directory / "staged", entry)
                record["afterArchitecture"] = after
                observed = semantic_facts(after)
                if observed != expected:
                    raise LoweringError("Independent ExpectedDelta does not match staged ObservedDelta; the source transform is blocked.")
                record["_observedDigest"] = digest(observed)
                change = {"path": logical, "beforeDigest": digest(original_bytes[logical]), "afterDigest": digest(changed)}
                record["sourceChanges"] = [change]
                record["_writeSet"] = {logical: {**change, "mode": mode}}
                old_text = original_bytes[logical].decode("utf-8-sig")
                new_text = changed.decode("utf-8-sig")
                record["diff"] = "".join(difflib.unified_diff(old_text.splitlines(keepends=True), new_text.splitlines(keepends=True), fromfile=f"a/{logical}", tofile=f"b/{logical}"))
                record["checkpointImpact"] = {"status": "compatible", "message": "Changing a dropout probability does not alter state_dict tensor names or shapes. No checkpoint was loaded and runtime behavior was not executed."}
                record["gates"] = [
                    _gate("G0", "来源与能力", "passed", "External PyTorch constructor, exact float-token anchor and complete source-origin call scope are proven within the registered static subset."),
                    _gate("G1", "源码有效性", "passed", "UTF-8 bytes/BOM/newlines preserved; the AST changes exactly one intended float argument."),
                    _gate("G2", "名称与项目", "passed", "Original external constructor and frozen local dependency corpus were statically resolved; no model imports or execution."),
                    _gate("G3", "重新分析", "passed", "The isolated staged corpus was parsed and its complete declared architecture was re-analyzed."),
                    _gate("G4", "意图兑现", "passed", "ExpectedDelta was frozen before lowering and matches ObservedDelta for every declared node, port, edge, parameter, repeat and sharing fact."),
                    _gate("G5", "参数约束", "passed", "Finite dropout probability in [0, 1]; this operation changes no tensor shape or type contract."),
                    _gate("G6", "运行验证", "not_run", "parameter-static profile: user model code was not executed; no forward/numerical equivalence claim."),
                    _gate("G7", "状态兼容", "passed", "Registered probability-only operation changes no parameter/buffer tensor shape; no checkpoint migration is performed."),
                    _gate("G8", "论文输出", "not_run", "No publication/export gate was requested by this source transaction."),
                    _gate("G9", "人工审核", "not_run", "Exact reviewDigest approval is required before source replacement."),
                    _gate("G10", "写回新鲜度", "not_run", "Full corpus, staging and approval will be rechecked under the project lock at commit."),
                    _gate("G11", "写后核验", "not_run", "Re-analysis and digest verification run only after approved source replacement."),
                ]
                if transform in (REBIND_TRANSFORM, STRUCTURAL_TRANSFORM):
                    record["checkpointImpact"] = {"status": "compatible", "message": "Rebinding a supported input changes tensor provenance and model behavior, but adds/removes no parameter or buffer definitions. No checkpoint was loaded or migrated. This static profile did not execute model code."}
                    messages = {
                        0: ("来源与能力", "The exact authored unary Name slot, in-scope dominating producer and same-base preserving chain are statically proven."),
                        1: ("源码有效性", "UTF-8 bytes/BOM/newlines preserved; exactly one direct unary call Name argument changes in the AST."),
                        2: ("名称与项目", "No reassignment, control flow, unresolved calls, shadowed framework symbols or in-place mutation exists in the registered forward region."),
                        4: ("意图兑现", "Independent ExpectedDelta changes exactly the chosen input edge source/tensor; every other declared node, port, edge, parameter, repeat and sharing fact matches."),
                        5: ("符号shape/type", "Conditional on a base tensor accepted by the registered operations, both producers preserve its same symbolic shape and dtype. Concrete dimensions/dtype remain unknown; different origins are refused and no numerical equivalence is claimed."),
                        6: ("运行验证", "symbolic-rebind-static profile: no user code execution, forward replay or numerical equivalence test was run."),
                        7: ("状态兼容", "The registered connection operation changes no parameter/buffer definitions or shape; no checkpoint migration is performed."),
                    }
                    for index, (label, message) in messages.items():
                        record["gates"][index] = _gate(f"G{index}", label, "not_run" if index == 6 else "passed", message)
                if transform == CONFIG_TRANSFORM:
                    record["gates"][0] = _gate("G0", "配置来源与完整影响", "passed", "One module-top-level float constant, no shadowing/reassignment, and every Name read is a fully analyzed registered probability argument. Derived or hidden readers are blocked.")
                    record["gates"][1] = _gate("G1", "源码有效性", "passed", "Exactly one frozen top-level float token changed; all reader expressions, comments and source bytes outside that token are preserved.")
                    record["gates"][4] = _gate("G4", "配置意图兑现", "passed", "ExpectedDelta independently updates all effective Dropout/MHA reader probabilities and container configuration facts; every other complete graph fact matches.")
                if transform in (ACTIVATION_TRANSFORM, ACTIVATION_VERIFIED_TRANSFORM):
                    record["checkpointImpact"] = {"status": "compatible", "message": "Default ReLU/GELU replacement changes activation behavior and adds/removes no parameter or buffer definitions. No checkpoint was loaded or migrated."}
                    record["gates"][0] = _gate("G0", "激活来源与完整影响", "passed", "One exact external no-argument ReLU/GELU constructor and every analyzed instance/call sharing it are source-bound.")
                    record["gates"][1] = _gate("G1", "源码有效性", "passed", "Exactly the activation constructor Name token changes; no arguments, calls, comments or other AST facts are rewritten.")
                    record["gates"][4] = _gate("G4", "激活意图兑现", "passed", "ExpectedDelta independently changes only the registered kind and required auto labels across its complete constructor scope; full topology, sharing and parameters remain equal.")
                    record["gates"][5] = _gate("G5", "激活参数契约", "passed", "Default ReLU/GELU preserve a valid floating input tensor's shape and dtype. Static profile makes no concrete input or numerical equivalence claim.")
                if transform["profile"] == "structural-verified":
                    if transform == STRUCTURAL_TRANSFORM:
                        record["gates"][0] = _gate("G0", "来源与能力", "passed", "Exact named/positional input slot, unique dominating producer and public unary/attention constructors are independently proven.")
                        record["gates"][1] = _gate("G1", "源码有效性", "passed", "UTF-8 bytes/BOM/newlines preserved; exactly one registered named/positional call argument Name changes in the AST.")
                        record["gates"][4] = _gate("G4", "意图兑现", "passed", "Independent ExpectedDelta changes the selected input binding and any consequent attention semantic role facts; every other declared graph fact matches.")
                    record["gates"][5] = _gate("G5", "具体shape/type/mask", "passed", "Frozen concrete InputSpec validates every registered input/output tensor, attention query/key/value/mask axis, feature/head divisibility, dtype and tuple output slot. The intentional change preserves those exact contracts.")
                    record["_runtimeConfig"] = {key: copy.deepcopy(value) for key, value in (runtime_config or {}).items() if key != "cancelEvent"} if isinstance(runtime_config, dict) else None
                    if not isinstance(runtime_config, dict) or not all(isinstance(runtime_config.get(key), str) and Path(runtime_config[key]).is_absolute() and Path(runtime_config[key]).is_file() for key in ("interpreter", "dependencyLock")):
                        record["gates"][6] = _gate("G6", "隔离运行验证", "failed", "An explicit locked interpreter and dependency lock are required; structural verification cannot downgrade to static.")
                        raise LoweringError("Required structural runtime configuration is missing or its frozen interpreter/lock is unavailable.")
                    record["_runtimeReadSet"] = {str(Path(runtime_config[key]).absolute()): digest(Path(runtime_config[key]).read_bytes()) for key in ("interpreter", "dependencyLock")}
                    try:
                        from archcanvas_runtime import verify_structural
                        verification = verify_structural(directory / "staged", entry, intent["inputSpec"], runtime_config)
                    except (ImportError, OSError, ValueError) as exc:
                        verification = {"schemaVersion": 1, "status": "unavailable", "profile": "structural-verified", "blockers": [str(exc)]}
                    record["runtimeVerification"] = verification
                    if verification.get("status") != "passed":
                        record["gates"][6] = _gate("G6", "隔离运行验证", "failed", "structural-verified requires successful isolated forward/replay; missing or failed runtime cannot downgrade to static approval.")
                        raise LoweringError("Required isolated structural verification did not pass: " + "; ".join(verification.get("blockers", [str(verification.get("reason", verification.get("status")))])))
                    try:
                        self._verify_runtime_contract(record, verification)
                    except (LoweringError, KeyError, TypeError, ValueError) as exc:
                        record["gates"][6] = _gate("G6", "独立运行契约核验", "failed", "The isolated runtime report does not satisfy the independently frozen source/IR/input/binding/state contract.")
                        raise LoweringError(f"Independent structural runtime contract verification failed: {exc}") from exc
                    record["runtimeEnvironment"] = copy.deepcopy(verification["manifest"]["environment"])
                    record["gates"][6] = _gate("G6", "隔离运行与replay", "passed", "Frozen staged source, declared modes and seeded inputs passed isolated CPU forward, replay, finiteness, concrete shape/dtype, named input bindings and tuple slot checks. This intentionally changed graph is not required to equal the previous model numerically.")
                    expected_state = intent["expectedRuntimeContract"]["state"]
                    record["checkpointImpact"] = {
                        "status": "compatible",
                        "message": ("Default ReLU/GELU replacement changes activation behavior." if transform == ACTIVATION_VERIFIED_TRANSFORM else "Rebinding the selected input changes tensor provenance and model behavior.") + " The frozen staged model was executed under the declared isolated CPU samples; its parameter/buffer keys, shapes, dtypes and tied tensor/storage groups match the unchanged original constructor contract before and after each mode. No checkpoint was loaded or migrated; compatibility with any external checkpoint remains untested.",
                        "modelExecuted": True, "checkpointLoaded": False,
                        "basis": "original-constructor-contract-versus-isolated-staged-observation",
                        "coverage": "declared-input-samples-and-modes-only",
                        "entries": copy.deepcopy(expected_state),
                        "sharing": copy.deepcopy(intent["expectedRuntimeContract"]["stateSharing"]),
                        "observedModes": list(intent["inputSpec"]["modes"]),
                    }
                    record["gates"][7] = _gate("G7", "状态兼容", "passed", "Observed parameter/buffer keys, shapes, dtypes and tied tensor/storage groups match the independently frozen unchanged constructor contract before/after all declared modes. No external checkpoint was loaded or migrated.")
                record["_verifiedGates"] = copy.deepcopy(record["gates"][:9])
                record["reviewDigest"] = self._binding(record)
                freshness = self._freshness(record)
                if freshness:
                    raise LoweringError(freshness)
                record["status"] = "ReviewReady"
        except (AnalysisError, LoweringError, OSError, UnicodeError, TransactionError) as exc:
            record["status"] = "Failed"
            record["blockers"] = [str(exc)]
            record["gates"].append(_gate("prepare", "准备事务", "failed", str(exc)))
        self._save(record)
        self._register(record)
        return _public(record)

    def get(self, identity: str) -> dict[str, Any]:
        return _public(self._read(identity))

    def matches_project(self, identity: str, root: str | Path, entry: str) -> bool:
        """Transport guard: a receipt marker alone is not the source-root authority."""
        record = self._read(identity)
        return record.get("_root") == str(Path(root).resolve()) and record.get("_entry") == entry

    def _stale(self, record: dict[str, Any], message: str) -> dict[str, Any]:
        record["status"] = "Stale"
        record["blockers"] = [message]
        record["gates"][10] = _gate("G10", "写回新鲜度", "failed", message)
        record.pop("approvalId", None)
        record.pop("_approval", None)
        self._save(record)
        return _public(record)

    def approve(self, identity: str, reviewDigest: str) -> dict[str, Any]:
        initial = self._read(identity)
        with self._lock(initial["_root"]):
            record = self._read(identity)
            if record["status"] != "ReviewReady":
                raise TransactionError("Only a ReviewReady transaction can receive a concrete human approval.")
            if not isinstance(reviewDigest, str) or reviewDigest != record["reviewDigest"]:
                raise TransactionError("Approval digest does not match the concrete reviewed transaction.")
            problem = self._integrity(record) or self._freshness(record)
            if problem:
                return self._stale(record, problem)
            approval = secrets.token_hex(32)
            record.update(status="Approved", approvalId=approval, _approval={"id": approval, "reviewDigest": reviewDigest, "transactionId": identity, "revision": record["revision"]})
            record["_approval"]["signature"] = self._approval_signature(record["_approval"])
            record["gates"][9] = _gate("G9", "人工审核", "passed", "Explicit approval binds this exact transaction revision, corpus, staging, delta, diff and gate receipts.")
            self._save(record)
            return _public(record)

    def _verify_committed(self, record: dict[str, Any]) -> dict[str, Any]:
        root = Path(record["_root"])
        for logical, change in record["_writeSet"].items():
            if digest(self._source_path(root, logical).read_bytes()) != change["afterDigest"]:
                raise TransactionError("Written source bytes do not match the approved staging.")
        architecture = analyze_project(root, record["_entry"])
        if architecture["sourceDigest"] != record["afterArchitecture"]["sourceDigest"] or semantic_facts(architecture) != record["_expected"]:
            raise TransactionError("Written source architecture does not match the approved ExpectedDelta.")
        return architecture

    def commit(self, identity: str, approvalId: str) -> dict[str, Any]:
        initial = self._read(identity)
        with self._lock(initial["_root"]):
            record = self._read(identity)
            approval = record.get("_approval", {})
            if record["status"] != "Approved" or not isinstance(approvalId, str) or not secrets.compare_digest(approvalId, approval.get("id", "")) or approval.get("transactionId") != identity or approval.get("reviewDigest") != record["reviewDigest"] or approval.get("revision") != record["revision"] or not secrets.compare_digest(approval.get("signature", ""), self._approval_signature(approval)) or approval.get("consumed"):
                raise TransactionError("Commit requires the unconsumed approval for this exact reviewed transaction.")
            problem = self._integrity(record) or self._freshness(record)
            if problem:
                return self._stale(record, problem)
            directory = self._directory(identity)
            project = Path(record["_root"])
            try:
                # All backups must be durable and checked before commit intent
                # is registered, and before any original file is replaced.
                for logical, change in record["_writeSet"].items():
                    original = self._source_path(project, logical).read_bytes()
                    if digest(original) != change["beforeDigest"]:
                        return self._stale(record, "Source changed immediately before backup.")
                    self._durable_write(directory / "backup" / logical, original, change["mode"])
                    if digest((directory / "backup" / logical).read_bytes()) != change["beforeDigest"]:
                        raise TransactionError("Backup verification failed; no source file was replaced.")
                record["status"] = "Committing"
                record["gates"][10] = _gate("G10", "写回新鲜度", "passed", "Full source corpus, dependency discovery, staging, exact diff and approval bindings rechecked under the project lock.")
                record["_journal"] = {"phase": "intent", "files": copy.deepcopy(record["_writeSet"]), "replaced": []}
                self._save(record)
                # Narrow the uncooperative-editor window by rechecking after
                # backup/journal persistence as well as before acquiring intent.
                problem = self._freshness(record)
                if problem:
                    return self._stale(record, problem)
                for logical, change in record["_writeSet"].items():
                    data = (directory / "staged" / logical).read_bytes()
                    if digest(data) != change["afterDigest"]:
                        return self._stale(record, "Staging changed immediately before replacement.")
                    self._replace(self._source_path(project, logical), data, change["mode"])
                    record["_journal"]["replaced"].append(logical)
                    record["_journal"]["phase"] = "replaced"
                    self._save(record)
                committed = self._verify_committed(record)
                record["status"] = "Committed"
                record["committedArchitecture"] = committed
                record["committedSourceDigest"] = committed["sourceDigest"]
                record["_journal"]["phase"] = "complete"
                record["_approval"]["consumed"] = True
                record["_approval"]["signature"] = self._approval_signature(record["_approval"])
                record["gates"][11] = _gate("G11", "写后核验", "passed", "Atomic single-file replacement, byte digest and independent complete architecture re-analysis match the approved transaction.")
                self._save(record)
            except (AnalysisError, OSError, UnicodeError, TransactionError) as exc:
                record["status"] = "RecoveryRequired"
                record["blockers"] = [f"Commit failed: {exc}"]
                self._save(record)
                self._recover(record)
            return _public(record)

    def _recover(self, record: dict[str, Any]):
        directory = self._directory(record["id"])
        root = Path(record["_root"])
        unresolved: list[str] = []
        for logical, change in record.get("_writeSet", {}).items():
            try:
                target = self._source_path(root, logical)
                current = digest(target.read_bytes())
                if current == change["beforeDigest"]:
                    continue
                if current != change["afterDigest"]:
                    unresolved.append(f"{logical}: later external changes or missing original; restore manually from {directory / 'backup' / logical}.")
                    continue
                backup = directory / "backup" / logical
                data = backup.read_bytes()
                if digest(data) != change["beforeDigest"]:
                    unresolved.append(f"{logical}: backup digest mismatch; automatic recovery stopped.")
                    continue
                # Recheck directly before replacing only our own exact after.
                if digest(target.read_bytes()) != change["afterDigest"]:
                    unresolved.append(f"{logical}: source changed during recovery; no overwrite.")
                    continue
                self._replace(target, data, change["mode"])
                if digest(target.read_bytes()) != change["beforeDigest"]:
                    unresolved.append(f"{logical}: recovery digest verification failed.")
            except (OSError, UnicodeError, TransactionError) as exc:
                unresolved.append(f"{logical}: recovery requires manual action: {exc}")
        record["status"] = "ManualRecovery" if unresolved else "RolledBack"
        if unresolved:
            record["blockers"].extend(unresolved)
        record.setdefault("_journal", {})["phase"] = "manual-recovery" if unresolved else "rolled-back"
        record.pop("approvalId", None)
        record.pop("_approval", None)
        self._save(record)

    def _recover_registered(self):
        index = self.store / "registered.json"
        if not index.exists():
            return
        try:
            registered = json.loads(index.read_text())
        except (OSError, ValueError) as exc:
            raise TransactionError("The transaction registry is unreadable; automatic recovery was not attempted.") from exc
        for identity, binding in registered.items():
            record = self._read(identity)
            if record["status"] not in ("Committing", "RecoveryRequired"):
                continue
            # Recovery enumerates only explicitly registered source bindings,
            # never source-directory scans or guessed backup files.
            if record.get("_root") != binding.get("root") or record.get("_entry") != binding.get("entry") or self._binding(record) != record.get("reviewDigest") or not secrets.compare_digest(record.get("_journal", {}).get("signature", ""), self._journal_signature(record)):
                raise TransactionError("Registered recovery binding changed; manual inspection is required.")
            with self._lock(record["_root"]):
                self._recover(record)

    def discard(self, identity: str) -> dict[str, Any]:
        initial = self._read(identity)
        with self._lock(initial["_root"]):
            record = self._read(identity)
            if record["status"] not in ("ReviewReady", "Approved", "Failed", "Stale"):
                raise TransactionError("Only an uncommitted transaction can be discarded.")
            record["status"] = "Discarded"
            record.pop("approvalId", None)
            record.pop("_approval", None)
            self._save(record)
            return _public(record)
