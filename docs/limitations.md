# Limitations, deviations, and roadmap

This file exists so nothing here is overstated. "Implemented" means it
runs and has an automated test in `tests/`. "Partial" means it works
for the documented cases and no others. "Planned" means it does not
exist yet.

## Implemented

Core language: variables (`=`, `let`, `const`), function-level scoping,
all listed types, arithmetic/comparison/logical operators, string
interpolation, `if`/`otherwise if`/`otherwise`, `for each`,
`for ... from ... to ...`, `repeat ... times`, `while`, `break`,
`continue`, functions with default arguments and closures, `try`/
`catch` with typed errors.

Filesystem: `create file/folder`, `write`, `append`, `read`, `delete
file/folder`, `list files in`, `file/folder ... exists`, `path(...)`
with `.name`/`.extension`/`.parent`/`.exists`.

Processes: `run "cmd"` (no shell, via `shlex` + `subprocess`), `run
"cmd" with arguments [...]`, `with timeout ... seconds`, structured
result (`.output .error .exit_code .ok .timed_out`), real process-to-
process piping with `->`.

HTTP: `get/post/put/patch/delete`, `with header {...}`, `with query
{...}`, `with timeout ... seconds`, `send json {...}`, `download` /
`save as`, `is successful` / `is failed`, TLS always verified, JSON
body parsing on `.json`.

JSON: `parse_json`, `to_json` (pretty by default); map/list literals
are already JSON-shaped.

Modules: `use "./local_file"` (or `.ez`), built-in module name
validation for `use "http"` etc.

Concurrency: `parallel` block (thread-per-assignment, join-all).

Misc: `matches` (regex), `wait N seconds`, a generic `->` pipeline
binding `it`, a CLI (`ezy run|check|repl`), a REPL, `arguments` for
CLI scripts, defined exit codes.

Tests: 118 automated tests covering the lexer, parser, interpreter
semantics (including scoping, closures, error types, edge cases like
division by zero and out-of-range indexing), filesystem operations in
isolated temp directories, process execution (including a missing
command, non-zero exit, and a real timeout), HTTP against a local
`http.server` test server (no external network required for the
suite), and the CLI's exit codes and argument handling.

## Partial

- **`parallel`** only accepts a flat list of `name = expression`
  assignments at its top level; it is not general structured
  concurrency (no per-task cancellation, no nested `parallel`, no
  timeout on the whole block). It is genuinely threaded (verified with
  real concurrent HTTP calls in `examples/concurrency.ezy`), which
  helps for I/O-bound scripts but does not parallelize CPU-bound Ezy
  code because of CPython's GIL.
- **`read`** only supports UTF-8 text files; a binary file raises a
  clear `FileError` rather than either crashing unpredictably or
  silently corrupting data. Binary file support (read as bytes, write
  bytes) is not implemented.
- **The REPL's** multi-line block detection is a heuristic (checks for
  known block-opening keywords and trailing colons), not a full
  incremental parse. It handles the common cases shown in
  `docs/language.md` but can be confused by unusual formatting.
- **`->` pipelines**: when every stage is a `run "..."` process call,
  `->` performs a real OS-level pipe. Otherwise it is sugar for
  binding `it` to the previous value and evaluating the next
  expression — it does not lazily stream large collections.

## Planned (not implemented)

- **Package manager** (`package install/remove/update/publish`). This
  is a significant trust boundary — signature verification, lock
  files, a real registry — and building a fake or insecure one would
  be worse than leaving it out. `use "./local_file"` covers the
  single-project case in the meantime.
- **Formatter** (`ezy format`). Not built; a half-working formatter
  that occasionally reflows a script incorrectly is worse than none.
- **Linter beyond syntax checking**. `ezy check` currently validates
  syntax only; unused-variable/unreachable-code detection is not
  implemented.
- **`command "name" / argument ... required` CLI-definition DSL**. Use
  the built-in `arguments` list and `integer(...)`/`string(...)`
  conversions directly (see `examples/cli.ezy`); a declarative
  argument-parsing DSL on top of it is future work.
- **HEAD/OPTIONS/custom HTTP methods, proxies, client certificates,
  cookies-as-a-first-class-object, HTTP/2/3, streaming responses,
  resumable downloads, Unix-socket transport.** The HTTP subsystem
  covers the common REST-client case (GET/POST/PUT/PATCH/DELETE,
  headers, query params, JSON bodies, timeouts, downloads) on top of
  `requests`, which itself does not support HTTP/2/3 or Unix sockets —
  adding those would mean swapping the underlying library, which is a
  bigger change than this pass covers.
- **`every N seconds ...` recurring scheduler.** A script statement
  that blocks forever running a callback is a meaningfully different
  execution model (a long-lived service, not a one-shot script) and
  was intentionally left out rather than half-implemented as something
  that just loops with a fixed count.
- **Windows support.** Development and testing here were done on
  Linux. `subprocess`/`shlex` behavior and path separators differ on
  Windows; nothing has been verified there.
- **Bytecode compiler / VM.** The interpreter tree-walks the AST
  directly (see docs/architecture.md) — there is no faster execution
  tier.
- **Sandboxing.** See docs/security.md — Ezy scripts have the same
  filesystem/process/network access as the OS user running them.

## Deliberate design deviations from the original brief

- **Pipeline modifiers use explicit function calls over `it`**
  (`-> filter(it, is_even)`) rather than a bare-predicate DSL
  (`-> filter age >= 18`). A point-free predicate syntax needs its own
  parsing rules layered onto expressions, which fragments the grammar;
  routing everything through the same expression grammar is more
  coherent and easier to extend, at the cost of a few extra characters
  per pipeline stage.
- **HTTP request modifiers are trailing `with`/`send` clauses**
  (`get url with header {...} with timeout 5 seconds`) rather than an
  indented sub-block (`send json:` followed by an indented
  `name = "Ayush"` block). This keeps modifiers composable in a single
  expression (assignable, passable to a function) instead of only
  valid as a special statement shape, and reuses map literals instead
  of inventing a second way to write a map.
- **`files` is a contextual keyword**, recognized only immediately
  after `list`, rather than a reserved word — because the canonical
  example in the design brief (`files = list files in "projects"`)
  uses "files" as both a variable name and part of the syntax in the
  same line. Every other keyword listed in docs/language.md *is*
  fully reserved; this is the one deliberate exception.
- **String interpolation reserves `{` and `}`** inside string literals,
  requiring `\{`/`\}` for a literal brace (e.g. embedding raw JSON
  text in a string). This is standard for languages with `{}`
  interpolation, but is worth knowing before pasting JSON directly
  into a string literal — building the same data as a map/list literal
  avoids the issue entirely.
