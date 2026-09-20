# Ezy

<div align="center">
  <img src="docs/assets/ezy_logo.png" alt="Ezy Logo" width="300" />
</div>

Ezy is a readable, deterministic scripting language for automation:
files, processes, HTTP, and JSON as first-class citizens, with syntax
that stays close to plain English without becoming a natural-language
parser.

```
name = "World"
say "Hello, {name}!"

if file "config.json" exists
    config = parse_json(read "config.json")
    say config.name

response = get "https://api.example.com/users"
if response is successful
    for each user in response.json
        say user.name
```

Ezy does not depend on AI at runtime. The lexer, parser, and interpreter
are fully deterministic Python code; there is no model in the execution
path.

## Installation

Requires Python 3.9+.

```
pip install -e .
```

This installs the `ezy` command (see `pyproject.toml`). The only runtime
dependency is [`requests`](https://pypi.org/project/requests/), used for
the HTTP subsystem.

## Quick start

```
ezy run examples/hello.ezy
ezy check examples/hello.ezy   # syntax check only, does not run
ezy repl                       # interactive session
```

File extensions `.ezy` and `.ez` are both accepted.



## Linting

Ezy includes a static linter to catch common bugs before execution:

```bash
ezy lint script.ezy
```

The linter detects:
- `[E101]` Undefined variables
- `[E102]` Reassignment of constants
- `[W202]` Unused variables
- `[W203]` Unreachable code

## Formatting

Ezy includes an AST-based formatter (`ezy fmt`) for the currently supported language constructs. It safely preserves comments by detecting their structural placement.

```bash
ezy fmt script.ezy
```

Check if a file requires formatting (useful for CI, exits 1 if unformatted):
```bash
ezy fmt --check script.ezy
```

## Documentation

- [docs/language.md](docs/language.md) — full language reference
- [docs/architecture.md](docs/architecture.md) — how the interpreter is built
- [docs/security.md](docs/security.md) — security model and review notes
- [docs/limitations.md](docs/limitations.md) — honest list of what is not
  (yet) implemented, and deliberate deviations from a natural-language-style
  design
- [examples/](examples) — runnable example scripts

## Development

```
pip install -e ".[dev]"   # or: pip install -e . pytest
python -m pytest tests/ -q
```

Project layout:

```
src/ezy/
  lexer.py        tokenizer (indentation-aware)
  parser.py       recursive-descent parser -> AST
  ast_nodes.py    AST node definitions
  interpreter.py  tree-walking evaluator, environments, builtins
  values.py       runtime value types (Function, HttpResponse, ...)
  stdlib/         files.py, process.py, http.py
  cli.py          `ezy` command (run / check / repl)
  repl.py         interactive shell
tests/            pytest suite (lexer, parser, interpreter, files,
                  process, http against a local test server, CLI)
examples/         runnable .ezy scripts
docs/             language reference, architecture, security, limitations
```

## Status

This is a working v0.1 implementation of a real subset of the language
described in the original design brief, not a mock or a proof of
concept — every statement below `docs/limitations.md`'s "Implemented"
section runs and is covered by an automated test. See that file for
what is partial or not yet built (a package registry, a formatter, a
full point-free pipeline DSL, and a few others), and why.

## CLI Scripts

Ezy allows you to create robust CLI applications effortlessly via the built-in `cli` statement. It automatically provides help text generation, type-checking, alias expansion, and argument parsing.

```ezy
cli "deploy" desc "Deploy the application"
    flag "verbose" alias "v" desc "Enable verbose output"
    option "env" default "dev" desc "Deployment environment"

if cli.verbose
    say "Deploying to {cli.env}"
```

Simply run your script:
```sh
$ ezy run deploy.ezy --help
Usage: deploy [options] [--] [args...]

Deploy the application

Options:
  -v, --verbose      Enable verbose output
  -e, --env          Deployment environment (default: dev)
  -h, --help         Show this help message
```
