# Architecture

```
source (.ezy / .ez)
     |
     v
  Lexer (lexer.py)       tokens, with INDENT/DEDENT synthesized from
     |                   leading spaces (Python-style layout rule)
     v
  Parser (parser.py)     recursive-descent, one function per grammar
     |                   rule, precedence-climbing for expressions
     v
  AST (ast_nodes.py)     plain dataclasses, one per statement/expression
     |                   kind
     v
  Interpreter            tree-walking evaluator: exec_<NodeType> for
  (interpreter.py)       statements, eval_<NodeType> for expressions,
     |                   dispatched by node class name
     v
  stdlib/                files.py, process.py, http.py: thin wrappers
                          around os/shutil, subprocess, and requests
                          that translate failures into EzyRuntimeError
```

There is no bytecode compiler or VM: the interpreter walks the AST
directly. For a scripting language whose workloads are dominated by
I/O (file, process, HTTP) rather than tight numeric loops, the
overhead of tree-walking is not the bottleneck, and it keeps the whole
pipeline (source -> tokens -> AST -> result) inspectable and easy to
extend — a deliberate simplicity-over-raw-speed tradeoff. `docs/limitations.md`
notes what this rules out for now (e.g. a bytecode-level debugger).

## Environments

`Environment` (in `interpreter.py`) is a parent-linked scope chain: a
dict of names plus a set of names that are `const`. Function calls
create a new `Environment` whose parent is the function's *closure*
(the environment active where the function was defined), which is how
closures work. `if`/`for`/`while`/`try` bodies execute directly against
the enclosing environment rather than creating a new one — see
"Scoping" in docs/language.md for the reasoning.

## Values

Most Ezy values map directly onto native Python values (`str`, `int`,
`float`, `bool`, `None`, `list`, `dict`) so that builtins like
`parse_json`/`to_json` need no conversion layer. `values.py` adds small
wrapper types only where extra behavior is needed: `EzyPath`,
`HttpResponse`, `ProcessResult`, `Function`, `BuiltinFunction`,
`EzyModule`, `EzyErrorValue`.

## Control flow

`break`, `continue`, and `return` are implemented as Python exceptions
(`BreakSignal`, `ContinueSignal`, `ReturnSignal` in `errors.py`) caught
at the appropriate loop/function boundary. This is the standard
technique for a tree-walking interpreter and keeps `exec_*` methods
free of manual "did we return?" flag threading.

## Errors

`EzyRuntimeError` carries an `error_type` string (`"FileError"`,
`"HttpError"`, etc.) and a `message`; `try`/`catch` in `interpreter.py`
catches exactly this class and binds an `EzyErrorValue` with those two
fields to the `catch` variable. `EzySyntaxError` is a separate class
used only by the lexer/parser, and is never catchable from inside an
Ezy script — a syntax error is caught before the program starts
running.

## String interpolation

The lexer, while scanning a string literal, recognizes `{...}` and
records the enclosed source text as an `("expr", source)` tuple rather
than trying to tokenize it as part of the same token stream. The
parser (`parse_embedded_expression` in `parser.py`) re-lexes and parses
that fragment as a standalone expression with a fresh `Lexer`/`Parser`
pair. This keeps the main grammar free of string-interpolation special
cases at the cost of a second small lexer/parser pass per interpolated
expression — negligible for realistic script sizes.

## Modules

`use "./utils"` (or `.ez`) parses and executes the target file once,
in its own top-level `Environment`, then wraps every name it defined
in an `EzyModule` and caches it by resolved path so re-importing the
same file within one run is free. Built-in module names (`use "http"`)
are validated against a fixed set but are a no-op otherwise — the
corresponding functions are always available as globals; `use` exists
to make a script's dependencies self-documenting and to catch typos.

## Processes

`stdlib/process.py` uses `shlex.split` plus `subprocess.run`/`Popen`
with `shell=False` always — see docs/security.md for why. Piping two
`run` stages together (`run "a" -> run "b"`) is detected in
`eval_PipelineExpr` and handed to `run_pipeline`, which wires
`Popen` stdout directly into the next process's stdin, rather than
buffering the whole first command's output in Python and starting the
second command afterward.

## HTTP

`stdlib/http.py` is a wrapper around `requests`. Ezy's `get/post/put
/patch/delete` expressions, `with header/query/timeout`, and
`send json` modifiers are all parsed into a single `HttpRequest` AST
node (see `_parse_http_request` in `parser.py`) and evaluated in one
place (`eval_HttpRequest` in `interpreter.py`), which keeps the
mapping from syntax to the underlying `requests.request(...)` call in
one spot.
