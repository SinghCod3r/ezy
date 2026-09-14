"""Runtime value representations.

Primitive Ezy values map directly onto Python values: string -> str,
integer -> int, decimal -> float, boolean -> bool, null -> None,
list -> list, map -> dict (insertion-ordered, string keys). The classes
below cover the values that need extra behavior.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class EzyPath:
    """A filesystem path with a few convenience properties."""

    def __init__(self, raw: str):
        self.raw = raw

    def __str__(self) -> str:
        return self.raw

    def __eq__(self, other) -> bool:
        return isinstance(other, EzyPath) and self.raw == other.raw

    def __hash__(self) -> int:
        return hash(("EzyPath", self.raw))

    @property
    def name(self) -> str:
        return os.path.basename(self.raw)

    @property
    def extension(self) -> str:
        _, ext = os.path.splitext(self.raw)
        return ext[1:] if ext.startswith(".") else ext

    @property
    def parent(self) -> "EzyPath":
        return EzyPath(os.path.dirname(self.raw) or ".")

    @property
    def exists(self) -> bool:
        return os.path.exists(self.raw)


class Function:
    """A user-defined Ezy function (closure over its defining scope)."""

    def __init__(self, name: str, params: List[tuple], body: list, closure):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:  # pragma: no cover
        return f"<function {self.name}>"


class BuiltinFunction:
    def __init__(self, name: str, fn):
        self.name = name
        self.fn = fn

    def __call__(self, *args):
        return self.fn(*args)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<builtin {self.name}>"


@dataclass
class HttpResponse:
    status: int
    text: str
    headers: Dict[str, str]
    url: str
    ok: bool
    error: Optional[str] = None
    elapsed_ms: float = 0.0

    @property
    def json(self):
        import json as _json
        try:
            return _json.loads(self.text)
        except ValueError as exc:
            from .errors import EzyRuntimeError
            raise EzyRuntimeError(f"response body is not valid JSON: {exc}", "JsonError")


@dataclass
class ProcessResult:
    output: str
    error: str
    exit_code: int
    ok: bool
    timed_out: bool = False


class EzyModule:
    """A namespace produced by `use "./file"` (local module import)."""

    def __init__(self, name: str, members: Dict[str, Any]):
        self.name = name
        self.members = members

    def __repr__(self) -> str:  # pragma: no cover
        return f"<module {self.name}>"


class EzyErrorValue:
    """The `error` object bound inside a `catch` block."""

    def __init__(self, type_: str, message: str):
        self.type = type_
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover
        return f"<error {self.type}: {self.message}>"
