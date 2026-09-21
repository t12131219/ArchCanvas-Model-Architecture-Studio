"""Validate an explicitly selected interpreter and lockfile without installing dependencies."""

from __future__ import annotations

import os
from pathlib import Path

from archcanvas_core.models.engine import EngineEnvironment

from .service_errors import EngineRejected


class EnvironmentResolver:
    """Accept only an executable interpreter and an optional approved-root lockfile."""

    def resolve(self, environment: EngineEnvironment, approved_root: Path) -> EngineEnvironment:
        executable = Path(environment.python_executable)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise EngineRejected("PYTHON_EXECUTABLE_INVALID", str(executable))
        if environment.dependency_lockfile is not None:
            lockfile = (approved_root / environment.dependency_lockfile).resolve(strict=False)
            if not lockfile.is_file() or not lockfile.is_relative_to(approved_root):
                raise EngineRejected("DEPENDENCY_LOCKFILE_NOT_APPROVED", environment.dependency_lockfile)
        return environment
