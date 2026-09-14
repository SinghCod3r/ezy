"""Tree-walking interpreter for Ezy.

Scoping is function-level rather than block-level: `if`, `for`, `while`
and `try` bodies share the enclosing scope, matching what a beginner
coming from Python or Bash expects (a variable assigned inside an `if`
is visible after it). `let`/`const` create a new binding in the current
scope explicitly; plain `name = value` walks outward to an existing
binding before falling back to defining one locally, so functions can
still shadow outer names deliberately.
"""

from __future__ import annotations

import json as _json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from . import ast_nodes as A
from .errors import BreakSignal, ContinueSignal, EzyRuntimeError, ReturnSignal
from .parser import parse
from .values import (BuiltinFunction, EzyErrorValue, EzyModule, EzyPath,
                      Function, HttpResponse, ProcessResult)
from .stdlib import files as files_mod
from .stdlib import http as http_mod
from .stdlib import process as process_mod

BUILTIN_MODULES = {"http", "files", "json", "process", "regex", "math", "cli"}


class Environment:
    __slots__ = ("vars", "consts", "parent")

    def __init__(self, parent: Optional["Environment"] = None):
        self.vars: Dict[str, Any] = {}
        self.consts = set()
        self.parent = parent

    def has(self, name: str) -> bool:
        env = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False

    def get(self, name: str, line: int = 0):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise EzyRuntimeError(f"undefined variable: '{name}'", "NameError", line)

    def assign_or_define(self, name: str, value: Any, line: int = 0) -> None:
        env = self
        while env is not None:
            if name in env.vars:
                if name in env.consts:
                    raise EzyRuntimeError(f"cannot reassign constant '{name}'", "TypeError", line)
                env.vars[name] = value
                return
            env = env.parent
        self.vars[name] = value

    def define_local(self, name: str, value: Any) -> None:
        self.vars[name] = value

    def define_const(self, name: str, value: Any, line: int = 0) -> None:
        if name in self.vars and name in self.consts:
            raise EzyRuntimeError(f"cannot reassign constant '{name}'", "TypeError", line)
        self.vars[name] = value
        self.consts.add(name)


def truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if value == 0 and isinstance(value, (int, float)) and not isinstance(value, bool):
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


