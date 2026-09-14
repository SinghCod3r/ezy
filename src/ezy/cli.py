"""Command-line entry point for the `ezy` executable.

Exit codes (documented in docs/language.md):
  0   success
  1   syntax error
  2   runtime error
  64  invalid CLI usage
  130 interrupted (Ctrl+C / SIGINT)
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from . import __version__
from .errors import EzyRuntimeError, EzySyntaxError
from .interpreter import Interpreter
from .parser import parse

EXIT_OK = 0
EXIT_SYNTAX_ERROR = 1
EXIT_RUNTIME_ERROR = 2
EXIT_USAGE = 64
EXIT_INTERRUPTED = 130

USAGE = """Ezy {version}

Usage:
  ezy run <script.ezy> [args...]   Run a script
  ezy check <script.ezy>           Check a script for syntax errors
  ezy repl                         Start an interactive session
  ezy --version                    Print the version
  ezy --help                       Show this message

If no subcommand is given and a file is provided, it is run directly:
  ezy script.ezy [args...]
""".format(version=__version__)


def _read_source(path: str) -> str:
    if not os.path.exists(path):
        print(f"ezy: no such file: {path}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_file(path: str, script_args: List[str]) -> int:
    source = _read_source(path)
    try:
        program = parse(source, path)
    except EzySyntaxError as exc:
        print(f"ezy: {exc}", file=sys.stderr)
        return EXIT_SYNTAX_ERROR
    interp = Interpreter(filename=path, script_dir=os.path.dirname(os.path.abspath(path)) or ".")
    interp.arguments = script_args
    try:
        interp.run(program)
    except EzyRuntimeError as exc:
        print(f"ezy: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except KeyboardInterrupt:
        print("\nezy: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    return EXIT_OK


def check_file(path: str) -> int:
    source = _read_source(path)
    try:
        parse(source, path)
    except EzySyntaxError as exc:
        print(f"ezy: {exc}", file=sys.stderr)
        return EXIT_SYNTAX_ERROR
    print(f"{path}: OK")
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return EXIT_OK
    if argv[0] in ("-v", "--version"):
        print(f"Ezy {__version__}")
        return EXIT_OK
    if argv[0] == "repl":
        from .repl import run_repl
        return run_repl()
    if argv[0] == "check":
        if len(argv) < 2:
            print("ezy: 'check' requires a file path", file=sys.stderr)
            return EXIT_USAGE
        return check_file(argv[1])
    if argv[0] == "run":
        if len(argv) < 2:
            print("ezy: 'run' requires a file path", file=sys.stderr)
            return EXIT_USAGE
        return run_file(argv[1], argv[2:])
    if argv[0].endswith((".ezy", ".ez")):
        return run_file(argv[0], argv[1:])
    print(f"ezy: unknown command '{argv[0]}'", file=sys.stderr)
    print(USAGE)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
