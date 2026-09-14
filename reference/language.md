# Ezy language reference

## Syntax basics

- Blocks are indented with spaces (tabs are rejected). A block follows
  a line ending in a statement that expects one (`if`, `for`, `while`,
  `repeat`, `function`, `try`/`catch`, `parallel`).
- Comments start with `#` and run to the end of the line.
- Statements end at a newline; there is no statement separator.
- Strings can use `"` or `'`. `{expr}` inside a string interpolates an
  expression. A literal `{` or `}` must be escaped as `\{` / `\}`.

## Values and types

| Type | Example | Notes |
|---|---|---|
| string | `"hi"` | UTF-8 text |
| integer | `42` | arbitrary-precision (Python `int`) |
| decimal | `3.14` | IEEE double |
| boolean | `true` / `false` | |
| null | `null` | also the result of a missing map key |
| list | `[1, 2, 3]` | 0-indexed, mutable |
| map | `{"a": 1, "b": 2}` | string keys, insertion-ordered |
| path | `path("a/b.txt")` | `.name`, `.extension`, `.parent`, `.exists` |
| http response | result of `get`/`post`/... | `.status .text .json .headers .url .ok .error` |
| process result | result of `run` | `.output .error .exit_code .ok .timed_out` |
| function | `function f ...` | closes over its defining scope |

`type_of(x)` returns the type name as a string. `string(x)`,
`integer(x)`, `decimal(x)` convert between types.

### Equality and truthiness

`==`/`!=` compare any two values by structural equality. `<`, `<=`,
`>`, `>=` only work between two numbers or two strings; comparing other
combinations raises a `TypeError`. In an `if`/`while` condition,
`false`, `null`, `0`, `0.0`, `""`, `[]` and `{}` are falsy; everything
else is truthy.

## Variables

```
name = "Ayush"          # define or reassign, walking outward to an
                         # existing binding first, else defining locally
let x = 1                # always defines a new local binding (shadows)
const max_retries = 3    # like `let`, but reassignment is a TypeError
```

Ezy uses **function-level scoping**, not block-level scoping: a
variable assigned inside an `if`, `for`, `while`, or `try` body is
visible after that block ends, in the same function (or top-level
script). This matches what people coming from Python or Bash expect,
and avoids a class of "why can't I see this variable" beginner
confusion. `let`/`const` create an explicit new binding in the current
scope if you do want to shadow an outer variable on purpose.

## Operators

`+ - * /` `%` (modulo) `== != < <= > >=` `and or not` `matches` (regex
test, see below). `+` concatenates when either side is a string
(auto-converting the other side), concatenates two lists, and adds
otherwise. `/` returns an integer when both operands are integers and
divide evenly, a decimal otherwise. Division and modulo by zero raise
a `MathError`.

## Conditions

```
if age >= 18
    say "adult"
otherwise if age >= 13
    say "teen"
otherwise
    say "child"
```

## Loops

```
for each item in [1, 2, 3]
    say item

for n from 1 to 10       # inclusive; counts down if start > end
    say n

repeat 5 times
    say "hi"

while condition
    ...
    break
    continue
```

`for each` iterates a list's elements, a string's characters, or a
map's values.

## Functions

```
function add a, b
    return a + b

function greet name, greeting = "Hello"   # default argument
    return "{greeting}, {name}"
```

Functions are closures: a nested function keeps access to the
variables of the function that defined it, including after the outer
function has returned (see `examples/functions.ezy`). Calling with too
few arguments (and no default) or too many is a `TypeError`.

## Strings and collections

Built-in functions: `length`, `upper`, `lower`, `trim`, `split`,
`join`, `replace`, `contains`, `keys`, `values`, `sort`, `sort_by`,
`reverse`, `map`, `filter`, `reduce`, `find`, `count`, `min`, `max`,
`round`, `abs`, `sqrt`. `x.length` also works as a property.

## Files

```
create file "notes.txt"
create folder "projects"
write "hello" to "notes.txt"      # overwrites
append "\nmore" to "notes.txt"
content = read "notes.txt"
delete file "notes.txt"
delete folder "projects"
if file "notes.txt" exists
    ...
if folder "projects" exists
    ...
files = list files in "projects"   # list of paths, sorted by name
```

`read` only supports UTF-8 text files; a binary file raises a
`FileError` with a clear message rather than returning garbage (see
reference/limitations.md).

## Processes

