"""Tokenizer for Ezy.

Indentation is significant, similar to Python: blocks are opened by a
trailing ':' or by certain block-starting keywords followed by a newline,
and are delimited with INDENT/DEDENT tokens derived from leading whitespace.
Tabs are rejected to avoid ambiguous indentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from typing import Any, List, Optional

from .errors import EzySyntaxError

KEYWORDS = {
    "and", "or", "not", "true", "false", "null",
    "if", "otherwise", "for", "each", "in", "from", "to",
    "repeat", "times", "while", "break", "continue",
    "function", "return", "say", "use", "try", "catch",
    "create", "folder", "file", "write", "append", "delete",
    "list", "exists", "environment", "set",
    "run", "with", "arguments", "get", "post", "put", "patch",
    "download", "save", "as", "header", "query", "timeout",
    "seconds", "json", "parallel", "matches", "is", "read", "wait", "send",
    "successful", "failed", "let", "const",
}

SYMBOLS = [
    ("->", "ARROW"),
    ("==", "EQ"), ("!=", "NEQ"), ("<=", "LE"), (">=", "GE"),
    ("=", "ASSIGN"), ("<", "LT"), (">", "GT"),
    ("+", "PLUS"), ("-", "MINUS"), ("*", "STAR"), ("/", "SLASH"),
    ("%", "PERCENT"), ("(", "LPAREN"), (")", "RPAREN"),
    ("[", "LBRACKET"), ("]", "RBRACKET"), ("{", "LBRACE"), ("}", "RBRACE"),
    (",", "COMMA"), (":", "COLON"), (".", "DOT"),
]


@dataclass
class Token:
    type: str
    value: Any
    line: int
    col: int
    comments: List[str] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.col})"


class Lexer:
    def __init__(self, source: str, filename: str = "<script>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.indent_stack = [0]
        self.tokens: List[Token] = []
        self.at_line_start = True
        self.paren_depth = 0
        self.pending_comments: List[str] = []

    def error(self, message: str) -> EzySyntaxError:
        return EzySyntaxError(message, self.filename, self.line, self.col)

    def peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else ""

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            if self.at_line_start and self.paren_depth == 0:
                self._handle_indentation()
                if self.pos >= len(self.source):
                    break
            ch = self.peek()
            if ch == "":
                break
            if ch == "\t":
                raise self.error("tabs are not allowed for indentation or spacing; use spaces")
            if ch in " \t":
                self.advance()
                continue
            if ch == "#":
                comment_text = ""
                self.advance() # consume #
                while self.peek() not in ("\n", ""):
                    comment_text += self.advance()
                self.pending_comments.append(comment_text.strip())
                continue
            if ch == "\n":
                nl_line, nl_col = self.line, self.col
                self.advance()
                if self.paren_depth == 0:
                    self._emit("NEWLINE",  "\n", nl_line, nl_col)
                    self.at_line_start = True
                continue
            if ch in ('"', "'"):
                self._read_string(ch)
                continue
            if ch.isdigit():
                self._read_number()
                continue
            if ch.isalpha() or ch == "_":
                self._read_name()
                continue
            self._read_symbol()
        # close open logical line
        if self.tokens and self.tokens[-1].type != "NEWLINE":
            self._emit("NEWLINE", "\n")
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self._emit("DEDENT", "")
        self._emit("EOF", None)
        return self.tokens

    def _emit(self, type_: str, value: Any, line: int = None, col: int = None) -> None:
        line = line if line is not None else self.line
        col = col if col is not None else self.col
        tok = Token(type_, value, line, col)
        if self.pending_comments:
            tok.comments = self.pending_comments
            self.pending_comments = []
        self.tokens.append(tok)

    def _handle_indentation(self) -> None:
        while True:
            width = 0
            while self.peek() == " ":
                self.advance()
                width += 1
            # blank line or comment-only line: skip without affecting indentation
            if self.peek() in ("\n", "#", ""):
                if self.peek() == "#":
                    comment_text = ""
                    self.advance()
                    while self.peek() not in ("\n", ""):
                        comment_text += self.advance()
                    self.pending_comments.append(comment_text.strip())
                if self.peek() == "\n":
                    self.advance()
                    continue
                return  # EOF reached while skipping blank/comment lines
            break
        self.at_line_start = False
        current = self.indent_stack[-1]
        if width > current:
            self.indent_stack.append(width)
            self._emit("INDENT", width)
        else:
            while width < self.indent_stack[-1]:
                self.indent_stack.pop()
                self._emit("DEDENT", "")
            if width != self.indent_stack[-1]:
                raise self.error("inconsistent indentation")

    def _read_string(self, quote: str) -> None:
        line, col = self.line, self.col
        self.advance()
        parts: List[Any] = []
        buf = ""
        while True:
            ch = self.peek()
            if ch == "":
                raise self.error("unterminated string literal")
            if ch == quote:
                self.advance()
                break
            if ch == "\\":
                self.advance()
                esc = self.advance()
                buf += {"n": "\n", "t": "\t", "\\": "\\", '"': '"',
                        "'": "'", "{": "{", "}": "}"}.get(esc, esc)
                continue
            if ch == "{" and self.peek(1) != "{":
                if buf:
                    parts.append(buf)
                    buf = ""
                self.advance()
                depth = 1
                expr_src = ""
                while True:
                    c = self.peek()
                    if c == "":
                        raise self.error("unterminated interpolation in string")
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            self.advance()
                            break
                    expr_src += self.advance()
                parts.append(("expr", expr_src))
                continue
            buf += self.advance()
        if buf or not parts:
            parts.append(buf)
        self._emit("STRING",  parts, line, col)

    def _read_number(self) -> None:
        line, col = self.line, self.col
        buf = ""
        while self.peek().isdigit():
            buf += self.advance()
        is_float = False
        if self.peek() == "." and self.peek(1).isdigit():
            is_float = True
            buf += self.advance()
            while self.peek().isdigit():
                buf += self.advance()
        value = float(buf) if is_float else int(buf)
        self._emit("NUMBER",  value, line, col)

    def _read_name(self) -> None:
        line, col = self.line, self.col
        buf = ""
        while self.peek().isalnum() or self.peek() == "_":
            buf += self.advance()
        type_ = buf if buf in KEYWORDS else "NAME"
        self._emit(type_,  buf, line, col)

    def _read_symbol(self) -> None:
        line, col = self.line, self.col
        if self.source.startswith("\u2192", self.pos):  # → pipeline arrow
            self.pos += 1
            self.col += 1
            self._emit("ARROW",  "->", line, col)
            return
        for sym, name in SYMBOLS:
            if self.source.startswith(sym, self.pos):
                for _ in sym:
                    self.advance()
                if name in ("LPAREN", "LBRACKET", "LBRACE"):
                    self.paren_depth += 1
                elif name in ("RPAREN", "RBRACKET", "RBRACE"):
                    self.paren_depth = max(0, self.paren_depth - 1)
                self._emit(name,  sym, line, col)
                return
        raise self.error(f"unexpected character {self.peek()!r}")


def tokenize(source: str, filename: str = "<script>") -> List[Token]:
    return Lexer(source, filename).tokenize()
