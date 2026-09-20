from ezy.formatter import format_source
from ezy.parser import parse
from ezy.interpreter import Interpreter
import pytest
import os
import subprocess
from io import StringIO
import sys

def run_ezy_code(src: str) -> str:
    from ezy.interpreter import Interpreter
    from ezy.parser import parse
    program = parse(src, "test.ezy")
    interpreter = Interpreter()
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        interpreter.run(program)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

def test_formatter_semantic_preservation_by_execution():
    src = """\
let x = 2
let y = 3
say x + y * 4

if x > 0
    say "positive"
otherwise
    say "negative"

function foo a, b = 1
    return a + b
say foo(10)
say foo(10, 5)

let arr = [1, 2, 3]
for each i in arr
    say i
"""
    out1 = run_ezy_code(src)
    formatted = format_source(src)
    out2 = run_ezy_code(formatted)
    assert out1 == out2
    assert "14" in out1
    assert "positive" in out1

def test_formatter_idempotence_with_comments():
    src = """\
# Header comment
let x = 10 # inline 1

# Block comment
# spanning two lines
function test
    # inside function
    say x # inline 2

# before call
test()
# eof comment"""
    f1 = format_source(src)
    f2 = format_source(f1)
    assert f1 == f2
    assert "# Header comment" in f1
    assert "let x = 10  # inline 1" in f1
    assert "say x  # inline 2" in f1
    assert "# eof comment" in f1

def test_operator_precedence():
    src = """\
say a + b * c
say (a + b) * c
say a * (b + c)
say a - (b - c)
say (a - b) - c
say a and b or c
"""
    f = format_source(src)
    # the parens for left-associative operations at same precedence should be removed,
    # but kept for right child.
    assert "say a + b * c" in f
    assert "say (a + b) * c" in f
    assert "say a * (b + c)" in f
    assert "say a - (b - c)" in f
    assert "say a - b - c" in f
    assert "say a and b or c" in f

def test_string_handling():
    src = 'say "hello \\"world\\""\nsay "C:\\\\temp"\nsay "hello {name}"\n'
    f = format_source(src)
    assert 'say "hello \\"world\\""' in f
    assert 'say "C:\\\\temp"' in f
    assert 'say "hello {name}"' in f

def test_formatter_cli_safety(tmp_path):
    bad_file = tmp_path / "bad.ezy"
    original = "let x = 1\nif\nsay x"
    bad_file.write_text(original)
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    res = subprocess.run(["python3", "-m", "ezy.cli", "fmt", str(bad_file)], env=env, capture_output=True, text=True)
    
    assert res.returncode != 0
    assert "syntax error" in res.stderr.lower()
    assert bad_file.read_text() == original

def test_formatter_cli_check_mode(tmp_path):
    f = tmp_path / "check.ezy"
    f.write_text("let x =    1\n")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    
    # check mode fails
    res1 = subprocess.run(["python3", "-m", "ezy.cli", "fmt", "--check", str(f)], env=env, capture_output=True, text=True)
    assert res1.returncode != 0
    
    # normal format
    res2 = subprocess.run(["python3", "-m", "ezy.cli", "fmt", str(f)], env=env, capture_output=True, text=True)
    assert res2.returncode == 0
    
    # check mode passes
    res3 = subprocess.run(["python3", "-m", "ezy.cli", "fmt", "--check", str(f)], env=env, capture_output=True, text=True)
    assert res3.returncode == 0
