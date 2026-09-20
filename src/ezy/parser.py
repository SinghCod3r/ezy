"""Recursive-descent parser for Ezy.

The grammar deliberately trades some of the "bare predicate" pipeline
syntax sketched in early language notes (e.g. `-> filter age >= 18`)
for explicit function calls over an implicit `it` variable
(`-> filter(it, ...)`). A point-free predicate DSL would need its own
sub-grammar bolted onto expressions, which fragments the language; a
single consistent expression grammar used everywhere is more coherent
and easier to reason about. This is documented in docs/limitations.md.
"""

from __future__ import annotations

from typing import List, Optional

from . import ast_nodes as A
from .errors import EzySyntaxError
from .lexer import KEYWORDS, Lexer, Token

COMPARISON_OPS = {"EQ", "NEQ", "LT", "LE", "GT", "GE"}
ADDITIVE_OPS = {"PLUS", "MINUS"}
MULT_OPS = {"STAR", "SLASH", "PERCENT"}


class Parser:
    def __init__(self, tokens: List[Token], filename: str = "<script>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0

    # -- token helpers ---------------------------------------------------

    def cur(self) -> Token:
        return self.tokens[self.pos]

    def check(self, type_: str) -> bool:
        return self.cur().type == type_

    def check_any(self, *types: str) -> bool:
        return self.cur().type in types

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != "EOF":
            self.pos += 1
        return tok

    def expect(self, type_: str, message: Optional[str] = None) -> Token:
        if not self.check(type_):
            tok = self.cur()
            raise EzySyntaxError(
                message or f"expected {type_} but found {tok.type} ({tok.value!r})",
                self.filename, tok.line, tok.col,
            )
        return self.advance()

    def skip_newlines(self) -> None:
        while self.check("NEWLINE"):
            self.advance()

    # -- entry point -------------------------------------------------------

    def parse_program(self) -> A.Program:
        stmts = []
        self.skip_newlines()
        while not self.check("EOF"):
            stmts.append(self.parse_statement())
            self.skip_newlines()
        return A.Program(stmts)

    def parse_block(self) -> List[A.Node]:
        self.expect("NEWLINE", "expected a new line before an indented block")
        self.expect("INDENT", "expected an indented block")
        stmts = []
        while not self.check("DEDENT") and not self.check("EOF"):
            stmts.append(self.parse_statement())
            self.skip_newlines()
        self.expect("DEDENT")
        return stmts

    # -- statements ----------------------------------------------------

    def parse_statement(self) -> A.Node:
        tok = self.cur()
        line, col = tok.line, tok.col
        if tok.type in ("let", "const"):
            return self.parse_declaration()
        if tok.type == "if":
            return self.parse_if()
        if tok.type == "for":
            return self.parse_for()
        if tok.type == "repeat":
            return self.parse_repeat()
        if tok.type == "while":
            return self.parse_while()
        if tok.type == "break":
            self.advance()
            self.expect("NEWLINE")
            return A.BreakStatement(line=line, col=col)
        if tok.type == "continue":
            self.advance()
            self.expect("NEWLINE")
            return A.ContinueStatement(line=line, col=col)
        if tok.type == "function":
            return self.parse_function_def()
        if tok.type == "return":
            self.advance()
            expr = None
            if not self.check("NEWLINE"):
                expr = self.parse_expression()
            self.expect("NEWLINE")
            return A.ReturnStatement(expr, line=line, col=col)
        if tok.type == "try":
            return self.parse_try()
        if tok.type == "use":
            self.advance()
            name_tok = self.expect("STRING")
            module = "".join(p for p in name_tok.value if isinstance(p, str))
            self.expect("NEWLINE")
            return A.UseStatement(module, line=line, col=col)
        if tok.type == "say":
            self.advance()
            expr = self.parse_expression()
            self.expect("NEWLINE")
            return A.SayStatement(expr, line=line, col=col)
        if tok.type == "create":
            return self.parse_create()
        if tok.type == "write":
            return self.parse_write(append=False)
        if tok.type == "append":
            return self.parse_write(append=True)
        if tok.type == "delete":
            return self.parse_delete_or_expr_statement()
        if tok.type == "set":
            return self.parse_set_environment()
        if tok.type == "download":
            return self.parse_download()
        if tok.type == "parallel":
            return self.parse_parallel()
        if tok.type == "wait":
            self.advance()
            duration = self.parse_expression()
            if self.check("seconds"):
                self.advance()
            self.expect("NEWLINE")
            return A.WaitStatement(duration, line=line, col=col)
        return self.parse_assignment_or_expr_statement()

    def parse_declaration(self) -> A.Node:
        line, col = self.cur().line, self.cur().col
        kind = self.advance().type  # let / const
        name = self.expect("NAME").value
        name_tok = self.expect("NAME")
        name = name_tok.value
        self.expect("ASSIGN")
        value = self.parse_expression()
        self.expect("NEWLINE")
        return A.Assignment(A.Identifier(name, line=line, col=col), value, declared=kind, line=line, col=col)
        return A.Assignment(A.Identifier(name, line=name_tok.line, col=name_tok.col), value, declared=kind, line=line, col=col)

    def parse_assignment_or_expr_statement(self) -> A.Node:
        line, col = self.cur().line, self.cur().col
        expr = self.parse_expression()
        if self.check("ASSIGN"):
            if not isinstance(expr, (A.Identifier, A.MemberAccess, A.IndexAccess)):
                raise EzySyntaxError("invalid assignment target", self.filename, line, self.cur().col)
            self.advance()
            value = self.parse_expression()
            self.expect("NEWLINE")
            return A.Assignment(expr, value, line=line, col=col)
        self.expect("NEWLINE")
        return A.ExprStatement(expr, line=line, col=col)

    def parse_if(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'if'
        condition = self.parse_expression()
        then_body = self.parse_block()
        elif_clauses = []
        else_body = None
        while self.check("otherwise"):
            self.advance()
            if self.check("if"):
                self.advance()
                cond = self.parse_expression()
                body = self.parse_block()
                elif_clauses.append((cond, body))
            else:
                else_body = self.parse_block()
                break
        return A.IfStatement(condition, then_body, elif_clauses, else_body, line=line, col=col)

    def parse_for(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'for'
        if self.check("each"):
            self.advance()
            var_name = self.expect("NAME").value
            self.expect("in")
            iterable = self.parse_expression()
            body = self.parse_block()
            return A.ForEachStatement(var_name, iterable, body, line=line, col=col)
        var_name = self.expect("NAME").value
        self.expect("from")
        start = self.parse_expression()
        self.expect("to")
        end = self.parse_expression()
        body = self.parse_block()
        return A.ForRangeStatement(var_name, start, end, body, line=line, col=col)

    def parse_repeat(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'repeat'
        count = self.parse_expression()
        self.expect("times")
        body = self.parse_block()
        return A.RepeatStatement(count, body, line=line, col=col)

    def parse_while(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'while'
        condition = self.parse_expression()
        body = self.parse_block()
        return A.WhileStatement(condition, body, line=line, col=col)

    def parse_function_def(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'function'
        name = self.expect("NAME").value
        params = []
        if not self.check("NEWLINE"):
            while True:
                pname = self.expect("NAME").value
                default = None
                if self.check("ASSIGN"):
                    self.advance()
                    default = self.parse_or()
                params.append((pname, default))
                if self.check("COMMA"):
                    self.advance()
                    continue
                break
        body = self.parse_block()
        return A.FunctionDef(name, params, body, line=line, col=col)

    def parse_try(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'try'
        try_body = self.parse_block()
        self.expect("catch", "expected 'catch' after a try block")
        error_name = None
        if self.check("NAME"):
            error_name = self.advance().value
        catch_body = self.parse_block()
        return A.TryStatement(try_body, error_name, catch_body, line=line, col=col)

    def parse_create(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'create'
        kind = self.expect_any("file", "folder").type
        path = self.parse_expression()
        self.expect("NEWLINE")
        return A.CreateFileStatement(kind, path, line=line, col=col)

    def parse_write(self, append: bool) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'write' / 'append'
        content = self.parse_expression()
        self.expect("to")
        path = self.parse_expression()
        self.expect("NEWLINE")
        return A.WriteStatement(content, path, append, line=line, col=col)

    def parse_delete_or_expr_statement(self) -> A.Node:
        save = self.pos
        line, col = self.cur().line, self.cur().col
        self.advance()  # 'delete'
        if self.check_any("file", "folder"):
            kind = self.advance().type
            path = self.parse_expression()
            self.expect("NEWLINE")
            return A.DeleteStatement(kind, path, line=line, col=col)
        self.pos = save
        return self.parse_assignment_or_expr_statement()

    def parse_set_environment(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'set'
        self.expect("environment")
        name = self.parse_unary()
        self.expect("ASSIGN")
        value = self.parse_expression()
        self.expect("NEWLINE")
        return A.SetEnvironmentStatement(name, value, line=line, col=col)

    def parse_download(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'download'
        url = self.parse_expression()
        self.expect("NEWLINE")
        self.skip_newlines()
        self.expect("save", "expected 'save as <path>' on the line after 'download'")
        self.expect("as")
        save_as = self.parse_expression()
        self.expect("NEWLINE")
        return A.DownloadStatement(url, save_as, line=line, col=col)

    def parse_parallel(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'parallel'
        self.expect("NEWLINE")
        self.expect("INDENT")
        assignments = []
        while not self.check("DEDENT") and not self.check("EOF"):
            stmt = self.parse_assignment_or_expr_statement()
            if not isinstance(stmt, A.Assignment):
                raise EzySyntaxError(
                    "a 'parallel' block may only contain assignments like 'x = get url'",
                    self.filename, stmt.line, 1,
                )
            assignments.append(stmt)
            self.skip_newlines()
        self.expect("DEDENT")
        return A.ParallelStatement(assignments, line=line, col=col)

    def expect_any(self, *types: str) -> Token:
        if self.cur().type not in types:
            tok = self.cur()
            raise EzySyntaxError(
                f"expected one of {types} but found {tok.type}", self.filename, tok.line, tok.col
            )
        return self.advance()

    # -- expressions -----------------------------------------------------

    def parse_expression(self) -> A.Node:
        return self.parse_pipeline()

    def parse_pipeline(self) -> A.Node:
        first = self.parse_or()
        if not self.check("ARROW"):
            return first
        stages = [first]
        while self.check("ARROW"):
            self.advance()
            stages.append(self.parse_or())
        return A.PipelineExpr(stages, line=first.line, col=first.col)

    def parse_or(self) -> A.Node:
        left = self.parse_and()
        while self.check("or"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            right = self.parse_and()
            left = A.LogicalOp("or", left, right, line=line, col=col)
        return left

    def parse_and(self) -> A.Node:
        left = self.parse_not()
        while self.check("and"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            right = self.parse_not()
            left = A.LogicalOp("and", left, right, line=line, col=col)
        return left

    def parse_not(self) -> A.Node:
        if self.check("not"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            operand = self.parse_not()
            return A.UnaryOp("not", operand, line=line, col=col)
        return self.parse_comparison()

    def parse_comparison(self) -> A.Node:
        left = self.parse_additive()
        if self.check_any(*COMPARISON_OPS):
            op_tok = self.advance()
            right = self.parse_additive()
            left = A.BinaryOp(op_tok.type, left, right, line=op_tok.line, col=op_tok.col)
        elif self.check("matches"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            pattern = self.parse_additive()
            left = A.MatchesOp(left, pattern, line=line, col=col)
        left = self._parse_result_postfix(left)
        return left

    def _parse_result_postfix(self, expr: A.Node) -> A.Node:
        if self.check("is"):
            self.advance()
        if self.check("successful"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            return A.Call(A.Identifier("is_successful", line=line, col=col), [expr], line=line, col=col)
        if self.check("failed"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            return A.Call(A.Identifier("is_failed", line=line, col=col), [expr], line=line, col=col)
        if self.check("exists"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            return A.Call(A.Identifier("path_exists", line=line, col=col), [expr], line=line, col=col)
        return expr

    def parse_additive(self) -> A.Node:
        left = self.parse_multiplicative()
        while self.check_any(*ADDITIVE_OPS):
            op_tok = self.advance()
            right = self.parse_multiplicative()
            left = A.BinaryOp(op_tok.type, left, right, line=op_tok.line, col=op_tok.col)
        return left

    def parse_multiplicative(self) -> A.Node:
        left = self.parse_unary()
        while self.check_any(*MULT_OPS):
            op_tok = self.advance()
            right = self.parse_unary()
            left = A.BinaryOp(op_tok.type, left, right, line=op_tok.line, col=op_tok.col)
        return left

    def parse_unary(self) -> A.Node:
        if self.check("MINUS"):
            __tok = self.advance(); line, col = __tok.line, __tok.col
            operand = self.parse_unary()
            return A.UnaryOp("MINUS", operand, line=line, col=col)
        return self.parse_postfix()

    def parse_postfix(self) -> A.Node:
        expr = self.parse_primary()
        while True:
            if self.check("DOT"):
                self.advance()
                name = self._parse_member_name()
                expr = A.MemberAccess(expr, name, line=expr.line, col=expr.col)
            elif self.check("LPAREN"):
                self.advance()
                args = []
                if not self.check("RPAREN"):
                    args.append(self.parse_expression())
                    while self.check("COMMA"):
                        self.advance()
                        args.append(self.parse_expression())
                self.expect("RPAREN")
                expr = A.Call(expr, args, line=expr.line, col=expr.col)
            elif self.check("LBRACKET"):
                self.advance()
                index = self.parse_expression()
                self.expect("RBRACKET")
                expr = A.IndexAccess(expr, index, line=expr.line, col=expr.col)
            else:
                break
        return expr

    def _parse_member_name(self) -> str:
        tok = self.cur()
        if tok.type == "NAME" or (tok.type in KEYWORDS and isinstance(tok.value, str)):
            self.advance()
            return tok.value
        raise EzySyntaxError(f"expected a property name after '.', found {tok.type}", self.filename, tok.line, tok.col)

    def parse_primary(self) -> A.Node:
        tok = self.cur()
        if tok.type == "NUMBER":
            self.advance()
            return A.Literal(tok.value, line=tok.line, col=tok.col)
        if tok.type == "STRING":
            self.advance()
            return self._build_interpolated(tok)
        if tok.type == "true":
            self.advance()
            return A.Literal(True, line=tok.line, col=tok.col)
        if tok.type == "false":
            self.advance()
            return A.Literal(False, line=tok.line, col=tok.col)
        if tok.type == "null":
            self.advance()
            return A.Literal(None, line=tok.line, col=tok.col)
        if tok.type == "NAME":
            self.advance()
            return A.Identifier(tok.value, line=tok.line, col=tok.col)
        if tok.type == "LPAREN":
            self.advance()
            expr = self.parse_expression()
            self.expect("RPAREN")
            return expr
        if tok.type == "LBRACKET":
            self.advance()
            items = []
            if not self.check("RBRACKET"):
                items.append(self.parse_expression())
                while self.check("COMMA"):
                    self.advance()
                    items.append(self.parse_expression())
            self.expect("RBRACKET")
            return A.ListLiteral(items, line=tok.line, col=tok.col)
        if tok.type == "LBRACE":
            return self._parse_map_literal()
        if tok.type in ("get", "post", "put", "patch", "delete"):
            return self._parse_http_request()
        if tok.type == "run":
            return self._parse_run_process()
        if tok.type == "read":
            self.advance()
            path = self.parse_unary()
            return A.ReadFile(path, line=tok.line, col=tok.col)
        if tok.type == "environment":
            self.advance()
            name = self.parse_unary()
            return A.EnvironmentGet(name, line=tok.line, col=tok.col)
        if tok.type in ("file", "folder"):
            self.advance()
            path = self.parse_unary()
            self.expect("exists")
            return A.FileExistsCheck(tok.type, path, line=tok.line, col=tok.col)
        if tok.type == "list":
            self.advance()
            files_tok = self.expect("NAME")
            if files_tok.value != "files":
                raise EzySyntaxError("expected 'files' after 'list'", self.filename, files_tok.line, files_tok.col)
            self.expect("in")
            path = self.parse_unary()
            return A.Call(A.Identifier("list_files", line=tok.line, col=tok.col), [path], line=tok.line, col=tok.col)
        if tok.type == "arguments":
            self.advance()
            return A.Identifier("arguments", line=tok.line, col=tok.col)
        raise EzySyntaxError(f"unexpected token {tok.type} ({tok.value!r})", self.filename, tok.line, tok.col)

    def _build_interpolated(self, tok: Token) -> A.Node:
        parts = []
        has_expr = False
        for part in tok.value:
            if isinstance(part, tuple):
                has_expr = True
                _, src = part
                parts.append(parse_embedded_expression(src, self.filename, tok.line))
            else:
                parts.append(part)
        if not has_expr and len(parts) == 1:
            return A.Literal(parts[0], line=tok.line, col=tok.col)
        return A.InterpolatedString(parts, line=tok.line, col=tok.col)

    def _parse_map_literal(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # '{'
        pairs = []
        if not self.check("RBRACE"):
            pairs.append(self._parse_map_pair())
            while self.check("COMMA"):
                self.advance()
                pairs.append(self._parse_map_pair())
        self.expect("RBRACE")
        return A.MapLiteral(pairs, line=line, col=col)

    def _parse_map_pair(self):
        tok = self.cur()
        if tok.type == "STRING":
            key = self._build_interpolated(self.advance())
        elif tok.type == "NAME" or tok.type in ("true", "false", "null"):
            key = A.Literal(self.advance().value, line=tok.line, col=tok.col)
        else:
            raise EzySyntaxError("expected a map key (string or name)", self.filename, tok.line, tok.col)
        self.expect("COLON")
        value = self.parse_expression()
        return (key, value)

    def _parse_http_request(self) -> A.Node:
        tok = self.advance()
        method = tok.type.upper()
        url = self.parse_unary()
        modifiers = []
        while self.check("with") or self.check("send"):
            if self.check("with"):
                self.advance()
                if self.check("header"):
                    self.advance()
                    modifiers.append(self._parse_kv_or_map("header"))
                elif self.check("query"):
                    self.advance()
                    modifiers.append(self._parse_kv_or_map("query"))
                elif self.check("timeout"):
                    self.advance()
                    value = self.parse_additive()
                    if self.check("seconds"):
                        self.advance()
                    modifiers.append(("timeout", value))
                else:
                    raise EzySyntaxError(
                        "expected 'header', 'query' or 'timeout' after 'with'",
                        self.filename, self.cur().line, self.cur().col,
                    )
            else:  # send
                self.advance()
                self.expect("json")
                value = self.parse_or()
                modifiers.append(("json_body", value))
        return A.HttpRequest(method, url, modifiers, line=tok.line, col=tok.col)

    def _parse_kv_or_map(self, kind: str):
        key_or_map = self.parse_or()
        if self.check("ASSIGN"):
            self.advance()
            value = self.parse_or()
            return (f"{kind}_kv", key_or_map, value)
        return (f"{kind}_map", key_or_map)

    def _parse_run_process(self) -> A.Node:
        __tok = self.advance(); line, col = __tok.line, __tok.col  # 'run'
        command = self.parse_unary()
        modifiers = []
        while self.check("with"):
            self.advance()
            if self.check("arguments"):
                self.advance()
                value = self.parse_or()
                modifiers.append(("arguments", value))
            elif self.check("timeout"):
                self.advance()
                value = self.parse_additive()
                if self.check("seconds"):
                    self.advance()
                modifiers.append(("timeout", value))
            else:
                raise EzySyntaxError(
                    "expected 'arguments' or 'timeout' after 'with'",
                    self.filename, self.cur().line, self.cur().col,
                )
        return A.RunProcess(command, modifiers, line=line, col=col)


def parse_embedded_expression(src: str, filename: str, line: int) -> A.Node:
    tokens = Lexer(src + "\n", filename).tokenize()
    parser = Parser(tokens, filename)
    expr = parser.parse_expression()
    return expr


def parse(source: str, filename: str = "<script>") -> A.Program:
    tokens = Lexer(source, filename).tokenize()
    return Parser(tokens, filename).parse_program()
