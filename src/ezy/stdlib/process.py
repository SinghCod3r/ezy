"""Process execution for `run "..."`.

Commands are tokenized with shlex and executed via subprocess without a
shell, so user-controlled strings (e.g. a downloaded filename or an HTTP
response value) can never be interpreted as shell syntax. `run "cmd" with
arguments [...]` bypasses tokenization entirely and passes arguments
through untouched, which is the safer form for anything built from
untrusted data.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import List, Optional

from ..errors import EzyRuntimeError
from ..values import ProcessResult


def run_command(command: str, arguments: Optional[List[str]] = None,
                 timeout: Optional[float] = None) -> ProcessResult:
    if arguments is not None:
        argv = [command, *arguments]
    else:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise EzyRuntimeError(f"could not parse command: {exc}", "ProcessError") from exc
    if not argv:
        raise EzyRuntimeError("empty command", "ProcessError")
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ProcessResult(
            output=completed.stdout,
            error=completed.stderr,
            exit_code=completed.returncode,
            ok=completed.returncode == 0,
        )
    except FileNotFoundError as exc:
        return ProcessResult(output="", error=f"command not found: {argv[0]}", exit_code=127, ok=False)
    except subprocess.TimeoutExpired:
        return ProcessResult(output="", error="process timed out", exit_code=124, ok=False, timed_out=True)
    except PermissionError as exc:
        return ProcessResult(output="", error=str(exc), exit_code=126, ok=False)


def run_pipeline(commands: List[str]) -> ProcessResult:
    """Connect stdout -> stdin across a chain of commands, à la a shell pipe."""
    if not commands:
        raise EzyRuntimeError("empty pipeline", "ProcessError")
    argvs = []
    for cmd in commands:
        try:
            argvs.append(shlex.split(cmd))
        except ValueError as exc:
            raise EzyRuntimeError(f"could not parse command: {exc}", "ProcessError") from exc
    procs = []
    try:
        prev_stdout = None
        for i, argv in enumerate(argvs):
            is_last = i == len(argvs) - 1
            proc = subprocess.Popen(
                argv,
                stdin=prev_stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if is_last else subprocess.PIPE,
                text=True,
            )
            if prev_stdout is not None:
                prev_stdout.close()
            prev_stdout = proc.stdout
            procs.append(proc)
    except FileNotFoundError as exc:
        for p in procs:
            p.kill()
        return ProcessResult(output="", error=f"command not found: {exc.filename}", exit_code=127, ok=False)
    out, err = procs[-1].communicate()
    for p in procs[:-1]:
        p.wait()
    exit_code = procs[-1].returncode
    return ProcessResult(output=out, error=err or "", exit_code=exit_code, ok=exit_code == 0)
