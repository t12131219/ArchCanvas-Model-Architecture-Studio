"""Engine rejection shared by focused lifecycle services."""

from __future__ import annotations


class EngineRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