```
result = run "git status"
result = run "git" with arguments ["status", "--short"]
result = run "some-command" with timeout 5 seconds

result.output      # stdout
result.error       # stderr
result.exit_code
result.ok           # true if exit_code == 0
result.timed_out
```

`run "cmd"` (single string) is tokenized with `shlex` and executed
**without a shell** — no shell metacharacter ever gets interpreted.
`run "cmd" with arguments [...]` skips tokenization entirely; prefer it
whenever any part of the command comes from untrusted input (a
downloaded value, a user-supplied string). See reference/security.md.

Piping stdout into stdin across commands:

```
result = run "echo hello" -> run "tr a-z A-Z"
```

## HTTP

```
response = get "https://api.example.com/users"
response = get url with query {"q": "printer", "page": 2}
response = get url with header {"Authorization": "Bearer TOKEN"}
response = get url with timeout 10 seconds
response = post url send json {"name": "Ayush"}
response = put url send json {...}
response = patch url send json {...}
response = delete url

if response is successful       # response.ok, i.e. 2xx
    ...
if response is failed
    ...

download "https://example.com/file.zip"
save as "file.zip"
```

TLS certificate verification is always on — there is no language-level
way to turn it off. Redirects are followed using the underlying HTTP
library's defaults. A failed connection, DNS lookup, or timeout is
reported as `response.ok == false` with `response.error` set, rather
than raising — so a normal `if response is successful / otherwise`
handles it. A malformed JSON body only raises when you actually access
`.json`.

## JSON

```
data = parse_json(text)
text = to_json(value)              # pretty-printed by default
text = to_json(value, false)       # compact
```

Since a map/list literal already *is* JSON-shaped, most scripts never
need `parse_json`/`to_json` except at the edges (reading a file,
printing for a log). `response.json` parses an HTTP response body
automatically.

## Errors

```
try
    response = get url
    if response is failed
        say "not ok: {response.status}"
catch err
    say "{err.type}: {err.message}"
```

Errors raised by built-in operations always have a `type` (e.g.
`FileError`, `HttpError`, `ProcessError`, `MathError`, `TypeError`,
`NameError`, `IndexError`, `KeyError`, `JsonError`, `ModuleError`,
`RegexError`) and a `message`. Uncaught errors halt the script with
exit code 2 (see Exit codes below).

## Modules

```
use "http"          # built-in module names are validated, not required
use "./utils"        # loads ./utils.ezy (or .ez) as a namespace
say utils.some_function(1, 2)
```

A local module is executed once in its own scope; every top-level
name it defines (functions and variables) becomes a member accessible
with `.`. There is no package registry yet — see reference/limitations.md.

## Regex

```
if text matches "^[A-Z][a-z]+$"
    say "looks like a name"
```

`matches` uses Python's `re.search` semantics (the pattern does not
need to match the whole string unless anchored with `^`/`$`).

## Concurrency

```
parallel
    users = get users_url
    products = get products_url
    orders = get orders_url
```

Each assignment inside a `parallel` block runs on its own thread; the
block waits for all of them before continuing. This is aimed
specifically at I/O-bound work (HTTP calls, process launches) — CPython's
GIL means it does not speed up CPU-bound Ezy code. See
reference/limitations.md for what `parallel` intentionally does not support.

`wait N seconds` pauses the script.

## Pipelines

```
result = run "cat file.txt" -> run "sort"    # real process pipe
value = 5 -> double(it) -> triple(it)         # generic: `it` is bound
                                                # to the previous stage's
                                                # value
```

See reference/limitations.md for why this is explicit-function-call based
rather than the bare-predicate form (`-> filter age >= 18`) sketched in
early notes.

## CLI scripts

`arguments` is a built-in list of the values passed after the script
path on the command line (`ezy run script.ezy a b c` → `arguments`
is `["a", "b", "c"]`).

## REPL

```
ezy repl
```

Runs an interactive session sharing the same parser and interpreter as
scripts. History is kept in `~/.ezy_history` when the `readline` module
is available.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | syntax error |
| 2 | runtime error |
| 64 | invalid CLI usage (bad flags, missing file) |
| 130 | interrupted (Ctrl+C) |

## Reserved words

`and or not true false null if otherwise for each in from to repeat
times while break continue function return say use try catch create
folder file write append delete list exists environment set run with
arguments get post put patch download save as header query timeout
seconds json parallel matches is read wait send successful failed let
const`

These cannot be used as variable or function names. `files` is *not*
reserved (it is recognized contextually only right after `list`), so
`files = list files in "."` works as written.
