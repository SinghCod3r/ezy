import pytest
from ezy.parser import parse
from ezy.linter import lint_program

def run_lint(source: str):
    prog = parse(source, "test.ezy")
    return lint_program(prog, "test.ezy")

def test_linter_e101_undefined_variable():
    findings = run_lint("say x\nx = 1\n")
    assert len(findings) == 1
    assert findings[0].code == "E101"

def test_linter_no_e101_for_implicit():
    findings = run_lint("x = 10\nsay x\n")
    assert len(findings) == 0

def test_linter_no_e101_for_builtins():
    findings = run_lint("say length([1, 2])\n")
    assert len(findings) == 0

def test_linter_e102_reassigned_const():
    findings = run_lint("const a = 1\na = 2\nsay a\n")
    assert len(findings) == 1
    assert findings[0].code == "E102"

def test_linter_w202_unused_variable():
    findings = run_lint("let x = 1\nconst y = 2\nsay y\n")
    assert len(findings) == 1
    assert findings[0].code == "W202"
    assert "unused variable 'x'" in findings[0].message

def test_linter_no_w202_for_implicit():
    findings = run_lint("x = 1\n")
    assert len(findings) == 0

def test_linter_w202_unused_param():
    findings = run_lint("function foo x, y\n    say x\nfoo(1, 2)\n")
    assert len(findings) == 1
    assert findings[0].code == "W202"
    assert "unused variable 'y'" in findings[0].message

def test_linter_w203_unreachable_code():
    src = (
        "function foo\n"
        "    return 1\n"
        "    say \"unreachable\"\n"
        "    say \"also unreachable\"\n"
        "foo()\n"
    )
    findings = run_lint(src)
    assert len(findings) == 1
    assert findings[0].code == "W203"

def test_linter_w203_unreachable_break():
    src = (
        "while true\n"
        "    break\n"
        "    say \"unreachable\"\n"
    )
    findings = run_lint(src)
    assert len(findings) == 1
    assert findings[0].code == "W203"

def test_linter_no_w203_for_nested_returns():
    src = (
        "function foo x\n"
        "    if x > 0\n"
        "        return 1\n"
        "    say \"reachable\"\n"
        "    return 0\n"
        "foo(1)\n"
    )
    findings = run_lint(src)
    assert len(findings) == 0

def test_linter_closure_resolves_parent_reads():
    src = (
        "let x = 1\n"
        "function get_x\n"
        "    return x\n"
        "say get_x()\n"
    )
    findings = run_lint(src)
    assert len(findings) == 0

def test_linter_pipeline_it_is_defined():
    src = (
        "function double n\n"
        "    return n * 2\n"
        "let x = 5 -> double(it)\n"
    )
    findings = run_lint(src)
    # x and double are unused
    assert len(findings) == 1
    assert findings[0].code == "W202"
    assert "unused variable 'x'" in findings[0].message
