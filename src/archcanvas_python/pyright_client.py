from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class PyrightUnavailableError(RuntimeError):
    pass


class PyrightTimeoutError(PyrightUnavailableError):
    pass


class JsonRpcTransport(Protocol):
    def request(self, method: str, params: dict[str, Any]) -> Any: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ResolverQuery:
    method: str
    logical_path: str
    line: int
    column: int
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolverBatchResult:
    status: str
    snapshot: str | None
    results: tuple[Any, ...]
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class ResolverFact:
    query: ResolverQuery
    snapshot: str
    result: Any


def lsp_utf16_column(source: str, line: int, column: int) -> int:
    lines = source.splitlines()
    if line < 0 or line >= len(lines):
        raise ValueError("resolver position line is outside the source file")
    prefix = lines[line][:column]
    return len(prefix.encode("utf-16-le")) // 2


class StdioJsonRpcTransport:
    """Minimal JSON-RPC transport for a pinned Type Server executable."""

    def __init__(
        self,
        executable: Path,
        snapshot_root: Path,
        *,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        executable = executable.resolve()
        snapshot_root = snapshot_root.resolve()
        if not executable.is_file():
            raise PyrightUnavailableError("pyright-typeserver executable is unavailable")
        environment = {
            "PATH": str(executable.parent),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONNOUSERSITE": "1",
        }
        self._process = subprocess.Popen(
            [str(executable), "--stdio"],
            cwd=snapshot_root,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self._process.stdin is None or self._process.stdout is None:
            self._process.kill()
            raise PyrightUnavailableError("pyright-typeserver did not expose stdio")
        self._next_id = 1
        self._lock = threading.Lock()
        self._request_timeout_seconds = request_timeout_seconds
        self._responses: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def request(self, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            message = json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
                separators=(",", ":"),
            ).encode("utf-8")
            assert self._process.stdin is not None
            self._process.stdin.write(f"Content-Length: {len(message)}\r\n\r\n".encode("ascii"))
            self._process.stdin.write(message)
            self._process.stdin.flush()
            deadline = time.monotonic() + self._request_timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.close()
                    raise PyrightTimeoutError(
                        f"Pyright Type Server timed out during {method}"
                    )
                try:
                    response = self._responses.get(timeout=remaining)
                except queue.Empty as error:
                    self.close()
                    raise PyrightTimeoutError(
                        f"Pyright Type Server timed out during {method}"
                    ) from error
                if isinstance(response, Exception):
                    raise PyrightUnavailableError(
                        "Pyright Type Server response reader failed"
                    ) from response
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    raise RuntimeError(f"Pyright Type Server error: {response['error']}")
                return response.get("result")

    def _read_loop(self) -> None:
        try:
            while True:
                self._responses.put(self._read_message())
        except (OSError, RuntimeError, ValueError, UnicodeError) as error:
            self._responses.put(error)

    def _read_message(self) -> dict[str, Any]:
        assert self._process.stdout is not None
        length: int | None = None
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise PyrightUnavailableError("pyright-typeserver closed its output")
            if line in {b"\r\n", b"\n"}:
                break
            name, _, value = line.decode("ascii").partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
        if length is None:
            raise RuntimeError("JSON-RPC response omitted Content-Length")
        payload = self._process.stdout.read(length)
        return json.loads(payload)

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)


class PyrightClient:
    def __init__(
        self,
        transport: JsonRpcTransport,
        snapshot_root: Path,
        *,
        max_snapshot_retries: int = 1,
    ) -> None:
        self.transport = transport
        self.snapshot_root = snapshot_root.resolve()
        self.max_snapshot_retries = max(0, max_snapshot_retries)

    def _snapshot(self) -> str:
        result = self.transport.request("typeServer/getSnapshot", {})
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and isinstance(result.get("snapshot"), str):
            return result["snapshot"]
        raise RuntimeError("Pyright Type Server returned an invalid snapshot")

    def query_batch(self, queries: list[ResolverQuery]) -> ResolverBatchResult:
        last_snapshot: str | None = None
        for _attempt in range(self.max_snapshot_retries + 1):
            try:
                before = self._snapshot()
                results_list: list[Any] = []
                for query in queries:
                    target = self.snapshot_root.joinpath(
                        *query.logical_path.split("/")
                    ).resolve()
                    if not target.is_relative_to(self.snapshot_root):
                        raise ValueError("Pyright query path escapes the frozen snapshot")
                    results_list.append(
                        self.transport.request(
                            query.method,
                            {
                                "file": str(target),
                                "position": {
                                    "line": query.line,
                                    "character": query.column,
                                },
                                **query.extra,
                            },
                        )
                    )
                results = tuple(results_list)
                after = self._snapshot()
            except PyrightTimeoutError:
                return ResolverBatchResult(
                    status="unavailable",
                    snapshot=None,
                    results=(),
                    diagnostic_code="PYRIGHT_TIMEOUT",
                )
            except (OSError, RuntimeError, ValueError, PyrightUnavailableError):
                return ResolverBatchResult(
                    status="unavailable",
                    snapshot=None,
                    results=(),
                    diagnostic_code="PYRIGHT_UNAVAILABLE",
                )
            if before == after:
                return ResolverBatchResult(status="ok", snapshot=before, results=results)
            last_snapshot = after
        return ResolverBatchResult(
            status="discarded",
            snapshot=last_snapshot,
            results=(),
            diagnostic_code="PYRIGHT_SNAPSHOT_CHANGED",
        )

    def close(self) -> None:
        self.transport.close()
