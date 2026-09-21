"""Build runtime requests only from a current, approved source identity document."""

from __future__ import annotations

from pathlib import Path

from archcanvas_core.models.runtime import (
    NetworkPolicy,
    RuntimeProviderId,
    RuntimeTensorInput,
    TraceRequest,
)
from archcanvas_core.models.source_identity import SourceIdentityDocument
from archcanvas_python.source_revision import file_revision


class TraceRequestRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TraceRequestFactory:
    """Bind an explicit runtime execution request to the current static source snapshot."""

    def build(
        self,
        *,
        request_id: str,
        project_root: Path,
        source: SourceIdentityDocument,
        entrypoint: str,
        python_executable: str,
        inputs: list[RuntimeTensorInput],
        provider: RuntimeProviderId,
        constructor_kwargs: dict[str, object] | None = None,
        timeout_seconds: int = 30,
        memory_limit_mb: int = 4096,
        network_policy: NetworkPolicy = NetworkPolicy.DENY,
        environment_name: str | None = None,
        dependency_lockfile: str | None = None,
    ) -> TraceRequest:
        try:
            relative_file, _ = entrypoint.split(":", maxsplit=1)
        except ValueError as error:
            raise TraceRequestRejected("INVALID_ENTRYPOINT", "entrypoint must use file.py:ClassName") from error
        root = project_root.resolve(strict=True)
        source_path = (root / relative_file).resolve(strict=False)
        if not source_path.is_file() or not source_path.is_relative_to(root):
            raise TraceRequestRejected("ENTRYPOINT_OUTSIDE_APPROVED_ROOT", relative_file)
        expected_revision = source.file_revisions.get(relative_file)
        if expected_revision is None:
            raise TraceRequestRejected("ENTRYPOINT_NOT_IN_SOURCE_IDENTITY", relative_file)
        if file_revision(source_path.read_bytes()) != expected_revision:
            raise TraceRequestRejected("STALE_SOURCE_IDENTITY", relative_file)
        if dependency_lockfile is not None:
            lock_path = (root / dependency_lockfile).resolve(strict=False)
            if not lock_path.is_file() or not lock_path.is_relative_to(root):
                raise TraceRequestRejected("DEPENDENCY_LOCKFILE_NOT_APPROVED", dependency_lockfile)
        return TraceRequest(
            request_id=request_id,
            project_root=str(root),
            python_executable=python_executable,
            entrypoint=entrypoint,
            entrypoint_file_revision=expected_revision,
            source_revision=source.source_revision,
            environment_name=environment_name,
            dependency_lockfile=dependency_lockfile,
            constructor_kwargs=constructor_kwargs or {},
            inputs=inputs,
            provider=provider,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            network_policy=network_policy,
        )
