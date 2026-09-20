from typing import List, Dict, Set, Optional, Tuple
from . import ast_nodes as A

class LintFinding:
    def __init__(self, filename: str, line: int, col: int, severity: str, code: str, message: str):
        self.filename = filename
        self.line = line
        self.col = col
        self.severity = severity
        self.code = code
        self.message = message

    def __str__(self):
        return f"{self.filename}:{self.line}:{self.col}: {self.severity}: [{self.code}] {self.message}"

class Scope:
    def __init__(self, parent: Optional['Scope'] = None):
        self.parent = parent
        # name -> (decl_type, line, col)
        # decl_type in: "let", "const", "param", "builtin", "implicit"
        self.vars: Dict[str, Tuple[str, int, int]] = {}
        self.reads: Set[str] = set()

    def resolve(self, name: str) -> Optional['Scope']:
        env = self
        while env is not None:
            if name in env.vars:
                return env
            env = env.parent
        return None

class Linter:
    def __init__(self, filename: str = "<script>"):
        self.filename = filename
        self.findings: List[LintFinding] = []
        self.global_scope = Scope()
        self.current_scope = self.global_scope
        self._seed_builtins()

    def _seed_builtins(self):
        builtins = [
            "length", "upper", "lower", "trim", "split", "join", "replace",
            "contains", "keys", "values", "sort", "sort_by", "reverse",
            "to_json", "parse_json", "round", "abs", "min", "max",
            "is_successful", "is_failed", "path_exists", "list_files",
            "type_of", "string", "integer", "decimal", "path", "show",
            "map", "filter", "reduce", "find", "count", "sqrt"
        ]
        for b in builtins:
            self.global_scope.vars[b] = ("builtin", 0, 0)
            self.global_scope.reads.add(b)

    def report(self, line: int, col: int, severity: str, code: str, message: str):
        self.findings.append(LintFinding(self.filename, line, col, severity, code, message))

    def lint_program(self, program: A.Program) -> List[LintFinding]:
        self.visit_list(program.statements)
        self._check_unused(self.global_scope)
        return self.findings

    def _check_unused(self, scope: Scope):
        for name, (decl_type, line, col) in scope.vars.items():
            if decl_type in ("let", "const", "param") and name not in scope.reads:
                self.report(line, col, "warning", "W202", f"unused variable '{name}'")

    def visit_list(self, statements: List[A.Node]):
        is_unreachable = False
        reported_unreachable = False
        for stmt in statements:
            if is_unreachable and not reported_unreachable:
                self.report(stmt.line, stmt.col, "warning", "W203", "unreachable code after 'return', 'break', or 'continue'")
                reported_unreachable = True

            self.visit(stmt)

            if isinstance(stmt, (A.ReturnStatement, A.BreakStatement, A.ContinueStatement)):
                is_unreachable = True

    def visit(self, node: A.Node):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: A.Node):
        for key, value in vars(node).items():
            if isinstance(value, A.Node):
                self.visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, A.Node):
                        self.visit(item)
                    elif isinstance(item, tuple):
                        for sub_item in item:
                            if isinstance(sub_item, A.Node):
                                self.visit(sub_item)

    def visit_Assignment(self, node: A.Assignment):
        self.visit(node.value)

        target = node.target
        if isinstance(target, A.Identifier):
            name = target.name
            if node.declared:
                self.current_scope.vars[name] = (node.declared, target.line, target.col)
            else:
                scope = self.current_scope.resolve(name)
                if scope:
                    decl_type, decl_line, decl_col = scope.vars[name]
                    if decl_type == "const":
                        self.report(target.line, target.col, "error", "E102", f"cannot reassign constant '{name}'")
                else:
                    self.current_scope.vars[name] = ("implicit", target.line, target.col)
        elif isinstance(target, A.MemberAccess):
            self.visit(target.obj)
        elif isinstance(target, A.IndexAccess):
            self.visit(target.obj)
            self.visit(target.index)
        else:
            self.visit(target)

    def visit_Identifier(self, node: A.Identifier):
        scope = self.current_scope.resolve(node.name)
        if scope:
            scope.reads.add(node.name)
        else:
            self.report(node.line, node.col, "error", "E101", f"undefined variable '{node.name}'")

    def visit_FunctionDef(self, node: A.FunctionDef):
        self.current_scope.vars[node.name] = ("let", node.line, node.col)

        for _, default_val in node.params:
            if default_val:
                self.visit(default_val)

        old_scope = self.current_scope
        self.current_scope = Scope(parent=old_scope)

        for param_name, _ in node.params:
            self.current_scope.vars[param_name] = ("param", node.line, node.col)

        self.visit_list(node.body)
        self._check_unused(self.current_scope)

        self.current_scope = old_scope

    def visit_PipelineExpr(self, node: A.PipelineExpr):
        if not node.stages:
            return
        self.visit(node.stages[0])
        for stage in node.stages[1:]:
            old = self.current_scope
            self.current_scope = Scope(parent=old)
            self.current_scope.vars["it"] = ("implicit", stage.line, stage.col)
            self.visit(stage)
            self.current_scope = old


    def visit_CliDef(self, node: A.CliDef):
        self.current_scope.vars["cli"] = ("let", node.line, node.col)
        for child in node.body:
            self.visit(child)

    def visit_CliFlag(self, node: A.CliFlag):
        pass

    def visit_CliOption(self, node: A.CliOption):
        if node.default:
            self.visit(node.default)

    def visit_IfStatement(self, node: A.IfStatement):
        self.visit(node.condition)
        self.visit_list(node.then_body)
        for cond, body in node.elif_clauses:
            self.visit(cond)
            self.visit_list(body)
        if node.else_body:
            self.visit_list(node.else_body)

    def visit_ForEachStatement(self, node: A.ForEachStatement):
        self.visit(node.iterable)
        self.current_scope.vars[node.name] = ("implicit", node.line, node.col)
        self.visit_list(node.body)

    def visit_ForRangeStatement(self, node: A.ForRangeStatement):
        self.visit(node.start)
        self.visit(node.end)
        self.current_scope.vars[node.name] = ("implicit", node.line, node.col)
        self.visit_list(node.body)

    def visit_WhileStatement(self, node: A.WhileStatement):
        self.visit(node.condition)
        self.visit_list(node.body)

    def visit_TryStatement(self, node: A.TryStatement):
        self.visit_list(node.try_body)
        if node.catch_name:
            self.current_scope.vars[node.catch_name] = ("implicit", node.line, node.col)
        self.visit_list(node.catch_body)

    def visit_UseStatement(self, node: A.UseStatement):
        basename = node.module.split("/")[-1]
        self.current_scope.vars[basename] = ("let", node.line, node.col)

def lint_program(program: A.Program, filename: str = "<script>") -> List[LintFinding]:
    linter = Linter(filename)
    return linter.lint_program(program)
