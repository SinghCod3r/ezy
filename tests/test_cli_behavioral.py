"""Behavioral tests for the Ezy CLI DSL.

Each test creates a temporary .ezy file, runs it via subprocess using
``python -m ezy.cli run <file> <args...>``, and asserts the exit code
and captured output.
"""

import os
import subprocess
import sys
import tempfile
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")


def _run_ezy(script_source: str, cli_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Write *script_source* to a temp .ezy file and run it via the CLI."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ezy", delete=False, dir=PROJECT_ROOT
    ) as f:
        f.write(textwrap.dedent(script_source))
        filepath = f.name

    try:
        cmd = [sys.executable, "-m", "ezy.cli", "run", filepath]
        if cli_args:
            cmd.extend(cli_args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": SRC_DIR},
        )
        return result
    finally:
        os.unlink(filepath)


# The base CLI script used by most tests
BASE_SCRIPT = """\
cli "deploy" desc "Deploy app"
    flag "verbose" alias "v" desc "Verbose"
    option "env" alias "e" default "dev" desc "Environment"
    option "port" alias "p" required desc "Port"

say "env={cli.env} port={cli.port} verbose={cli.verbose}"
say "args={cli.args}"
"""


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestHelpFlag:
    """1 & 2: --help / -h should print usage and exit 0."""

    def test_long_help(self):
        r = _run_ezy(BASE_SCRIPT, ["--help"])
        assert r.returncode == 0
        assert "deploy" in r.stdout.lower()

    def test_short_help(self):
        r = _run_ezy(BASE_SCRIPT, ["-h"])
        assert r.returncode == 0
        assert "deploy" in r.stdout.lower()


class TestLongOptions:
    """3: --env prod --port 8080 should produce correct output."""

    def test_long_options_space(self):
        r = _run_ezy(BASE_SCRIPT, ["--env", "prod", "--port", "8080"])
        assert r.returncode == 0
        assert "env=prod" in r.stdout
        assert "port=8080" in r.stdout
        assert "verbose=false" in r.stdout


class TestEqualsOptions:
    """4: --env=prod --port=8080 should also work."""

    def test_long_options_equals(self):
        r = _run_ezy(BASE_SCRIPT, ["--env=prod", "--port=8080"])
        assert r.returncode == 0
        assert "env=prod" in r.stdout
        assert "port=8080" in r.stdout


class TestShortAliases:
    """5: -e prod -p 8080 should resolve via aliases."""

    def test_short_aliases(self):
        r = _run_ezy(BASE_SCRIPT, ["-e", "prod", "-p", "8080"])
        assert r.returncode == 0
        assert "env=prod" in r.stdout
        assert "port=8080" in r.stdout


class TestDashValueForOption:
    """6: --env -xyz --port 8080 — '-xyz' treated as value for --env."""

    def test_dash_value(self):
        r = _run_ezy(BASE_SCRIPT, ["--env", "-xyz", "--port", "8080"])
        assert r.returncode == 0
        assert "env=-xyz" in r.stdout
        assert "port=8080" in r.stdout


class TestDoubleDash:
    """7: --port 8080 -- --not-an-option → args should contain '--not-an-option'."""

    def test_double_dash_separator(self):
        r = _run_ezy(BASE_SCRIPT, ["--port", "8080", "--", "--not-an-option"])
        assert r.returncode == 0
        assert "--not-an-option" in r.stdout


class TestPositionalArgs:
    """8: pos1 --port 8080 pos2 → args=[pos1, pos2]."""

    def test_positional_mixed(self):
        r = _run_ezy(BASE_SCRIPT, ["pos1", "--port", "8080", "pos2"])
        assert r.returncode == 0
        out = r.stdout
        assert "pos1" in out
        assert "pos2" in out
        assert "port=8080" in out


class TestDuplicateOption:
    """9: --env dev --env prod --port 8080 → last wins, env=prod."""

    def test_last_wins(self):
        r = _run_ezy(BASE_SCRIPT, ["--env", "dev", "--env", "prod", "--port", "8080"])
        assert r.returncode == 0
        assert "env=prod" in r.stdout


