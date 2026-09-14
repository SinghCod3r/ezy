"""Error hierarchy for Ezy.

Distinguishing syntax errors from runtime errors matters for exit codes
and for how the CLI formats failures.
"""

from __future__ import annotations


class EzyError(Exception):
    """Base class for all errors surfaced to Ezy programs or the CLI."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EzySyntaxError(EzyError):
    def __init__(self, message: str, filename: str, line: int, col: int):
        self.filename = filename
        self.line = line
        self.col = col
        super().__init__(message)

    def __str__(self) -> str:
        return f"{self.filename}:{self.line}:{self.col}: syntax error: {self.message}"


class EzyRuntimeError(EzyError):
    """Raised for errors that occur while executing a parsed program.

    error_type mirrors what an Ezy script sees as `error.type` inside a
    catch block (e.g. "TypeError", "FileError", "HttpError").
    """

    def __init__(self, message: str, error_type: str = "RuntimeError", line: int = 0):
        self.error_type = error_type
        self.line = line
        super().__init__(message)

    def __str__(self) -> str:
        where = f" (line {self.line})" if self.line else ""
        return f"{self.error_type}: {self.message}{where}"


class EzyControlFlow(Exception):
    """Base for internal non-error control-flow signals (break/continue/return)."""


class BreakSignal(EzyControlFlow):
    pass


class ContinueSignal(EzyControlFlow):
    pass


class ReturnSignal(EzyControlFlow):
    def __init__(self, value):
        self.value = value
