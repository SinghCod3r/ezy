import subprocess
import sys
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
ENV = dict(os.environ)
ENV["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + ENV.get("PYTHONPATH", "")


def run_cli(args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "ezy.cli", *args],
        capture_output=True, text=True, env=ENV, cwd=cwd,
    )


def test_no_arguments_shows_usage():
    result = run_cli([])
    assert result.returncode == 0
    assert "Usage" in result.stdout


def test_version_flag():
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert "Ezy" in result.stdout


def test_run_missing_file():
    result = run_cli(["run", "/tmp/does_not_exist_xyz.ezy"])
    assert result.returncode == 64
    assert "no such file" in result.stderr


def test_run_success(tmp_path):
    script = tmp_path / "ok.ezy"
    script.write_text('say "hi"\n')
    result = run_cli(["run", str(script)])
    assert result.returncode == 0
    assert result.stdout.strip() == "hi"


def test_run_syntax_error_exit_code(tmp_path):
    script = tmp_path / "bad.ezy"
    script.write_text("if\n")
    result = run_cli(["run", str(script)])
    assert result.returncode == 1
    assert "syntax error" in result.stderr


def test_run_runtime_error_exit_code(tmp_path):
    script = tmp_path / "boom.ezy"
    script.write_text("say 1 / 0\n")
    result = run_cli(["run", str(script)])
    assert result.returncode == 2
    assert "MathError" in result.stderr


def test_check_valid_script(tmp_path):
    script = tmp_path / "ok.ezy"
    script.write_text('say "hi"\n')
    result = run_cli(["check", str(script)])
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_check_invalid_script(tmp_path):
    script = tmp_path / "bad.ezy"
    script.write_text("if\n")
    result = run_cli(["check", str(script)])
    assert result.returncode == 1


def test_run_shorthand_without_subcommand(tmp_path):
    script = tmp_path / "ok.ezy"
    script.write_text('say "hi"\n')
    result = run_cli([str(script)])
    assert result.returncode == 0
    assert result.stdout.strip() == "hi"


def test_command_line_arguments_reach_script(tmp_path):
    script = tmp_path / "args.ezy"
    script.write_text("for each a in arguments\n    say a\n")
    result = run_cli(["run", str(script), "one", "two"])
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["one", "two"]


def test_unknown_command():
    result = run_cli(["frobnicate"])
    assert result.returncode == 64


def test_local_module_import(tmp_path):
    (tmp_path / "utils.ezy").write_text(
        "function shout s\n    return upper(s) + \"!\"\n"
    )
    main = tmp_path / "main.ezy"
    main.write_text('use "./utils"\nsay utils.shout("hi")\n')
    result = run_cli(["run", str(main)])
    assert result.returncode == 0
    assert result.stdout.strip() == "HI!"


def test_unknown_builtin_module_raises(tmp_path):
    script = tmp_path / "bad_module.ezy"
    script.write_text('use "not_a_real_module"\n')
    result = run_cli(["run", str(script)])
    assert result.returncode == 2
    assert "ModuleError" in result.stderr
