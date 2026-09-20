"""AST node definitions.

Plain dataclasses are used rather than a visitor-generation framework:
the tree is small and a tree-walking interpreter can dispatch on type
directly, which keeps the implementation readable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


class Node:
    line: int = 0
    col: int = 0
    comments: List[str] = field(default_factory=list)


# ---- Expressions -----------------------------------------------------

@dataclass
class Literal(Node):
    value: Any
    line: int = 0
    col: int = 0


@dataclass
class InterpolatedString(Node):
    parts: List[Any]  # str literals mixed with Node expressions
    line: int = 0
    col: int = 0


@dataclass
class ListLiteral(Node):
    items: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class MapLiteral(Node):
    pairs: List[tuple]  # (Node key, Node value)
    line: int = 0
    col: int = 0


@dataclass
class Identifier(Node):
    name: str
    line: int = 0
    col: int = 0


@dataclass
class UnaryOp(Node):
    op: str
    operand: Node
    line: int = 0
    col: int = 0


@dataclass
class BinaryOp(Node):
    op: str
    left: Node
    right: Node
    line: int = 0
    col: int = 0


@dataclass
class LogicalOp(Node):
    op: str  # and / or
    left: Node
    right: Node
    line: int = 0
    col: int = 0


@dataclass
class Call(Node):
    callee: Node
    args: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class MemberAccess(Node):
    obj: Node
    name: str
    line: int = 0
    col: int = 0


@dataclass
class IndexAccess(Node):
    obj: Node
    index: Node
    line: int = 0
    col: int = 0


@dataclass
class PipelineExpr(Node):
    """A → B → C pipeline; each stage receives the previous value as `it`."""
    stages: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class HttpRequest(Node):
    method: str
    url: Node
    modifiers: List[tuple] = field(default_factory=list)  # (kind, Node)
    line: int = 0
    col: int = 0


@dataclass
class RunProcess(Node):
    command: Node
    modifiers: List[tuple] = field(default_factory=list)
    line: int = 0
    col: int = 0


@dataclass
class ReadFile(Node):
    path: Node
    line: int = 0
    col: int = 0


@dataclass
class FileExistsCheck(Node):
    kind: str  # "file" or "folder"
    path: Node
    line: int = 0
    col: int = 0


@dataclass
class EnvironmentGet(Node):
    name: Node
    line: int = 0
    col: int = 0


@dataclass
class MatchesOp(Node):
    left: Node
    pattern: Node
    line: int = 0
    col: int = 0


# ---- Statements --------------------------------------------------------

@dataclass
class Program(Node):
    statements: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class Assignment(Node):
    target: Node
    value: Node
    declared: Optional[str] = None  # "let" / "const" / None
    line: int = 0
    col: int = 0


@dataclass
class ExprStatement(Node):
    expr: Node
    line: int = 0
    col: int = 0


@dataclass
class SayStatement(Node):
    expr: Node
    line: int = 0
    col: int = 0


@dataclass
class IfStatement(Node):
    condition: Node
    then_body: List[Node]
    elif_clauses: List[tuple]  # (condition, body)
    else_body: Optional[List[Node]]
    line: int = 0
    col: int = 0


@dataclass
class ForEachStatement(Node):
    var_name: str
    iterable: Node
    body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class ForRangeStatement(Node):
    var_name: str
    start: Node
    end: Node
    body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class RepeatStatement(Node):
    count: Node
    body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class WhileStatement(Node):
    condition: Node
    body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class BreakStatement(Node):
    line: int = 0
    col: int = 0


@dataclass
class ContinueStatement(Node):
    line: int = 0
    col: int = 0


@dataclass
class FunctionDef(Node):
    name: str
    params: List[tuple]  # (name, default_expr_or_None)
    body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class ReturnStatement(Node):
    expr: Optional[Node]
    line: int = 0
    col: int = 0


@dataclass
class TryStatement(Node):
    try_body: List[Node]
    error_name: Optional[str]
    catch_body: List[Node]
    line: int = 0
    col: int = 0


@dataclass
class UseStatement(Node):
    module: str
    line: int = 0
    col: int = 0


@dataclass
class CreateFileStatement(Node):
    kind: str  # "file" or "folder"
    path: Node
    line: int = 0
    col: int = 0


@dataclass
class WriteStatement(Node):
    content: Node
    path: Node
    append: bool
    line: int = 0
    col: int = 0


@dataclass
class DeleteStatement(Node):
    kind: str  # "file" or "folder"
    path: Node
    line: int = 0
    col: int = 0


@dataclass
class SetEnvironmentStatement(Node):
    name: Node
    value: Node
    line: int = 0
    col: int = 0


@dataclass
class DownloadStatement(Node):
    url: Node
    save_as: Node
    line: int = 0
    col: int = 0


@dataclass
class ParallelStatement(Node):
    assignments: List[Assignment]
    line: int = 0
    col: int = 0


@dataclass
class WaitStatement(Node):
    duration: Node
    line: int = 0
    col: int = 0

@dataclass
class CliFlag(Node):
    name: str
    alias: Optional[str]
    desc: Optional[str]
    line: int = 0
    col: int = 0

@dataclass
class CliOption(Node):
    name: str
    alias: Optional[str]
    default: Optional[Node]
    required: bool
    desc: Optional[str]
    line: int = 0
    col: int = 0

@dataclass
class CliDef(Node):
    name: str
    desc: Optional[str]
    body: List[Node]
    line: int = 0
    col: int = 0
