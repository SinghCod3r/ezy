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
from .errors import EzyRuntimeError, EzySyntaxError, EzyCliArgumentError, EzyCliHelpRequest, EzyCliArgumentError, EzyCliHelpRequest, EzyCliArgumentError, EzyCliHelpRequest
from .interpreter import Interpreter
from .parser import parse
from .linter import lint_program

EXIT_OK = 0
EXIT_SYNTAX_ERROR = 1
EXIT_RUNTIME_ERROR = 2
EXIT_USAGE = 64
EXIT_INTERRUPTED = 130

USAGE = """Ezy {version}

Usage:
  ezy run <script.ezy> [args...]   Run a script
  ezy check <script.ezy>           Check a script for syntax errors\n  ezy fmt [--check] <file.ezy>     Format a script
  ezy lint <file.ezy>              Lint a script for potential bugs
  ezy repl                         Start an interactive session
  ezy --version                    Print the version
  ezy --help                       Show this message

If no subcommand is given and a file is provided, it is run directly:
  ezy script.ezy [args...]
""".format(version=__version__)



def _format_error(exc: Exception) -> str:
    if isinstance(exc, EzySyntaxError):
        title = f"Syntax Error: {exc.message}"
        filename = exc.filename
        line = exc.line
        col = exc.col
    elif isinstance(exc, EzyRuntimeError):
        title = f"{exc.error_type}: {exc.message}"
        filename = exc.filename
        line = getattr(exc, "line", 0)
        col = getattr(exc, "col", 0)
    else:
        return str(exc)

    if not filename or line <= 0:
        return f"Error: {title}"

    out = f"Error: {title}\n\n  {filename}:{line}:{col}\n\n"

    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if 1 <= line <= len(lines):
            source_line = lines[line - 1]
            out += f"  {line} | {source_line}\n"
            if col > 0:
                indent = " " * (len(str(line)) + 3 + col - 1)
                out += f"  {indent}^\n"
    except Exception:
        pass

    return out.rstrip()

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
        print(_format_error(exc), file=sys.stderr)
        return EXIT_SYNTAX_ERROR
    interp = Interpreter(filename=path, script_dir=os.path.dirname(os.path.abspath(path)) or ".")
    interp.arguments = script_args
    try:
        interp.run(program)

    except EzyCliHelpRequest as exc:
        print(exc.help_text)
        return 0
    except EzyCliArgumentError as exc:
        print(f"error: {exc.message}\n", file=sys.stderr)
        print(exc.usage, file=sys.stderr)
        return 2

    except EzyCliHelpRequest as exc:
        print(exc.help_text)
        return 0
    except EzyCliArgumentError as exc:
        print(f"error: {exc.message}\n", file=sys.stderr)
        print(exc.usage, file=sys.stderr)
        return 2
    except EzyRuntimeError as exc:
        if not getattr(exc, "filename", ""):
            exc.filename = path
        print(_format_error(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except KeyboardInterrupt:
        print("\nezy: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    return 0


def check_file(path: str) -> int:
    source = _read_source(path)
    try:
        parse(source, path)
    except EzySyntaxError as exc:
        print(_format_error(exc), file=sys.stderr)
        return EXIT_SYNTAX_ERROR
    print(f"{path}: OK")
    return 0




def lint_file(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"ezy: cannot read file '{path}': {e}", file=sys.stderr)
        return EXIT_FILE_ERROR

    try:
        program = parse(source, path)
    except EzySyntaxError as e:
        print(_format_error(e), file=sys.stderr)
        return EXIT_SYNTAX_ERROR

    findings = lint_program(program, path)
    if not findings:
        return 0

    has_error = False
    for finding in findings:
        print(str(finding))
        if finding.severity == "error":
            has_error = True

    return 2 if has_error else 0

def format_file(path: str, check_only: bool) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"ezy: file not found: {path}", file=sys.stderr)
        return 1

    try:
        from .formatter import format_source
        from .linter import lint_program
        from .parser import parse
        parse(source, path)
        formatted = format_source(source, path)
        parse(formatted, path)
    except EzySyntaxError as exc:
        if not getattr(exc, "filename", ""):
            exc.filename = path
        print(_format_error(exc), file=sys.stderr)
        return 1

    if check_only:
        if source != formatted:
            print(f"File {path} requires formatting.", file=sys.stderr)
            return 1
        else:
            print(f"File {path} is already formatted.")
            return 0
    else:
        if source != formatted:
            with open(path, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"Formatted {path}")
        else:
            print(f"Unchanged {path}")
        return 0

def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv[0] in ("-v", "--version"):
        print(f"Ezy {__version__}")
        return 0
    if argv[0] == "repl":
        from .repl import run_repl
        return run_repl()
    if argv[0] == "fmt":
        if len(argv) < 2:
            print("Usage: ezy fmt [--check] <file.ezy>")
            return EXIT_USAGE
        if argv[1] == "--check":
            if len(argv) < 3:
                print("Usage: ezy fmt --check <file.ezy>")
                return EXIT_USAGE
            return format_file(argv[2], check_only=True)
        return format_file(argv[1], check_only=False)
    if argv[0] == "lint":
        if len(argv) < 2:
            print("ezy: 'lint' requires a file path", file=sys.stderr)
            return EXIT_USAGE
        return lint_file(argv[1])
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
