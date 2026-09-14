"""Interactive REPL.

Supports multi-line blocks: if a line ends with a colon-free block opener
(if/for/while/repeat/function/try/parallel) the REPL keeps reading indented
lines until a blank line ends the block, then parses and runs the whole
accumulated chunk at once. This keeps the REPL's parsing identical to
script parsing rather than maintaining a second grammar.
"""

from __future__ import annotations

import atexit
import os

from . import __version__
from .errors import EzyRuntimeError, EzySyntaxError
from .interpreter import Interpreter
from .parser import parse

BLOCK_OPENERS = ("if ", "for ", "while ", "repeat ", "function ", "try", "parallel")

HISTORY_FILE = os.path.expanduser("~/.ezy_history")


def _setup_history():
    try:
        import readline
        if os.path.exists(HISTORY_FILE):
            readline.read_history_file(HISTORY_FILE)
        atexit.register(readline.write_history_file, HISTORY_FILE)
    except ImportError:
        pass


def run_repl() -> int:
    _setup_history()
    print(f"Ezy {__version__} — interactive mode. Type 'exit' to quit.")
    interp = Interpreter(filename="<repl>", script_dir=os.getcwd())
    buffer = ""
    prompt = "> "
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not buffer and line.strip() in ("exit", "quit"):
            return 0
        if not buffer and not line.strip():
            continue
        needs_more = line.rstrip().endswith((":",)) or any(
            line.strip().startswith(op.strip()) for op in BLOCK_OPENERS
        )
        buffer += line + "\n"
        if needs_more or (buffer.strip() and line.startswith((" ",))):
            prompt = ". "
            continue
        source = buffer
        buffer = ""
        prompt = "> "
        try:
            program = parse(source, "<repl>")
            interp.run(program)
        except EzySyntaxError as exc:
            print(f"syntax error: {exc.message}")
        except EzyRuntimeError as exc:
            print(f"{exc.error_type}: {exc.message}")
    return 0
