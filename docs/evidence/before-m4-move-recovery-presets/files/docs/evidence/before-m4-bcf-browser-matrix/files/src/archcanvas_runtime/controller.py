"""Control-plane code. User Python is executed only by the isolated worker.

Bubblewrap's namespaces and a kernel seccomp filter are mandatory, not a
best-effort subprocess fallback. A fresh isolation probe precedes every request.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from archcanvas_python.frontend import analyze_project, digest


class RuntimeProfileError(ValueError):
    """An invalid explicit execution profile; no model execution occurred."""


def normalize_input_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"schemaVersion", "inputs", "constructor", "seed", "modes"}:
        raise RuntimeProfileError("Input spec must contain only schemaVersion, inputs, constructor, seed and modes.")
    if value.get("schemaVersion") != 1 or not isinstance(value.get("inputs"), dict) or not 1 <= len(value["inputs"]) <= 16:
        raise RuntimeProfileError("Input spec v1 requires 1–16 named inputs.")
    if value.get("constructor", {}) != {}:
        raise RuntimeProfileError("This structural profile supports only the source-declared default constructor.")
    seed = value.get("seed", 0)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise RuntimeProfileError("Seed must be an integer in [0, 2**32).")
    modes = value.get("modes")
    if not isinstance(modes, list) or not modes or len(set(modes)) != len(modes) or any(mode not in ("eval", "train") for mode in modes):
        raise RuntimeProfileError("Declare a unique nonempty modes list containing eval and/or train.")
    inputs = {}
    total = 0
    for name, spec in sorted(value["inputs"].items()):
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(spec, dict) or set(spec) - {"shape", "dtype", "fill"}:
            raise RuntimeProfileError("Each named input requires shape, dtype and optional fill.")
        shape, dtype = spec.get("shape"), spec.get("dtype")
        if not isinstance(shape, list) or not 1 <= len(shape) <= 8 or any(type(n) is not int or not 1 <= n <= 8192 for n in shape):
            raise RuntimeProfileError("Input shape must have 1–8 positive bounded integer dimensions.")
        if dtype not in ("float32", "float64", "int64", "bool"):
            raise RuntimeProfileError("Supported CPU input dtypes: float32, float64, int64, bool.")
        fill = spec.get("fill", "normal" if dtype.startswith("float") else "zeros")
        if fill not in ("normal", "zeros", "ones") or (fill == "normal" and not dtype.startswith("float")):
            raise RuntimeProfileError("Fill must be normal for floating inputs, zeros or ones.")
        count = 1
        for n in shape:
            count *= n
        total += count
        if total > 1_000_000:
            raise RuntimeProfileError("Input allocation budget exceeded: 1,000,000 elements.")
        inputs[name] = {"shape": shape, "dtype": dtype, "fill": fill}
    return {"schemaVersion": 1, "inputs": inputs, "constructor": {}, "seed": seed, "modes": modes}


def _config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"interpreter", "dependencyLock", "timeoutSeconds", "memoryMb", "cpuSeconds", "cancelEvent"}:
        raise RuntimeProfileError("Runtime config requires explicit interpreter/dependencyLock and bounded resource settings.")
    result = {}
    for key in ("interpreter", "dependencyLock"):
        path = value.get(key)
        if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
            raise RuntimeProfileError(f"{key} must name an existing absolute file.")
        result[key] = path
    for key, default, maximum in (("timeoutSeconds", 20, 120), ("memoryMb", 4096, 8192), ("cpuSeconds", 20, 120)):
        n = value.get(key, default)
        minimum = 128 if key == "memoryMb" else 1
        if type(n) is not int or not minimum <= n <= maximum:
            raise RuntimeProfileError(f"{key} must be an integer in [{minimum}, {maximum}].")
        result[key] = n
    event = value.get("cancelEvent")
    if event is not None and (not callable(getattr(event, "is_set", None))):
        raise RuntimeProfileError("cancelEvent must provide is_set().")
    result["cancelEvent"] = event
    return result


def _environment(config: dict[str, Any]) -> dict[str, Any]:
    interpreter = Path(config["interpreter"]).absolute()
    env_dir = interpreter.parent.parent
    cfg = env_dir / "pyvenv.cfg"
    if not cfg.is_file() or "include-system-site-packages = false" not in cfg.read_text():
        raise RuntimeProfileError("Runtime interpreter must belong to an isolated virtual environment without system site packages.")
    cfg_values = dict(line.split(" = ", 1) for line in cfg.read_text().splitlines() if " = " in line)
    executable = Path(cfg_values.get("executable", str(interpreter.resolve()))).resolve()
    base = executable.parent.parent
    if not executable.is_file() or not interpreter.resolve().is_relative_to(base) or base in (Path("/"), Path("/home"), Path("/home/fzg")):
        raise RuntimeProfileError("Cannot identify a narrow base interpreter mount.")
    raw_lock = Path(config["dependencyLock"]).read_bytes()
    if len(raw_lock) > 50_000:
        raise RuntimeProfileError("Dependency lock exceeds 50 KB.")
    pins = {}
    for line in raw_lock.decode("utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9+_.-]+)", text)
        if not match:
            raise RuntimeProfileError("Dependency lock must contain exact name==version pins only.")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in pins:
            raise RuntimeProfileError("Duplicate dependency lock package.")
        pins[name] = match[2]
    if "torch" not in pins or not pins["torch"].endswith("+cpu"):
        raise RuntimeProfileError("This profile requires an explicitly locked CPU PyTorch build.")
    def file_digest(path):
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(block)
        return value.hexdigest()

    # Version strings cannot freeze a mutable installation. Hash the installed
    # runtime bytes, its config and the trusted adapter/filter implementation.
    package_files = []
    for path in sorted(env_dir.rglob("*")):
        if path.is_file():
            package_files.append({"path": path.relative_to(env_dir).as_posix(), "digest": file_digest(path)})
    version = cfg_values.get("version", "").split(".")[:2]
    if len(version) != 2 or version[0] != "3" or not version[1].isdigit() or int(version[1]) < 11:
        raise RuntimeProfileError("An explicit Python >=3.11 runtime is required.")
    stdlib = base / "lib" / ("python" + ".".join(version))
    if not stdlib.is_dir():
        raise RuntimeProfileError("Cannot identify the base standard library.")
    stdlib_files = []
    extension_roots = []
    for path in sorted(stdlib.rglob("*")):
        if "site-packages" in path.relative_to(stdlib).parts:
            continue
        if path.is_file():
            if not path.resolve().is_relative_to(stdlib):
                raise RuntimeProfileError("Base standard library contains an external symlink.")
            stdlib_files.append({"path": path.relative_to(stdlib).as_posix(), "digest": file_digest(path)})
            if path.suffix == ".so":
                extension_roots.append(path)
    extension_roots.extend(path for path in env_dir.rglob("*.so*") if path.is_file() and (path.suffix == ".so" or ".so." in path.name))
    dependencies = _dependency_closure([executable, *extension_roots], base, env_dir, file_digest)
    hidden = next((path for path in (base / "conda-meta/history", base / "bin/pip", stdlib / "site-packages") if path.exists()), base / "conda-meta")
    return {"interpreter": str(interpreter), "virtualEnvironment": str(env_dir), "basePrefix": str(base), "executable": str(executable), "executableDigest": file_digest(executable), "virtualEnvironmentContentDigest": digest(package_files), "virtualEnvironmentFileCount": len(package_files), "venvConfigDigest": digest(cfg.read_bytes()), "stdlibPath": str(stdlib), "stdlibContentDigest": digest(stdlib_files), "stdlibFileCount": len(stdlib_files), "sharedLibraryMounts": dependencies, "sharedLibraryContentDigest": digest(dependencies), "baseHiddenProbe": str(hidden), "baseHiddenProbeExists": hidden.exists(), "workerDigest": file_digest(Path(__file__).with_name("worker.py")), "controllerDigest": file_digest(Path(__file__)), "seccompDigest": digest(_seccomp()), "dependencyLockDigest": digest(raw_lock), "dependencyPins": pins, "backend": "pytorch", "device": "cpu", "environmentFreezeScope": "all venv files including bytecode, resolved Python executable, standard library excluding base site-packages, ELF dependency closure, config, dependency lock and trusted adapter; executable/stdlib/ELF mounts are private read-only copies, venv bytes are rechecked after execution"}


def _dependency_closure(roots, base, env_dir, file_digest):
    """Read ELF metadata as data; never execute ldd or a model's libraries."""
    if not Path("/usr/bin/readelf").is_file():
        raise RuntimeProfileError("Trusted ELF dependency inspection is unavailable.")
    system_dirs = [Path("/lib/x86_64-linux-gnu"), Path("/usr/lib/x86_64-linux-gnu"), Path("/lib64")]
    seen, pending, mounts = set(), list(roots), {}
    # ELF interpreter is a program-header dependency, not DT_NEEDED.
    loader = Path("/lib64/ld-linux-x86-64.so.2")
    if not loader.is_file():
        raise RuntimeProfileError("Verified x86-64 ELF interpreter is unavailable.")
    mounts[str(loader)] = {"path": str(loader), "digest": file_digest(loader)}
    while pending:
        path = pending.pop()
        identity = path.resolve()
        if identity in seen:
            continue
        seen.add(identity)
        result = subprocess.run(["/usr/bin/readelf", "-d", str(path)], capture_output=True, text=True, timeout=3, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        if result.returncode:
            raise RuntimeProfileError(f"Cannot inspect a locked ELF runtime dependency: {path.name}")
        rpaths = []
        for raw in re.findall(r"\((?:RUNPATH|RPATH)\).*?\[([^\]]+)\]", result.stdout):
            for value in raw.split(":"):
                value = value.replace("${ORIGIN}", str(path.parent)).replace("$ORIGIN", str(path.parent))
                if not value or "$" in value or not Path(value).is_absolute():
                    raise RuntimeProfileError("Unsupported runtime ELF search path.")
                rpaths.append(Path(os.path.normpath(value)))
        for name in re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", result.stdout):
            if "/" in name or name in (".", ".."):
                raise RuntimeProfileError("Unsupported ELF dependency path.")
            dependency = next((directory / name for directory in (*rpaths, *system_dirs) if (directory / name).is_file()), None)
            if dependency is None:
                raise RuntimeProfileError(f"Locked ELF dependency is missing: {name}")
            pending.append(dependency)
            if not dependency.resolve().is_relative_to(env_dir):
                mounts[str(dependency)] = {"path": str(dependency), "digest": file_digest(dependency)}
    return [mounts[path] for path in sorted(mounts)]


def _prepare_base(environment, temporary):
    """Stage narrow immutable interpreter/stdlib/library mounts once per job."""
    snapshot = temporary / "base-snapshot"
    if snapshot.exists():
        return snapshot
    snapshot.mkdir()
    shutil.copyfile(environment["executable"], snapshot / "python")
    os.chmod(snapshot / "python", 0o555)
    if digest((snapshot / "python").read_bytes()) != environment["executableDigest"]:
        raise RuntimeProfileError("Python executable changed while freezing its snapshot.")
    shutil.copytree(environment["stdlibPath"], snapshot / "stdlib", ignore=shutil.ignore_patterns("site-packages"))
    stdlib_files = [{"path": path.relative_to(snapshot / "stdlib").as_posix(), "digest": digest(path.read_bytes())} for path in sorted((snapshot / "stdlib").rglob("*")) if path.is_file()]
    if digest(stdlib_files) != environment["stdlibContentDigest"]:
        raise RuntimeProfileError("Python standard library changed while freezing its snapshot.")
    for index, dependency in enumerate(environment["sharedLibraryMounts"]):
        destination = snapshot / f"library-{index}"
        shutil.copyfile(dependency["path"], destination)
        os.chmod(destination, 0o555)
        if digest(destination.read_bytes()) != dependency["digest"]:
            raise RuntimeProfileError("Runtime library changed while freezing its snapshot.")
    return snapshot


def _limits(settings):
    return {"wallSeconds": settings["timeoutSeconds"], "cpuSeconds": settings["cpuSeconds"], "addressSpaceBytes": settings["memoryMb"] * 1024**2, "fileBytes": 8_000_000, "openFiles": 64, "modelTaskLimit": 1, "torchThreads": 1, "uidTaskLimit": 256, "threadLimitScope": "RLIMIT_NPROC counts all tasks for the real host UID; seccomp separately denies new processes", "memoryScope": "per-process virtual address space; no cgroup RSS or aggregate tmpfs quota"}


def runtime_capabilities(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Probe only trusted infrastructure; never import a user's model."""
    result = {"available": False, "structuralVerified": False, "status": "unavailable"}
    try:
        settings = _config(config)
        environment = _environment(settings)
        limits = _limits(settings)
        with tempfile.TemporaryDirectory(prefix="archcanvas-capability-") as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            (source / "probe.py").write_text("# Trusted read-only mount probe, never imported.\n")
            sentinel = temporary / "host-sentinel"
            sentinel.write_text("private host file")
            request = {"limits": limits, "environment": environment, "hostNamespaces": {name: os.readlink(f"/proc/self/ns/{name}") for name in ("mnt", "net", "pid", "user")}, "hostSentinel": str(sentinel), "sourceProbe": "probe.py"}
            isolation, error = _execute(environment, temporary, source, {**request, "action": "probe"}, settings)
            result["isolation"] = isolation or {"available": False, "reason": error}
            if not isolation or not isolation.get("available"):
                result["unavailableReason"] = error or (isolation or {}).get("reason", "Mandatory kernel probes failed.")
                return result
            description, error = _execute(environment, temporary, source, {**request, "action": "environment"}, settings)
            if not description or not description.get("valid"):
                result["unavailableReason"] = error or (description or {}).get("reason", "Dependency lock validation failed.")
                return result
            environment.update(description["environment"])
        result.update(available=True, structuralVerified=True, status="passed", environment=environment, environmentDigest=digest(environment), limits=limits)
    except (RuntimeProfileError, OSError) as exc:
        result["unavailableReason"] = str(exc)
    return result


def fresh_binding(config: dict[str, Any]) -> dict[str, Any]:
    """Rehash actual runtime bytes and rerun trusted kernel/environment probes."""
    return runtime_capabilities(config)


capabilities = runtime_capabilities


def _seccomp() -> bytes:
    """x86-64 classic BPF: prohibit all new tasks, sockets and namespace escape.

    clone permits CLONE_THREAD only. clone3 ENOSYS permits libc to fall back to
    the inspectable clone ABI. No user process can spawn; NPROC bounds threads.
    """
    if platform.machine() != "x86_64":
        raise RuntimeProfileError("Kernel seccomp policy is currently verified only on Linux x86-64.")
    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    for syscall in (41, 53, 57, 58, 101, 155, 165, 166, 272, 308, 310, 311, 321, 323):
        instructions.extend(((0x15, 0, 1, syscall), (0x06, 0, 0, 0x00050000 | 1)))
    instructions.extend(((0x15, 0, 1, 435), (0x06, 0, 0, 0x00050000 | 38)))
    # clone flags must include CLONE_THREAD (0x10000). Only the low word is
    # relevant for this flag. Reload syscall number for the x32 guard below.
    instructions.extend(((0x15, 0, 4, 56), (0x20, 0, 0, 16), (0x45, 1, 0, 0x10000), (0x06, 0, 0, 0x00050000 | 1), (0x06, 0, 0, 0x7FFF0000), (0x20, 0, 0, 0)))
    # Also reject x32 ABI syscall numbers: same AUDIT_ARCH value, different ABI.
    instructions.extend(((0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x00050000 | 1), (0x06, 0, 0, 0x7FFF0000)))
    return b"".join(struct.pack("HBBI", *instruction) for instruction in instructions)


def _command(environment: dict[str, Any], temporary: Path, request: Path, source: Path, seccomp_fd: int) -> list[str]:
    command = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--cap-drop", "ALL", "--clearenv"]
    snapshot = _prepare_base(environment, temporary)
    command.extend(("--ro-bind", str(snapshot / "python"), environment["executable"], "--ro-bind", str(snapshot / "stdlib"), environment["stdlibPath"], "--ro-bind", environment["virtualEnvironment"], environment["virtualEnvironment"]))
    for index, dependency in enumerate(environment["sharedLibraryMounts"]):
        command.extend(("--ro-bind", str(snapshot / f"library-{index}"), dependency["path"]))
    command.extend(("--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/work", "--ro-bind", str(source), "/model", "--ro-bind", str(Path(__file__).with_name("worker.py")), "/worker.py", "--ro-bind", str(request), "/request.json", "--chdir", "/work"))
    for key, value in {"HOME": "/work", "TMPDIR": "/tmp", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}.items():
        command.extend(("--setenv", key, value))
    command.extend(("--seccomp", str(seccomp_fd), environment["interpreter"], "-I", "-B", "/worker.py", "/request.json"))
    return command


def _execute(environment: dict[str, Any], temporary: Path, source: Path, request_data: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    request = temporary / "request.json"
    request.write_text(json.dumps(request_data, sort_keys=True, allow_nan=False))
    policy = temporary / "seccomp.bpf"
    policy.write_bytes(_seccomp())
    output_path, error_path = temporary / "stdout", temporary / "stderr"
    with policy.open("rb") as policy_file, output_path.open("wb") as output, error_path.open("wb") as error:
        command = _command(environment, temporary, request, source, policy_file.fileno())
        process = subprocess.Popen(command, stdout=output, stderr=error, pass_fds=(policy_file.fileno(),), start_new_session=True)
        deadline = time.monotonic() + config["timeoutSeconds"]
        reason = ""
        while process.poll() is None:
            if config["cancelEvent"] is not None and config["cancelEvent"].is_set():
                reason = "cancelled"
            elif time.monotonic() >= deadline:
                reason = "wall timeout"
            if reason:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                break
            time.sleep(0.02)
    if reason:
        return None, reason
    stderr = error_path.read_bytes()[:4000].decode("utf-8", errors="replace")
    if process.returncode:
        return None, f"worker exit {process.returncode}: {stderr}"
    raw = output_path.read_bytes()
    if len(raw) > 8_000_000:
        return None, "worker output budget exceeded"
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("not an object")
        return result, ""
    except (ValueError, UnicodeDecodeError):
        return None, "worker did not return a single valid JSON receipt"


def verify_structural(root: str | Path, entry: str, input_spec: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit isolated forward/backward and same-seed structural replay.

    Successful execution is sample-scoped. Transactions must separately compare
    these observations with their independently frozen expected structural delta.
    No checkpoint or optimizer state is loaded, written, or migrated.
    """
    spec = normalize_input_spec(input_spec)
    architecture = analyze_project(root, entry)
    receipt: dict[str, Any] = {"schemaVersion": 1, "profile": "structural-verified", "status": "unavailable", "sourceDigest": architecture["sourceDigest"], "testedIRDigest": architecture["irDigest"], "inputSpecDigest": digest(spec), "runtimeVerified": False, "limitations": ["Frozen CPU samples do not establish numerical equivalence or complete path coverage.", "Hooks observe module calls; arbitrary functional operations may have unresolved producer identities.", "Source and instrumentation share a Python process; supported semantic writes require a separate static contract/oracle."]}
    try:
        settings = _config(config)
    except RuntimeProfileError as exc:
        receipt["reason"] = str(exc)
        return receipt
    if settings["cancelEvent"] is not None and settings["cancelEvent"].is_set():
        receipt.update(status="failed", reason="cancelled")
        return receipt
    try:
        environment = _environment(settings)
        if platform.system() != "Linux" or not Path("/usr/bin/bwrap").is_file():
            raise RuntimeProfileError("Verified Linux Bubblewrap isolation is unavailable; runtime profile disabled.")
        _seccomp()
    except RuntimeProfileError as exc:
        receipt["reason"] = str(exc)
        return receipt
    limits = _limits(settings)
    frozen_environment_binding = digest(environment)
    receipt["manifest"] = {"inputSpec": spec, "constructor": {}, "environment": environment, "limits": limits, "observationMechanism": "PyTorch forward pre/post hooks, fresh same-seed reconstruction, autograd backward", "sourceGeneration": [{"path": file["path"], "digest": file["digest"]} for file in architecture["sources"]]}
    with tempfile.TemporaryDirectory(prefix="archcanvas-runtime-") as directory:
        temporary = Path(directory)
        source = temporary / "source"
        source.mkdir()
        for file in architecture["sources"]:
            path = Path(file["path"])
            if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
                raise RuntimeProfileError("Frozen source manifest contains an unsafe logical path.")
            destination = source / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            original = Path(root).resolve() / path
            raw = original.read_bytes()
            if digest(raw) != file["digest"]:
                receipt.update(status="failed", reason="source changed while freezing the runtime generation")
                return receipt
            destination.write_bytes(raw)
        sentinel = temporary / "host-only-sentinel"
        sentinel.write_text("This must never be visible inside the worker.")
        base_request = {"limits": limits, "environment": environment, "hostNamespaces": {name: os.readlink(f"/proc/self/ns/{name}") for name in ("mnt", "net", "pid", "user")}, "hostSentinel": str(sentinel), "sourceProbe": architecture["sources"][0]["path"]}
        probe, error = _execute(environment, temporary, source, {**base_request, "action": "probe"}, settings)
        if not probe or not probe.get("available"):
            if error == "cancelled":
                receipt["status"] = "failed"
            receipt["reason"] = error or (probe or {}).get("reason", "Mandatory kernel isolation probes failed.")
            receipt["manifest"]["isolation"] = probe or {"available": False, "reason": error}
            return receipt
        receipt["manifest"]["isolation"] = probe
        description, error = _execute(environment, temporary, source, {**base_request, "action": "environment"}, settings)
        if not description or not description.get("valid"):
            if error == "cancelled":
                receipt["status"] = "failed"
            receipt["reason"] = error or (description or {}).get("reason", "Runtime dependency environment did not match its lock.")
            return receipt
        environment.update(description["environment"])
        receipt["environmentDigest"] = digest(environment)
        result, error = _execute(environment, temporary, source, {**base_request, "environment": environment, "action": "observe", "entry": entry, "inputSpec": spec}, settings)
        if not result:
            receipt.update(status="failed", reason=error)
            return receipt
        if not result.get("success"):
            receipt.update(status="failed", reason=result.get("reason", "Model execution failed."))
            return receipt
        if digest(_environment(settings)) != frozen_environment_binding:
            receipt.update(status="failed", reason="Runtime environment bytes changed during execution.")
            return receipt
        receipt["observation"] = result["observation"]
        receipt["stateCompatibility"] = {"status": "observed", "strategy": "fresh default construction; no checkpoint loading or migration", "checkpoint": "not_provided", "optimizer": "not_provided", "scheduler": "not_provided", "trainingProgress": "not_provided", "randomState": "profile seed reset per replay; no external training RNG restored", "sourceVsCheckpointCompatibility": "unknown"}
        checks = all(mode["finite"] and all(mode["replay"][key] for key in ("structureEqual", "bindingsEqual", "outputEqual", "gradientsEqual", "stateEqual")) and mode["gradients"]["finite"] for mode in result["observation"]["modes"])
        receipt.update(status="passed" if checks else "failed", runtimeVerified=checks)
        if not checks:
            receipt["reason"] = "Forward/backward finiteness or frozen same-seed replay failed."
        return receipt