class TestRepeatedFlag:
    """10: --verbose --verbose --port 8080 → verbose=true (no error)."""

    def test_repeated_flag(self):
        r = _run_ezy(BASE_SCRIPT, ["--verbose", "--verbose", "--port", "8080"])
        assert r.returncode == 0
        assert "verbose=true" in r.stdout


class TestUnknownOption:
    """11: --xyz --port 8080 → exit 2 (CLI argument error)."""

    def test_unknown_option(self):
        r = _run_ezy(BASE_SCRIPT, ["--xyz", "--port", "8080"])
        assert r.returncode == 2


class TestMissingOptionValue:
    """12: --port 8080 --env (at end) → exit 2 (missing value for --env)."""

    def test_missing_value(self):
        r = _run_ezy(BASE_SCRIPT, ["--port", "8080", "--env"])
        assert r.returncode == 2


class TestMissingRequiredOption:
    """13: --env prod (without --port) → exit 2 (missing required --port)."""

    def test_missing_required(self):
        r = _run_ezy(BASE_SCRIPT, ["--env", "prod"])
        assert r.returncode == 2


class TestDuplicateCliDefinition:
    """14: Two cli blocks → runtime error (exit 1 or 2)."""

    def test_duplicate_cli_block(self):
        script = """\
        cli "app1" desc "First"
            flag "x"

        cli "app2" desc "Second"
            flag "y"

        say "should not reach here"
        """
        r = _run_ezy(script, ["--x"])
        # Should fail at runtime because "only one cli block is permitted"
        assert r.returncode == 2  # EzyRuntimeError → EXIT_RUNTIME_ERROR
        assert "cli" in r.stderr.lower() or "one" in r.stderr.lower()


class TestCliInsideFunction:
    """15: CLI inside a function → should parse OK but fail at runtime
    because the interpreter checks ``env.parent is not None``."""

    def test_cli_inside_function(self):
        script = """\
        fn setup()
            cli "inner" desc "Bad"
                flag "x"

        setup()
        """
        r = _run_ezy(script)
        # Runtime error: "cli block must be at the top level"
        assert r.returncode == 2
        assert "top level" in r.stderr.lower() or "cli" in r.stderr.lower()


class TestRawArguments:
    """16: `arguments` should remain the raw argv list even when a CLI
    block is present."""

    def test_raw_arguments(self):
        script = """\
        say "raw={arguments}"

        cli "tool"
            option "port" alias "p" required desc "Port"

        say "port={cli.port}"
        """
        r = _run_ezy(script, ["--port", "9090"])
        assert r.returncode == 0
        out = r.stdout
        # `arguments` is set before CLI parsing so it should contain raw argv
        assert "--port" in out
        assert "9090" in out
        assert "port=9090" in out


class TestNoCliScript:
    """17: A script without a CLI block should just work."""

    def test_plain_say(self):
        r = _run_ezy('say "hello"')
        assert r.returncode == 0
        assert "hello" in r.stdout


class TestDefaultValue:
    """Bonus: verify default value is used when option is not provided."""

    def test_default_value(self):
        r = _run_ezy(BASE_SCRIPT, ["--port", "3000"])
        assert r.returncode == 0
        assert "env=dev" in r.stdout  # default for --env is "dev"
        assert "port=3000" in r.stdout


class TestFlagWithShortAlias:
    """Bonus: -v should toggle verbose flag."""

    def test_short_flag(self):
        r = _run_ezy(BASE_SCRIPT, ["-v", "--port", "3000"])
        assert r.returncode == 0
        assert "verbose=true" in r.stdout


class TestHelpContent:
    """Bonus: help output should include option descriptions and required markers."""

    def test_help_content_details(self):
        r = _run_ezy(BASE_SCRIPT, ["--help"])
        assert r.returncode == 0
        assert "verbose" in r.stdout.lower()
        assert "port" in r.stdout.lower()
        assert "required" in r.stdout.lower()
        assert "environment" in r.stdout.lower() or "env" in r.stdout.lower()