class Interpreter:
    def __init__(self, filename: str = "<script>", script_dir: str = ".",
                 output: Callable[[str], None] = None):
        self.filename = filename
        self.script_dir = script_dir
        self.global_env = Environment()
        self.output = output or (lambda line: print(line))
        self.builtins = self._build_builtins()
        self._module_cache: Dict[str, EzyModule] = {}
        self.arguments: List[str] = []

    # -- program entry ---------------------------------------------------

    def run(self, program: A.Program) -> None:
        self.global_env.define_local("arguments", self.arguments)
        try:
            self.exec_block(program.statements, self.global_env)
        except ReturnSignal:
            pass
        except (BreakSignal, ContinueSignal):
            raise EzyRuntimeError("'break'/'continue' used outside of a loop", "SyntaxError")

    def exec_block(self, statements: List[A.Node], env: Environment) -> None:
        for stmt in statements:
            self.exec_stmt(stmt, env)

    def exec_stmt(self, node: A.Node, env: Environment) -> None:
        method = getattr(self, f"exec_{type(node).__name__}", None)
        if method is None:
            raise EzyRuntimeError(f"cannot execute {type(node).__name__}", "InternalError", node.line)
        method(node, env)

    def eval_expr(self, node: A.Node, env: Environment) -> Any:
        method = getattr(self, f"eval_{type(node).__name__}", None)
        if method is None:
            raise EzyRuntimeError(f"cannot evaluate {type(node).__name__}", "InternalError", node.line)
        return method(node, env)

    # -- statements --------------------------------------------------------

    def exec_Assignment(self, node: A.Assignment, env: Environment) -> None:
        value = self.eval_expr(node.value, env)
        target = node.target
        if isinstance(target, A.Identifier):
            if node.declared == "const":
                env.define_const(target.name, value, node.line)
            elif node.declared == "let":
                env.define_local(target.name, value)
            else:
                env.assign_or_define(target.name, value, node.line)
        elif isinstance(target, A.MemberAccess):
            obj = self.eval_expr(target.obj, env)
            self._set_member(obj, target.name, value, node.line)
        elif isinstance(target, A.IndexAccess):
            obj = self.eval_expr(target.obj, env)
            index = self.eval_expr(target.index, env)
            self._set_index(obj, index, value, node.line)
        else:
            raise EzyRuntimeError("invalid assignment target", "SyntaxError", node.line)

    def exec_ExprStatement(self, node: A.ExprStatement, env: Environment) -> None:
        self.eval_expr(node.expr, env)

    def exec_SayStatement(self, node: A.SayStatement, env: Environment) -> None:
        value = self.eval_expr(node.expr, env)
        self.output(self.stringify(value))

    def exec_IfStatement(self, node: A.IfStatement, env: Environment) -> None:
        if truthy(self.eval_expr(node.condition, env)):
            self.exec_block(node.then_body, env)
            return
        for cond, body in node.elif_clauses:
            if truthy(self.eval_expr(cond, env)):
                self.exec_block(body, env)
                return
        if node.else_body is not None:
            self.exec_block(node.else_body, env)

    def exec_ForEachStatement(self, node: A.ForEachStatement, env: Environment) -> None:
        iterable = self.eval_expr(node.iterable, env)
        if isinstance(iterable, list):
            items = iterable
        elif isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, dict):
            items = list(iterable.values())
        else:
            raise EzyRuntimeError("this value cannot be iterated with 'for each'", "TypeError", node.line)
        for item in items:
            env.define_local(node.var_name, item)
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_ForRangeStatement(self, node: A.ForRangeStatement, env: Environment) -> None:
        start = self.eval_expr(node.start, env)
        end = self.eval_expr(node.end, env)
        if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
            raise EzyRuntimeError("'for ... from ... to ...' requires whole numbers", "TypeError", node.line)
        step = 1 if start <= end else -1
        for n in range(start, end + step, step):
            env.define_local(node.var_name, n)
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_RepeatStatement(self, node: A.RepeatStatement, env: Environment) -> None:
        count = self.eval_expr(node.count, env)
        if not isinstance(count, int) or isinstance(count, bool):
            raise EzyRuntimeError("'repeat ... times' requires a whole number", "TypeError", node.line)
        for _ in range(count):
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_WhileStatement(self, node: A.WhileStatement, env: Environment) -> None:
        while truthy(self.eval_expr(node.condition, env)):
            try:
                self.exec_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_BreakStatement(self, node: A.BreakStatement, env: Environment) -> None:
        raise BreakSignal()

    def exec_ContinueStatement(self, node: A.ContinueStatement, env: Environment) -> None:
        raise ContinueSignal()

    def exec_FunctionDef(self, node: A.FunctionDef, env: Environment) -> None:
        env.define_local(node.name, Function(node.name, node.params, node.body, env))

    def exec_ReturnStatement(self, node: A.ReturnStatement, env: Environment) -> None:
        value = self.eval_expr(node.expr, env) if node.expr is not None else None
        raise ReturnSignal(value)

    def exec_TryStatement(self, node: A.TryStatement, env: Environment) -> None:
        try:
            self.exec_block(node.try_body, env)
        except EzyRuntimeError as exc:
            if node.error_name:
                env.define_local(node.error_name, EzyErrorValue(exc.error_type, exc.message))
            self.exec_block(node.catch_body, env)

    def exec_UseStatement(self, node: A.UseStatement, env: Environment) -> None:
        module = node.module
        if module.startswith("./") or module.startswith("../"):
            self._import_local_module(module, env, node.line)
            return
        if module not in BUILTIN_MODULES:
            raise EzyRuntimeError(f"unknown module: '{module}'", "ModuleError", node.line)
        # Built-in modules are always available as global functions; `use`
        # documents the dependency and validates the name.

    def exec_CreateFileStatement(self, node: A.CreateFileStatement, env: Environment) -> None:
        path = self.eval_expr(node.path, env)
        if node.kind == "file":
            files_mod.create_file(path)
        else:
            files_mod.create_folder(path)

    def exec_WriteStatement(self, node: A.WriteStatement, env: Environment) -> None:
        content = self.eval_expr(node.content, env)
        path = self.eval_expr(node.path, env)
        text = content if isinstance(content, str) else self.stringify(content)
        if node.append:
            files_mod.append_file(path, text)
        else:
            files_mod.write_file(path, text)

    def exec_DeleteStatement(self, node: A.DeleteStatement, env: Environment) -> None:
        path = self.eval_expr(node.path, env)
        if node.kind == "file":
            files_mod.delete_file(path)
        else:
            files_mod.delete_folder(path)

    def exec_SetEnvironmentStatement(self, node: A.SetEnvironmentStatement, env: Environment) -> None:
        name = self.eval_expr(node.name, env)
        value = self.eval_expr(node.value, env)
        os.environ[str(name)] = value if isinstance(value, str) else self.stringify(value)

    def exec_DownloadStatement(self, node: A.DownloadStatement, env: Environment) -> None:
        url = self.eval_expr(node.url, env)
        dest = self.eval_expr(node.save_as, env)
        resp = http_mod.download(str(url), str(dest))
        if not resp.ok:
            raise EzyRuntimeError(f"download failed: {resp.error or resp.status}", "HttpError", node.line)

    def exec_ParallelStatement(self, node: A.ParallelStatement, env: Environment) -> None:
        def run_one(assign: A.Assignment):
            return self.eval_expr(assign.value, env)

        with ThreadPoolExecutor(max_workers=max(1, len(node.assignments))) as pool:
            futures = [pool.submit(run_one, a) for a in node.assignments]
            results = [f.result() for f in futures]
        for assign, value in zip(node.assignments, results):
            if not isinstance(assign.target, A.Identifier):
                raise EzyRuntimeError("'parallel' assignments must target a simple name", "SyntaxError", node.line)
            if assign.declared == "const":
                env.define_const(assign.target.name, value, node.line)
            elif assign.declared == "let":
                env.define_local(assign.target.name, value)
            else:
                env.assign_or_define(assign.target.name, value, node.line)

    def exec_WaitStatement(self, node: A.WaitStatement, env: Environment) -> None:
        duration = self.eval_expr(node.duration, env)
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise EzyRuntimeError("'wait' requires a number of seconds", "TypeError", node.line)
        time.sleep(duration)

    # -- expressions -------------------------------------------------------

    def eval_Literal(self, node: A.Literal, env: Environment):
        return node.value

    def eval_InterpolatedString(self, node: A.InterpolatedString, env: Environment) -> str:
        out = []
        for part in node.parts:
            if isinstance(part, str):
                out.append(part)
            else:
                out.append(self.stringify(self.eval_expr(part, env)))
        return "".join(out)

    def eval_ListLiteral(self, node: A.ListLiteral, env: Environment) -> list:
        return [self.eval_expr(item, env) for item in node.items]

    def eval_MapLiteral(self, node: A.MapLiteral, env: Environment) -> dict:
        result = {}
        for key_node, value_node in node.pairs:
            key = self.eval_expr(key_node, env)
            result[str(key)] = self.eval_expr(value_node, env)
        return result

    def eval_Identifier(self, node: A.Identifier, env: Environment):
        if env.has(node.name):
            return env.get(node.name, node.line)
        if node.name in self.builtins:
            return self.builtins[node.name]
        raise EzyRuntimeError(f"undefined variable: '{node.name}'", "NameError", node.line)

    def eval_UnaryOp(self, node: A.UnaryOp, env: Environment):
        if node.op == "not":
            return not truthy(self.eval_expr(node.operand, env))
        value = self.eval_expr(node.operand, env)
        if node.op == "MINUS":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EzyRuntimeError("'-' requires a number", "TypeError", node.line)
            return -value
        raise EzyRuntimeError(f"unknown unary operator '{node.op}'", "InternalError", node.line)

    def eval_LogicalOp(self, node: A.LogicalOp, env: Environment) -> bool:
        left = truthy(self.eval_expr(node.left, env))
        if node.op == "and":
            return left and truthy(self.eval_expr(node.right, env))
        return left or truthy(self.eval_expr(node.right, env))

    def eval_BinaryOp(self, node: A.BinaryOp, env: Environment):
        left = self.eval_expr(node.left, env)
        right = self.eval_expr(node.right, env)
        op = node.op
        if op == "PLUS":
            return self._add(left, right, node.line)
        if op == "MINUS":
            return self._numeric_op(left, right, lambda a, b: a - b, "-", node.line)
        if op == "STAR":
            if isinstance(left, str) and isinstance(right, int) and not isinstance(right, bool):
                return left * right
            return self._numeric_op(left, right, lambda a, b: a * b, "*", node.line)
        if op == "SLASH":
            self._require_numbers(left, right, "/", node.line)
            if right == 0:
                raise EzyRuntimeError("division by zero", "MathError", node.line)
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                return left // right
            return left / right
        if op == "PERCENT":
            self._require_numbers(left, right, "%", node.line)
            if right == 0:
                raise EzyRuntimeError("division by zero", "MathError", node.line)
            return left % right
        if op == "EQ":
            return self._equals(left, right)
        if op == "NEQ":
            return not self._equals(left, right)
        if op in ("LT", "LE", "GT", "GE"):
            return self._compare(left, right, op, node.line)
        raise EzyRuntimeError(f"unknown operator '{op}'", "InternalError", node.line)

    def eval_MatchesOp(self, node: A.MatchesOp, env: Environment) -> bool:
        left = self.eval_expr(node.left, env)
        pattern = self.eval_expr(node.pattern, env)
        if not isinstance(left, str) or not isinstance(pattern, str):
            raise EzyRuntimeError("'matches' requires two strings", "TypeError", node.line)
        try:
            return re.search(pattern, left) is not None
        except re.error as exc:
            raise EzyRuntimeError(f"invalid regular expression: {exc}", "RegexError", node.line) from exc

    def eval_Call(self, node: A.Call, env: Environment):
        args = [self.eval_expr(a, env) for a in node.args]
        if isinstance(node.callee, A.Identifier):
            name = node.callee.name
            if not env.has(name) and name in self.builtins:
                return self._call_value(self.builtins[name], args, node.line)
            callee = env.get(name, node.line) if env.has(name) else self._lookup_builtin_or_fail(name, node.line)
        else:
            callee = self.eval_expr(node.callee, env)
        return self._call_value(callee, args, node.line)

    def _lookup_builtin_or_fail(self, name, line):
        raise EzyRuntimeError(f"undefined function: '{name}'", "NameError", line)

    def eval_MemberAccess(self, node: A.MemberAccess, env: Environment):
        obj = self.eval_expr(node.obj, env)
        return self._get_member(obj, node.name, node.line)

    def eval_IndexAccess(self, node: A.IndexAccess, env: Environment):
        obj = self.eval_expr(node.obj, env)
        index = self.eval_expr(node.index, env)
        return self._get_index(obj, index, node.line)

    def eval_PipelineExpr(self, node: A.PipelineExpr, env: Environment):
        if all(isinstance(s, A.RunProcess) for s in node.stages):
            commands = [self.eval_expr(s.command, env) for s in node.stages]
            return process_mod.run_pipeline([str(c) for c in commands])
        value = self.eval_expr(node.stages[0], env)
        for stage in node.stages[1:]:
            child = Environment(parent=env)
            child.define_local("it", value)
            value = self.eval_expr(stage, child)
        return value

    def eval_HttpRequest(self, node: A.HttpRequest, env: Environment) -> HttpResponse:
        url = self.eval_expr(node.url, env)
        headers: Dict[str, str] = {}
        params: Dict[str, Any] = {}
        json_body = None
        timeout = None
        for modifier in node.modifiers:
            kind = modifier[0]
            if kind == "header_kv":
                k = self.eval_expr(modifier[1], env)
                v = self.eval_expr(modifier[2], env)
                headers[str(k)] = str(v)
            elif kind == "header_map":
                m = self.eval_expr(modifier[1], env)
                headers.update({str(k): str(v) for k, v in m.items()})
            elif kind == "query_kv":
                k = self.eval_expr(modifier[1], env)
                v = self.eval_expr(modifier[2], env)
                params[str(k)] = v
            elif kind == "query_map":
                m = self.eval_expr(modifier[1], env)
                params.update(m)
            elif kind == "timeout":
                timeout = self.eval_expr(modifier[1], env)
            elif kind == "json_body":
                json_body = self.eval_expr(modifier[1], env)
        return http_mod.request(
            node.method, str(url),
            headers=headers or None, params=params or None,
            json_body=json_body, timeout=timeout,
        )

    def eval_RunProcess(self, node: A.RunProcess, env: Environment) -> ProcessResult:
        command = self.eval_expr(node.command, env)
        arguments = None
        timeout = None
        for kind, expr in node.modifiers:
            if kind == "arguments":
                arguments = [self.stringify(v) for v in self.eval_expr(expr, env)]
            elif kind == "timeout":
                timeout = self.eval_expr(expr, env)
        return process_mod.run_command(str(command), arguments=arguments, timeout=timeout)

    def eval_ReadFile(self, node: A.ReadFile, env: Environment) -> str:
        path = self.eval_expr(node.path, env)
        return files_mod.read_file(path)

    def eval_FileExistsCheck(self, node: A.FileExistsCheck, env: Environment) -> bool:
        path = self.eval_expr(node.path, env)
        return files_mod.file_exists(path) if node.kind == "file" else files_mod.folder_exists(path)

    def eval_EnvironmentGet(self, node: A.EnvironmentGet, env: Environment):
        name = self.eval_expr(node.name, env)
        return os.environ.get(str(name))

    # -- member / index access helpers --------------------------------------

    def _get_member(self, obj: Any, name: str, line: int):
        if name == "length":
            return self._builtin_length(obj, line)
        if isinstance(obj, dict):
            return obj.get(name)
        if isinstance(obj, EzyPath):
            if name in ("name", "extension", "parent", "exists"):
                return getattr(obj, name)
            raise EzyRuntimeError(f"a path has no property '{name}'", "TypeError", line)
        if isinstance(obj, HttpResponse):
            if name in ("status", "text", "headers", "url", "ok", "json", "error", "elapsed_ms"):
                return getattr(obj, name)
            raise EzyRuntimeError(f"a response has no property '{name}'", "TypeError", line)
        if isinstance(obj, ProcessResult):
            if name in ("output", "error", "exit_code", "ok", "timed_out"):
                return getattr(obj, name)
            raise EzyRuntimeError(f"a process result has no property '{name}'", "TypeError", line)
        if isinstance(obj, EzyModule):
            if name in obj.members:
                return obj.members[name]
            raise EzyRuntimeError(f"module '{obj.name}' has no member '{name}'", "NameError", line)
        if isinstance(obj, EzyErrorValue):
            if name in ("type", "message"):
                return getattr(obj, name)
            raise EzyRuntimeError(f"an error value has no property '{name}'", "TypeError", line)
        raise EzyRuntimeError(f"cannot access '.{name}' on this value", "TypeError", line)

    def _set_member(self, obj: Any, name: str, value: Any, line: int) -> None:
        if isinstance(obj, dict):
            obj[name] = value
            return
        raise EzyRuntimeError("only maps support setting a named field", "TypeError", line)

    def _get_index(self, obj: Any, index: Any, line: int):
        if isinstance(obj, list):
            if not isinstance(index, int) or isinstance(index, bool):
                raise EzyRuntimeError("a list index must be a whole number", "TypeError", line)
            if index < 0 or index >= len(obj):
                raise EzyRuntimeError(f"list index {index} is out of range (length {len(obj)})", "IndexError", line)
            return obj[index]
        if isinstance(obj, dict):
            return obj.get(str(index))
        if isinstance(obj, str):
            if not isinstance(index, int) or isinstance(index, bool):
                raise EzyRuntimeError("a string index must be a whole number", "TypeError", line)
            if index < 0 or index >= len(obj):
                raise EzyRuntimeError("string index out of range", "IndexError", line)
            return obj[index]
        raise EzyRuntimeError("this value cannot be indexed with [...]", "TypeError", line)

    def _set_index(self, obj: Any, index: Any, value: Any, line: int) -> None:
        if isinstance(obj, list):
            if not isinstance(index, int) or isinstance(index, bool):
                raise EzyRuntimeError("a list index must be a whole number", "TypeError", line)
            if index < 0 or index >= len(obj):
                raise EzyRuntimeError(f"list index {index} is out of range (length {len(obj)})", "IndexError", line)
            obj[index] = value
            return
        if isinstance(obj, dict):
            obj[str(index)] = value
            return
        raise EzyRuntimeError("this value does not support index assignment", "TypeError", line)

    # -- operator helpers ----------------------------------------------------

    def _require_numbers(self, left, right, op, line):
        if isinstance(left, bool) or isinstance(right, bool) or not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            raise EzyRuntimeError(
                f"'{op}' requires two numbers, got {self._type_name(left)} and {self._type_name(right)}",
                "TypeError", line,
            )

    def _numeric_op(self, left, right, fn, op, line):
        self._require_numbers(left, right, op, line)
        return fn(left, right)

    def _add(self, left, right, line):
        if isinstance(left, str) or isinstance(right, str):
            return self.stringify(left) + self.stringify(right)
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        return self._numeric_op(left, right, lambda a, b: a + b, "+", line)

    def _equals(self, left, right) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            return left is right
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left == right
        return type(left) == type(right) and left == right if not (left is None or right is None) else left is right

    def _compare(self, left, right, op, line):
        if isinstance(left, bool) or isinstance(right, bool):
            raise EzyRuntimeError("booleans cannot be ordered with <, >, <= or >=", "TypeError", line)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            pass
        elif isinstance(left, str) and isinstance(right, str):
            pass
        else:
            raise EzyRuntimeError(
                f"cannot compare {self._type_name(left)} with {self._type_name(right)}", "TypeError", line,
            )
        if op == "LT":
            return left < right
        if op == "LE":
            return left <= right
        if op == "GT":
            return left > right
        return left >= right

    def _type_name(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "decimal"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "map"
        if isinstance(value, EzyPath):
            return "path"
        if isinstance(value, HttpResponse):
            return "http response"
        if isinstance(value, ProcessResult):
            return "process result"
        if isinstance(value, (Function, BuiltinFunction)):
            return "function"
        return type(value).__name__

    # -- calling -------------------------------------------------------------

    def _call_value(self, callee: Any, args: List[Any], line: int):
        if isinstance(callee, Function):
            return self._call_function(callee, args, line)
        if isinstance(callee, BuiltinFunction):
            try:
                return callee(*args)
            except EzyRuntimeError:
                raise
            except (TypeError, ValueError) as exc:
                raise EzyRuntimeError(f"{callee.name}(): {exc}", "TypeError", line) from exc
        raise EzyRuntimeError("this value is not a function", "TypeError", line)

    def _call_function(self, fn: Function, args: List[Any], line: int):
        if len(args) > len(fn.params):
            raise EzyRuntimeError(
                f"'{fn.name}' takes {len(fn.params)} argument(s) but {len(args)} were given", "TypeError", line,
            )
        call_env = Environment(parent=fn.closure)
        for i, (pname, default) in enumerate(fn.params):
            if i < len(args):
                call_env.define_local(pname, args[i])
            elif default is not None:
                call_env.define_local(pname, self.eval_expr(default, fn.closure))
            else:
                raise EzyRuntimeError(f"missing argument '{pname}' for '{fn.name}'", "TypeError", line)
        try:
            self.exec_block(fn.body, call_env)
        except ReturnSignal as ret:
            return ret.value
        return None

    # -- modules --------------------------------------------------------------

    def _import_local_module(self, module: str, env: Environment, line: int) -> None:
        rel_path = module if module.endswith((".ezy", ".ez")) else module + ".ezy"
        full_path = os.path.normpath(os.path.join(self.script_dir, rel_path))
        if full_path in self._module_cache:
            mod = self._module_cache[full_path]
        else:
            if not os.path.exists(full_path):
                alt = full_path[:-4] + ".ez" if full_path.endswith(".ezy") else full_path
                if os.path.exists(alt):
                    full_path = alt
                else:
                    raise EzyRuntimeError(f"module not found: '{module}'", "ModuleError", line)
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
            program = parse(source, full_path)
            module_env = Environment()
            sub = Interpreter(filename=full_path, script_dir=os.path.dirname(full_path) or ".",
                               output=self.output)
            sub.global_env = module_env
            sub.exec_block(program.statements, module_env)
            name = os.path.splitext(os.path.basename(full_path))[0]
            mod = EzyModule(name, dict(module_env.vars))
            self._module_cache[full_path] = mod
        env.define_local(mod.name, mod)

    # -- display / stringification --------------------------------------------

    def stringify(self, value: Any) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            return value
        if isinstance(value, float):
            if value == int(value) and abs(value) < 1e15:
                return f"{value:.1f}"
            return repr(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, EzyPath):
            return value.raw
        if isinstance(value, list):
            return "[" + ", ".join(self._display_repr(v) for v in value) + "]"
        if isinstance(value, dict):
            return "{" + ", ".join(f"{k}: {self._display_repr(v)}" for k, v in value.items()) + "}"
        if isinstance(value, HttpResponse):
            return f"<response {value.status} {value.url}>"
        if isinstance(value, ProcessResult):
            return f"<process exit={value.exit_code}>"
        if isinstance(value, EzyErrorValue):
            return f"{value.type}: {value.message}"
        if isinstance(value, (Function, BuiltinFunction)):
            return f"<function {value.name}>"
        return str(value)

    def _display_repr(self, value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        return self.stringify(value)

    # -- builtins --------------------------------------------------------------

    def _builtin_length(self, value, line=0) -> int:
        if isinstance(value, (str, list, dict)):
            return len(value)
        raise EzyRuntimeError(f"'{self._type_name(value)}' has no length", "TypeError", line)

    def _build_builtins(self) -> Dict[str, BuiltinFunction]:
        def b(name):
            def deco(fn):
                self._builtins_tmp[name] = BuiltinFunction(name, fn)
                return fn
            return deco

        self._builtins_tmp: Dict[str, BuiltinFunction] = {}

        @b("length")
        def _length(x):
            return self._builtin_length(x)

        @b("upper")
        def _upper(s):
            return str(s).upper()

        @b("lower")
        def _lower(s):
            return str(s).lower()

        @b("trim")
        def _trim(s):
            return str(s).strip()

        @b("split")
        def _split(s, sep=" "):
            return str(s).split(sep)

        @b("join")
        def _join(items, sep=""):
            return sep.join(self.stringify(v) for v in items)

        @b("replace")
        def _replace(s, old, new):
            return str(s).replace(old, new)

        @b("contains")
        def _contains(collection, item):
            if isinstance(collection, dict):
                return item in collection
            return item in collection

        @b("keys")
        def _keys(m):
            return list(m.keys())

        @b("values")
        def _values(m):
            return list(m.values())

        @b("sort")
        def _sort(items):
            return sorted(items)

        @b("sort_by")
        def _sort_by(items, field):
            return sorted(items, key=lambda item: item.get(field) if isinstance(item, dict) else getattr(item, field))

        @b("reverse")
        def _reverse(items):
            if isinstance(items, str):
                return items[::-1]
            return list(reversed(items))

        @b("to_json")
        def _to_json(value, pretty=True):
            return _json.dumps(value, indent=2 if truthy(pretty) else None)

        @b("parse_json")
        def _parse_json(s):
            try:
                return _json.loads(s)
            except ValueError as exc:
                raise EzyRuntimeError(f"invalid JSON: {exc}", "JsonError") from exc

        @b("round")
        def _round(x, digits=0):
            return round(x, digits) if digits else int(round(x))

        @b("abs")
        def _abs(x):
            return abs(x)

        @b("min")
        def _min(*args):
            items = args[0] if len(args) == 1 and isinstance(args[0], list) else args
            return min(items)

        @b("max")
        def _max(*args):
            items = args[0] if len(args) == 1 and isinstance(args[0], list) else args
            return max(items)

        @b("is_successful")
        def _is_successful(resp):
            if isinstance(resp, HttpResponse):
                return resp.ok
            if isinstance(resp, ProcessResult):
                return resp.ok
            raise EzyRuntimeError("'is successful' expects a response or process result", "TypeError")

        @b("is_failed")
        def _is_failed(resp):
            return not _is_successful(resp)

        @b("path_exists")
        def _path_exists(p):
            return files_mod.path_exists(p)

        @b("list_files")
        def _list_files(p):
            return files_mod.list_files(p)

        @b("type_of")
        def _type_of(x):
            return self._type_name(x)

        @b("string")
        def _string(x):
            return self.stringify(x)

        @b("integer")
        def _integer(x):
            try:
                return int(x)
            except (TypeError, ValueError) as exc:
                raise EzyRuntimeError(f"cannot convert to an integer: {x!r}", "TypeError") from exc

        @b("decimal")
        def _decimal(x):
            try:
                return float(x)
            except (TypeError, ValueError) as exc:
                raise EzyRuntimeError(f"cannot convert to a decimal: {x!r}", "TypeError") from exc

        @b("path")
        def _path(x):
            return EzyPath(str(x))

        @b("show")
        def _show(x):
            self.output(self.stringify(x))
            return x

        @b("map")
        def _map(items, fn):
            return [self._call_value(fn, [item], 0) for item in items]

        @b("filter")
        def _filter(items, fn):
            return [item for item in items if truthy(self._call_value(fn, [item], 0))]

        @b("reduce")
        def _reduce(items, fn, initial=None):
            acc = initial
            it = iter(items)
            if acc is None:
                acc = next(it)
            for item in it:
                acc = self._call_value(fn, [acc, item], 0)
            return acc

        @b("find")
        def _find(items, fn):
            for item in items:
                if truthy(self._call_value(fn, [item], 0)):
                    return item
            return None

        @b("count")
        def _count(items):
            return len(items)

        @b("sqrt")
        def _sqrt(x):
            return math.sqrt(x)

        return self._builtins_tmp
