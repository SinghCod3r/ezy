# Security

## Process execution

`run "some string"` is tokenized with Python's `shlex.split` and
executed via `subprocess.run(argv, shell=False, ...)`. No shell is ever
invoked, so shell metacharacters (`;`, `&&`, `|`, backticks, `$()`,
etc.) inside the string are treated as literal argument text by
`shlex`, not interpreted — there is no command-injection path through
`run "literal string"` alone.

The risk that remains: if a script builds the command *string* itself
by concatenating untrusted input (`run "cat " + user_input`),
`shlex.split` will still split on whitespace/quotes inside
`user_input`, which can change the argument boundaries even though it
can't invoke a shell. **`run "cmd" with arguments [...]` avoids this
entirely** — the argument list is passed to `subprocess` untouched,
one Python list element per process argument, with no re-parsing. This
is called out in docs/language.md and used in
`examples/process.ezy`; scripts that build a command from any value
that isn't a fixed literal should prefer it.

Process pipelines (`run "a" -> run "b"`) use the same `shlex`-per-stage
approach for each stage independently.

## Filesystem

`create`/`write`/`append`/`read`/`delete` operate on whatever path
string the script provides, resolved the same way Python's `open()`
resolves it (relative to the process's current working directory
unless absolute). Ezy does **not** currently sandbox script filesystem
access to a project directory — a script can read or delete anything
the OS-level user running `ezy` can. This matches the trust model of
Bash/Python scripts run directly (the language is not a sandbox), but
it means Ezy scripts should be reviewed with the same care as shell
scripts before running them with elevated privileges. This is called
out again in docs/limitations.md.

`create_file`/`write_file`/`append_file` create missing parent
directories with `os.makedirs(..., exist_ok=True)`, which can silently
create directory structure the caller didn't expect; this is
convenient for scripts but worth knowing about.

Symlinks are followed by the underlying Python/OS calls without
special handling — Ezy does not currently detect or warn about a
symlink pointing outside an expected directory (a symlink attack). A
future version could add an explicit "resolve and check" step; today,
avoid running untrusted `.ezy` scripts that manipulate paths derived
from untrusted input.

## HTTP

- TLS certificate verification is always on. There is no
  `with insecure` or equivalent flag, on purpose — the master design
  brief for this project explicitly asked for this.
- Headers (including `Authorization`) are sent exactly as given and
  are **never logged** by the interpreter itself. `say response` does
  not print request headers. If a script explicitly does
  `say headers`, that is the script's own choice, not something Ezy
  does implicitly.
- A non-2xx response does not raise; it comes back as
  `response.ok == false` with the status and body still available,
  which avoids scripts being tempted to swallow errors with a broad
  `try` just to inspect a 404.
- Connection errors, timeouts, and TLS failures are caught and
  returned as `response.ok == false` with `response.error` describing
  the failure, rather than crashing the script — but they are never
  silently downgraded to "success".

## Modules

Local module imports (`use "./utils"`) only ever load a file the
script author names explicitly, resolved relative to the importing
script's directory — there is no remote/package-registry import path
yet (see docs/limitations.md), which removes an entire class of
supply-chain risk that a real package manager would need to address
before it ships.

## What was not built, and why that's a security-relevant gap

- No package manager: a "planned" package manager processing
  third-party code is a significant trust boundary (signature
  verification, lock files, registry compromise) — see
  docs/limitations.md. Shipping a fake one would be worse than not
  having one.
- No sandboxing of filesystem/process/network access per script. This
  is consistent with how Bash, Python, and Ruby scripts already work,
  but is worth stating plainly rather than implying "secure by
  default" covers this — Ezy's security work concentrates on *how*
  operations are performed (no shell injection, TLS always verified,
  no credential logging), not on isolating a script from the machine
  it runs on.
