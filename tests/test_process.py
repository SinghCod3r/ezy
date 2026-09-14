import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


def test_run_simple_command(ezy):
    ezy.run('result = run "echo hello"\nsay result.output\n')
    assert ezy.lines == ["hello\n"]


def test_run_nonzero_exit(ezy):
    ezy.run('result = run "python3 -c \'import sys; sys.exit(3)\'"\nsay result.exit_code\nsay result.ok\n')
    assert ezy.lines == ["3", "false"]


def test_run_missing_command(ezy):
    ezy.run('result = run "this_command_does_not_exist_xyz"\nsay result.exit_code\nsay is_failed(result)\n')
    assert ezy.lines == ["127", "true"]


def test_run_with_arguments_avoids_shell_parsing(ezy):
    # A value that looks like shell syntax must be passed through literally.
    ezy.run('result = run "echo" with arguments ["a && b"]\nsay result.output\n')
    assert ezy.lines == ["a && b\n"]


def test_run_with_timeout(ezy):
    ezy.run('result = run "sleep 2" with timeout 1 seconds\nsay result.timed_out\n')
    assert ezy.lines == ["true"]


def test_is_successful_and_is_failed(ezy):
    ezy.run('r = run "true"\nsay r is successful\nr2 = run "false"\nsay r2 is failed\n')
    assert ezy.lines == ["true", "true"]


def test_process_pipeline(ezy):
    # stdout of the first command is connected to stdin of the second.
    src = 'result = run "echo hello" -> run "tr a-z A-Z"\nsay result.output\n'
    ezy.run(src)
    assert ezy.lines[0].strip() == "HELLO"
