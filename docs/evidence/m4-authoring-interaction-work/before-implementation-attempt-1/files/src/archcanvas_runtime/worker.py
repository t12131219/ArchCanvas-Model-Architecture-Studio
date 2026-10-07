"""Trusted isolated worker bootstrap; intentionally independent of the service."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
import resource
import socket
import sys
import traceback
from pathlib import Path


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def apply_limits(limits):
    for kind, amount in ((resource.RLIMIT_AS, limits["addressSpaceBytes"]), (resource.RLIMIT_CPU, limits["cpuSeconds"]), (resource.RLIMIT_FSIZE, limits["fileBytes"]), (resource.RLIMIT_NOFILE, limits["openFiles"]), (resource.RLIMIT_NPROC, limits["uidTaskLimit"]), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(kind, (amount, amount))


def probe(request):
    checks = {}
    namespaces = {name: os.readlink(f"/proc/self/ns/{name}") for name in request["hostNamespaces"]}
    checks["namespacesDistinct"] = all(namespaces[name] != identity for name, identity in request["hostNamespaces"].items())
    checks["hostFileAbsent"] = not Path(request["hostSentinel"]).exists()
    checks["hostHomeAbsent"] = not Path("/home/fzg/.ssh").exists()
    checks["baseEnvironmentUnexposed"] = not Path(request["environment"]["baseHiddenProbe"]).exists()
    try:
        with open("/model/" + request["sourceProbe"], "ab") as handle:
            handle.write(b"isolation-probe")
        checks["frozenSourceReadOnly"] = False
    except OSError as exc:
        checks["frozenSourceReadOnly"] = exc.errno in (13, 30)
    Path("/work/private-probe").write_text("private")
    checks["privateWritable"] = Path("/work/private-probe").read_text() == "private"
    try:
        sock = socket.socket()
        sock.close()
        checks["socketDenied"] = False
    except OSError as exc:
        checks["socketDenied"] = exc.errno in (1, 13)
    try:
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        checks["processCreationDenied"] = False
    except OSError as exc:
        checks["processCreationDenied"] = exc.errno in (1, 11, 13)
    checks["addressSpaceLimitApplied"] = resource.getrlimit(resource.RLIMIT_AS) == (request["limits"]["addressSpaceBytes"],) * 2
    checks["cpuLimitApplied"] = resource.getrlimit(resource.RLIMIT_CPU) == (request["limits"]["cpuSeconds"],) * 2
    seccomp = next(line.strip() for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("Seccomp:"))
    checks["kernelSeccompFilter"] = seccomp.split()[-1] == "2"
    return {"available": all(checks.values()), "mechanism": "Linux Bubblewrap user/mount/pid/net/ipc/uts namespaces and mandatory x86-64 seccomp", "checks": checks, "namespaces": namespaces, "network": "separate namespace plus socket/socketpair syscall denial", "processLimit": "non-thread clone/fork/vfork denied; clone3 ENOSYS; RLIMIT_NPROC thread budget", "reason": "" if all(checks.values()) else "At least one mandatory isolation probe failed."}


def environment(request, torch):
    import re
    packages = {re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(): dist.version for dist in importlib.metadata.distributions() if dist.metadata["Name"]}
    expected = request["environment"]["dependencyPins"]
    mismatches = [f"{name}: expected {version}, observed {packages.get(name)}" for name, version in expected.items() if packages.get(name) != version]
    extras = sorted(set(packages) - set(expected) - {"pip", "setuptools", "wheel"})
    origin = str(Path(torch.__file__).resolve())
    prefix = request["environment"]["virtualEnvironment"]
    if not Path(origin).is_relative_to(prefix):
        mismatches.append("PyTorch module origin is outside the explicit virtual environment.")
    if torch.version.cuda is not None or not torch.__version__.endswith("+cpu"):
        mismatches.append("A CPU-only PyTorch build is mandatory.")
    if extras:
        mismatches.append("Unpinned environment packages: " + ", ".join(extras))
    return {"valid": not mismatches, "reason": "; ".join(mismatches), "environment": {"pythonVersion": sys.version.split()[0], "frameworkVersion": torch.__version__, "frameworkOrigin": origin, "installedPackages": packages, "sysPrefix": sys.prefix, "sysBasePrefix": sys.base_prefix, "device": "cpu", "backend": "pytorch"}}


def observe(request, torch):
    spec = request["inputSpec"]
    sys.path.insert(0, "/model")
    module_name, class_name = request["entry"].split(":", 1)
    module = importlib.import_module(module_name)
    model_class = getattr(module, class_name)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)

    def value_hash(tensor):
        value = tensor.detach().cpu().contiguous().clone()
        return digest(bytes(value.untyped_storage()))

    def state(model):
        params = dict(model.named_parameters(remove_duplicate=False))
        buffers = dict(model.named_buffers(remove_duplicate=False))
        identities = {}
        storages = {}
        for name, value in {**params, **buffers}.items():
            identities.setdefault(id(value), []).append(name)
            if value.numel():
                storages.setdefault(value.untyped_storage().data_ptr(), []).append(name)
        entries = []
        for key, value in sorted(model.state_dict().items()):
            entries.append({"key": key, "shape": list(value.shape), "dtype": str(value.dtype).removeprefix("torch."), "role": "parameter" if key in params else "buffer" if key in buffers else "state", "requiresGrad": bool(params[key].requires_grad) if key in params else False, "valueDigest": value_hash(value)})
        return {"entries": entries, "digest": digest(entries), "sharedGroups": sorted((sorted(names) for names in identities.values() if len(names) > 1)), "sharedStorageGroups": sorted((sorted(names) for names in storages.values() if len(names) > 1)), "parameters": len(params), "buffers": len(buffers)}

    def one_pass(mode):
        torch.manual_seed(spec["seed"])
        model = model_class(**spec["constructor"]).cpu()
        if not isinstance(model, torch.nn.Module):
            raise ValueError("Entry did not construct a torch.nn.Module.")
        model.train(mode == "train")
        inputs = {}
        for name, item in spec["inputs"].items():
            dtype = getattr(torch, item["dtype"])
            maker = {"normal": torch.randn, "zeros": torch.zeros, "ones": torch.ones}[item["fill"]]
            tensor = maker(item["shape"], dtype=dtype, device="cpu")
            if tensor.is_floating_point():
                tensor.requires_grad_(True)
            inputs[name] = tensor
        inspect.signature(model.forward).bind(**inputs)
        producers, tensor_ids, live_tensors = {}, {}, []
        calls, active, counts, handles = [], [], {}, []
        module_names = {}
        for name, child in model.named_modules(remove_duplicate=False):
            module_names.setdefault(id(child), name)
        before = state(model)

        def tensor_description(value):
            key = id(value)
            if key not in tensor_ids:
                tensor_ids[key] = f"tensor:{len(tensor_ids)}"
                live_tensors.append(value)
            history = producers.get(key, [])
            return {"kind": "tensor", "tensorId": tensor_ids[key], "shape": list(value.shape), "dtype": str(value.dtype).removeprefix("torch."), "device": str(value.device), "finite": bool(torch.isfinite(value.detach()).all()), "valueDigest": value_hash(value), "producer": history[-1] if history else {"kind": "unresolved", "reason": "functional operation or unobserved alias"}, "producerHistory": list(history)}

        def describe(value):
            if isinstance(value, torch.Tensor):
                return tensor_description(value)
            if value is None:
                return {"kind": "none"}
            if isinstance(value, (bool, int, float, str)):
                return {"kind": "scalar", "value": value}
            if isinstance(value, (list, tuple)):
                return {"kind": "sequence", "items": [describe(item) for item in value]}
            if isinstance(value, dict) and all(isinstance(key, str) for key in value):
                return {"kind": "mapping", "items": {key: describe(item) for key, item in sorted(value.items())}}
            return {"kind": "opaque", "type": type(value).__name__}

        def mark(value, producer):
            if isinstance(value, torch.Tensor):
                producers.setdefault(id(value), []).append(producer)
            elif isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    mark(item, {**producer, "component": str(index)})
            elif isinstance(value, dict):
                for key, item in value.items():
                    mark(item, {**producer, "component": str(key)})

        for name, tensor in inputs.items():
            mark(tensor, {"kind": "input", "name": name})
        input_descriptions = {name: describe(value) for name, value in inputs.items()}

        def pre(child, args, kwargs):
            path = module_names[id(child)]
            index = counts.get(path, 0)
            counts[path] = index + 1
            bound = inspect.signature(child.forward).bind(*args, **kwargs)
            bound.apply_defaults()
            call = {"callId": f"call:{path or '$root'}:{index}", "modulePath": path, "instanceId": f"module:{path or '$root'}", "moduleType": f"{type(child).__module__}.{type(child).__qualname__}", "sequence": len(calls), "parentCallId": active[-1][1]["callId"] if active else None, "inputs": {name: describe(value) for name, value in bound.arguments.items()}}
            calls.append(call)
            active.append((id(child), call))

        def post(child, args, kwargs, result):
            if not active or active[-1][0] != id(child):
                raise RuntimeError("Module hook nesting could not be reconstructed.")
            _, call = active.pop()
            if isinstance(child, torch.nn.MultiheadAttention) and isinstance(result, tuple):
                ports = {"output": result[0], "weights": result[1]}
            elif isinstance(result, tuple):
                ports = {str(index): item for index, item in enumerate(result)}
            else:
                ports = {"output": result}
            for port, value in ports.items():
                mark(value, {"kind": "call", "modulePath": call["modulePath"], "callId": call["callId"], "portId": port})
            call["outputs"] = {port: describe(value) for port, value in ports.items()}

        for child in model.modules():
            handles.append(child.register_forward_pre_hook(pre, with_kwargs=True))
            handles.append(child.register_forward_hook(post, with_kwargs=True))
        try:
            output = model(**inputs)
        finally:
            for handle in handles:
                handle.remove()
        after = state(model)
        output_description = describe(output)

        def tensors(value):
            if isinstance(value, torch.Tensor):
                return [value]
            if isinstance(value, (tuple, list)):
                return [tensor for item in value for tensor in tensors(item)]
            if isinstance(value, dict):
                return [tensor for item in value.values() for tensor in tensors(item)]
            return []

        differentiable = [tensor for tensor in tensors(output) if tensor.is_floating_point() and tensor.requires_grad]
        if differentiable:
            sum(tensor.sum() for tensor in differentiable).backward()
        gradient_items = []
        for name, value in inputs.items():
            if value.requires_grad:
                gradient_items.append({"kind": "input", "name": name, "status": "observed" if value.grad is not None else "unused", "shape": list(value.grad.shape) if value.grad is not None else None, "finite": bool(torch.isfinite(value.grad).all()) if value.grad is not None else True, "valueDigest": value_hash(value.grad) if value.grad is not None else None})
        for name, value in model.named_parameters():
            if value.requires_grad:
                gradient_items.append({"kind": "parameter", "name": name, "status": "observed" if value.grad is not None else "unused", "shape": list(value.grad.shape) if value.grad is not None else None, "finite": bool(torch.isfinite(value.grad).all()) if value.grad is not None else True, "valueDigest": value_hash(value.grad) if value.grad is not None else None})
        old_values = {entry["key"]: entry["valueDigest"] for entry in before["entries"]}
        changed = [entry["key"] for entry in after["entries"] if old_values.get(entry["key"]) != entry["valueDigest"]]
        return {"mode": mode, "inputs": input_descriptions, "calls": calls, "outputs": output_description, "finite": all(bool(torch.isfinite(tensor.detach()).all()) for tensor in tensors(output)), "state": {"before": before, "after": after, "mutatedKeys": changed}, "gradients": {"status": "observed" if differentiable else "not_applicable", "objective": "sum of floating differentiable output elements", "items": gradient_items, "finite": all(item["finite"] for item in gradient_items)}}

    def project(value, exclude):
        if isinstance(value, dict):
            return {key: project(item, exclude) for key, item in value.items() if key not in exclude}
        if isinstance(value, list):
            return [project(item, exclude) for item in value]
        return value

    modes = []
    for mode in spec["modes"]:
        original, replay = one_pass(mode), one_pass(mode)
        original["replay"] = {"structureEqual": project(original["calls"], {"valueDigest", "tensorId", "producer", "producerHistory"}) == project(replay["calls"], {"valueDigest", "tensorId", "producer", "producerHistory"}), "bindingsEqual": project(original["calls"], {"valueDigest"}) == project(replay["calls"], {"valueDigest"}), "outputEqual": original["outputs"] == replay["outputs"], "gradientsEqual": original["gradients"] == replay["gradients"], "stateEqual": original["state"] == replay["state"], "claim": "Fresh construction with the same seed and input sample; exact CPU equality only, not old/new numerical equivalence or all-input determinism."}
        modes.append(original)
    return {"success": True, "observation": {"modes": modes, "coverage": "only declared modes and named frozen generated inputs", "seed": spec["seed"], "checkpointLoaded": False}}


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    apply_limits(request["limits"])
    if request["action"] == "probe":
        return probe(request)
    import torch
    torch.set_num_threads(1)
    if request["action"] == "environment":
        return environment(request, torch)
    return observe(request, torch)


if __name__ == "__main__":
    try:
        result = main()
    except BaseException as exc:
        result = {"success": False, "reason": f"{type(exc).__name__}: {str(exc)[:2000]}"}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
