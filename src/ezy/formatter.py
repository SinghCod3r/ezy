from typing import List
from . import ast_nodes as A
from .lexer import tokenize

class Formatter:
    def __init__(self, source: str):
        self.source = source
        self.tokens = tokenize(source)
        self.standalone = {}
        self.inline = {}
        self.eof_comments = []
        for tok in self.tokens:
            if hasattr(tok, 'comments') and tok.comments:
                if tok.type == "NEWLINE":
                    self.inline.setdefault(tok.line, []).extend(tok.comments)
                elif tok.type == "EOF":
                    self.eof_comments.extend(tok.comments)
                else:
                    self.standalone.setdefault(tok.line, []).extend(tok.comments)
        self.last_standalone_line = 0

    def format_program(self, program: A.Program) -> str:
        out = ""
        for i, stmt in enumerate(program.statements):
            out += self.format_statement(stmt, indent_level=0)
            if i < len(program.statements) - 1:
                if isinstance(stmt, A.FunctionDef) or isinstance(program.statements[i+1], A.FunctionDef):
                    out += "\n\n"
                else:
                    out += "\n"
        trailing = self.get_standalone_comments(999999)
        if trailing:
            out += "\n" + trailing
        if self.eof_comments:
            eof_str = "\n".join(f"# {c}" if c and not c.startswith(" ") else f"#{c}" for c in self.eof_comments)
            out += "\n" + eof_str + "\n"
        return out.strip() + "\n"

    def get_standalone_comments(self, up_to_line: int) -> str:
        res = []
        for line in sorted(self.standalone.keys()):
            if self.last_standalone_line < line <= up_to_line:
                for c in self.standalone[line]:
                    res.append(f"# {c}" if c and not c.startswith(" ") else f"#{c}")
                self.last_standalone_line = line
        if res:
            return "\n".join(res) + "\n"
        return ""

    def get_inline_comments(self, exact_line: int) -> str:
        if exact_line in self.inline:
            res = []
            for c in self.inline.pop(exact_line):
                res.append(f"# {c}" if c and not c.startswith(" ") else f"#{c}")
            return "  " + "  ".join(res)
        return ""

    def format_statement(self, stmt: A.Node, indent_level: int) -> str:
        indent = "    " * indent_level
        comments = self.get_standalone_comments(stmt.line)
        if comments:
            comments = "".join(indent + line + "\n" for line in comments.strip().split("\n"))
        inline = self.get_inline_comments(stmt.line)
        
        if isinstance(stmt, A.Assignment):
            decl = f"{stmt.declared} " if stmt.declared else ""
            res = f"{decl}{self.format_expr(stmt.target)} = {self.format_expr(stmt.value)}"
            return comments + indent + res + inline
        elif isinstance(stmt, A.ExprStatement):
            return comments + indent + self.format_expr(stmt.expr) + inline
        elif isinstance(stmt, A.SayStatement):
            return comments + indent + f"say {self.format_expr(stmt.expr)}" + inline
        elif isinstance(stmt, A.ReturnStatement):
            if stmt.expr:
                return comments + indent + f"return {self.format_expr(stmt.expr)}" + inline
            return comments + indent + "return" + inline
        elif isinstance(stmt, A.BreakStatement):
            return comments + indent + "break" + inline
        elif isinstance(stmt, A.ContinueStatement):
            return comments + indent + "continue" + inline
        elif isinstance(stmt, A.IfStatement):
            res = f"if {self.format_expr(stmt.condition)}\n"
            res += self.format_block(stmt.then_body, indent_level + 1)
            for elif_cond, elif_body in stmt.elif_clauses:
                # To grab comments preceding otherwise if, we'd need its line. It's in the condition.
                elif_comments = self.get_standalone_comments(elif_cond.line)
                if elif_comments:
                    res += "\n" + "".join(indent + line + "\n" for line in elif_comments.strip().split("\n"))
                else:
                    res += "\n"
                res += f"{indent}otherwise if {self.format_expr(elif_cond)}\n"
                res += self.format_block(elif_body, indent_level + 1)
            if stmt.else_body is not None:
                # Best guess for else block comments: they might precede the first statement of the else body
                # We can't perfectly place them if the else body is empty, but that's rare.
                if stmt.else_body:
                    else_comments = self.get_standalone_comments(stmt.else_body[0].line - 1)
                    if else_comments:
                        res += "\n" + "".join(indent + line + "\n" for line in else_comments.strip().split("\n"))
                    else:
                        res += "\n"
                else:
                    res += "\n"
                res += f"{indent}otherwise\n"
                res += self.format_block(stmt.else_body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.ForEachStatement):
            res = f"for each {stmt.var_name} in {self.format_expr(stmt.iterable)}\n"
            res += self.format_block(stmt.body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.ForRangeStatement):
            res = f"for {stmt.var_name} from {self.format_expr(stmt.start)} to {self.format_expr(stmt.end)}\n"
            res += self.format_block(stmt.body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.RepeatStatement):
            res = f"repeat {self.format_expr(stmt.count)} times\n"
            res += self.format_block(stmt.body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.WhileStatement):
            res = f"while {self.format_expr(stmt.condition)}\n"
            res += self.format_block(stmt.body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.FunctionDef):
            params = ", ".join(p[0] + (f" = {self.format_expr(p[1])}" if p[1] else "") for p in stmt.params)
            res = f"function {stmt.name} {params}\n" if params else f"function {stmt.name}\n"
            res += self.format_block(stmt.body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.TryStatement):
            res = "try\n"
            res += self.format_block(stmt.try_body, indent_level + 1)
            res += f"\n{indent}catch {stmt.error_name}\n"
            res += self.format_block(stmt.catch_body, indent_level + 1)
            return comments + indent + res + inline
        elif isinstance(stmt, A.UseStatement):
            return comments + indent + f"use {stmt.module}" + inline
        elif isinstance(stmt, A.CreateFileStatement):
            return comments + indent + f"create {stmt.kind} {self.format_expr(stmt.path)}" + inline
        elif isinstance(stmt, A.WriteStatement):
            verb = "append" if stmt.append else "write"
            return comments + indent + f"{verb} {self.format_expr(stmt.content)} to {self.format_expr(stmt.path)}" + inline
        elif isinstance(stmt, A.DeleteStatement):
            return comments + indent + f"delete {stmt.kind} {self.format_expr(stmt.path)}" + inline
        elif isinstance(stmt, A.SetEnvironmentStatement):
            return comments + indent + f"set environment {stmt.name} = {self.format_expr(stmt.expr)}" + inline
        elif isinstance(stmt, A.DownloadStatement):
            return comments + indent + f"download {self.format_expr(stmt.url)} save as {self.format_expr(stmt.save_as)}" + inline
        elif isinstance(stmt, A.ParallelStatement):
            res = "parallel\n"
            for assign in stmt.assignments:
                res += self.format_statement(assign, indent_level + 1) + "\n"
            return comments + indent + res.rstrip() + inline
        elif isinstance(stmt, A.WaitStatement):
            return comments + indent + f"wait {self.format_expr(stmt.duration)} seconds" + inline
        
        elif isinstance(stmt, A.CliDef):
            res = f"cli \"{stmt.name}\""
            if stmt.desc:
                res += f" desc \"{stmt.desc}\""
            out_parts = [comments + indent + res + inline]
            
            for child in stmt.body:
                ind2 = indent + "    "
                cc = self.get_standalone_comments(child.line)
                if cc:
                    cc = "".join(ind2 + line + "\n" for line in cc.strip().split("\n"))
                ic = self.get_inline_comments(child.line)
                
                if isinstance(child, A.CliFlag):
                    line_str = f"flag \"{child.name}\""
                    if child.alias:
                        line_str += f" alias \"{child.alias}\""
                    if child.desc:
                        line_str += f" desc \"{child.desc}\""
                    out_parts.append(cc + ind2 + line_str + ic)
                elif isinstance(child, A.CliOption):
                    line_str = f"option \"{child.name}\""
                    if child.alias:
                        line_str += f" alias \"{child.alias}\""
                    if child.default:
                        line_str += f" default {self.format_expr(child.default)}"
                    if child.required:
                        line_str += " required"
                    if child.desc:
                        line_str += f" desc \"{child.desc}\""
                    out_parts.append(cc + ind2 + line_str + ic)
            return "\n".join(out_parts)
        raise ValueError(f"Formatter unsupported statement: {type(stmt).__name__}")

    def format_block(self, stmts: List[A.Node], indent_level: int) -> str:
        if not stmts:
            return ""
        out = []
        for stmt in stmts:
            out.append(self.format_statement(stmt, indent_level))
        return "\n".join(out)

    def _escape_str(self, s: str) -> str:
        s = s.replace("\\", "\\\\")
        s = s.replace("\n", "\\n")
        s = s.replace("\t", "\\t")
        s = s.replace("\"", "\\\"")
        s = s.replace("{", "\\{")
        s = s.replace("}", "\\}")
        return s

    def _get_precedence(self, node: A.Node) -> int:
        if isinstance(node, A.LogicalOp):
            if node.op == "or": return 0
            if node.op == "and": return 1
        elif isinstance(node, A.BinaryOp):
            if node.op in ("EQ", "NEQ", "=="): return 2
            if node.op in ("LT", "LE", "GT", "GE", "<", "<=", ">", ">="): return 3
            if node.op in ("PLUS", "MINUS", "+", "-"): return 4
            if node.op in ("STAR", "SLASH", "PERCENT", "*", "/", "%"): return 5
        elif isinstance(node, A.MatchesOp):
            return 3
        elif isinstance(node, A.UnaryOp):
            return 6
        return 99

    def _format_expr_with_parens(self, expr: A.Node, parent_precedence: int, is_right: bool = False) -> str:
        res = self.format_expr(expr)
        prec = self._get_precedence(expr)
        if prec < parent_precedence:
            return f"({res})"
        if prec == parent_precedence and is_right and prec != 99:
            return f"({res})"
        return res

    def format_expr(self, expr: A.Node) -> str:
        if isinstance(expr, A.Literal):
            if isinstance(expr.value, bool):
                return "true" if expr.value else "false"
            if expr.value is None:
                return "null"
            if isinstance(expr.value, str):
                return f'"{self._escape_str(expr.value)}"'
            return str(expr.value)
        elif isinstance(expr, A.Identifier):
            return expr.name
        elif isinstance(expr, A.InterpolatedString):
            res = '"'
            for part in expr.parts:
                if isinstance(part, str):
                    res += self._escape_str(part)
                else:
                    res += f"{{{self.format_expr(part)}}}"
            return res + '"'
        elif isinstance(expr, A.ListLiteral):
            items = ", ".join(self.format_expr(i) for i in expr.items)
            return f"[{items}]"
        elif isinstance(expr, A.MapLiteral):
            if not expr.pairs:
                return "{}"
            pairs = ", ".join(f"{self.format_expr(k)}: {self.format_expr(v)}" for k, v in expr.pairs)
            return f"{{{pairs}}}"
        elif isinstance(expr, A.BinaryOp):
            op_str = {
                "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/", "PERCENT": "%",
                "EQ": "==", "NEQ": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="
            }.get(expr.op, expr.op)
            prec = self._get_precedence(expr)
            left = self._format_expr_with_parens(expr.left, prec, False)
            right = self._format_expr_with_parens(expr.right, prec, True)
            return f"{left} {op_str} {right}"
        elif isinstance(expr, A.LogicalOp):
            prec = self._get_precedence(expr)
            left = self._format_expr_with_parens(expr.left, prec, False)
            right = self._format_expr_with_parens(expr.right, prec, True)
            return f"{left} {expr.op} {right}"
        elif isinstance(expr, A.UnaryOp):
            op_str = "-" if expr.op == "MINUS" else f"{expr.op} "
            prec = self._get_precedence(expr)
            val = self._format_expr_with_parens(expr.operand, prec, False)
            return f"{op_str}{val}"
        elif isinstance(expr, A.MatchesOp):
            left = self.format_expr(expr.left)
            pattern = self.format_expr(expr.pattern)
            return f"{left} matches {pattern}"
        elif isinstance(expr, A.MemberAccess):
            return f"{self.format_expr(expr.obj)}.{expr.name}"
        elif isinstance(expr, A.IndexAccess):
            return f"{self.format_expr(expr.obj)}[{self.format_expr(expr.index)}]"
        elif isinstance(expr, A.Call):
            args = ", ".join(self.format_expr(a) for a in expr.args)
            return f"{self.format_expr(expr.callee)}({args})"
        elif isinstance(expr, A.PipelineExpr):
            stages = " -> ".join(self.format_expr(s) for s in expr.stages)
            return stages
        elif isinstance(expr, A.HttpRequest):
            modifiers = []
            for name, val in expr.modifiers:
                if name == "json_body":
                    modifiers.append(f"with json {self.format_expr(val)}")
                elif name == "header_map":
                    modifiers.append(f"with header {self.format_expr(val)}")
                elif name == "query_map":
                    modifiers.append(f"with query {self.format_expr(val)}")
                elif name == "header_kv":
                    modifiers.append(f"with header {self.format_expr(val[0])}: {self.format_expr(val[1])}")
                elif name == "query_kv":
                    modifiers.append(f"with query {self.format_expr(val[0])} = {self.format_expr(val[1])}")
            mod_str = (" " + " ".join(modifiers)) if modifiers else ""
            return f"{expr.method} {self.format_expr(expr.url)}{mod_str}"
        elif isinstance(expr, A.RunProcess):
            modifiers = []
            for name, val in expr.modifiers:
                if name == "arguments":
                    modifiers.append(f"with arguments {self.format_expr(val)}")
                elif name == "timeout":
                    modifiers.append(f"with timeout {self.format_expr(val)}")
            mod_str = (" " + " ".join(modifiers)) if modifiers else ""
            return f"run {self.format_expr(expr.command)}{mod_str}"
        elif isinstance(expr, A.ReadFile):
            return f"read {self.format_expr(expr.path)}"
        elif isinstance(expr, A.EnvironmentGet):
            return f"environment {self.format_expr(expr.name)}"
        elif isinstance(expr, A.FileExistsCheck):
            return f"{expr.kind} {self.format_expr(expr.path)} exists"
        
        raise ValueError(f"Formatter unsupported expression: {type(expr).__name__}")

def format_source(source: str, filename: str = "<script>") -> str:
    from .parser import parse
    program = parse(source, filename)
    fmt = Formatter(source)
    return fmt.format_program(program)
