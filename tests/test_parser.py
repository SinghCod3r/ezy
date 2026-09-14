import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from ezy.parser import parse
from ezy import ast_nodes as A
from ezy.errors import EzySyntaxError


def test_assignment():
    prog = parse('x = 5\n')
    assert isinstance(prog.statements[0], A.Assignment)
    assert prog.statements[0].target.name == "x"


def test_let_and_const():
    prog = parse('let a = 1\nconst b = 2\n')
    assert prog.statements[0].declared == "let"
    assert prog.statements[1].declared == "const"


def test_if_otherwise_if_otherwise():
    src = (
        "if x == 1\n"
        "    say 1\n"
        "otherwise if x == 2\n"
        "    say 2\n"
        "otherwise\n"
        "    say 3\n"
    )
    prog = parse(src)
    stmt = prog.statements[0]
    assert isinstance(stmt, A.IfStatement)
    assert len(stmt.elif_clauses) == 1
    assert stmt.else_body is not None


def test_for_each_and_for_range():
    prog = parse("for each x in items\n    say x\n")
    assert isinstance(prog.statements[0], A.ForEachStatement)
    prog2 = parse("for n from 1 to 10\n    say n\n")
    assert isinstance(prog2.statements[0], A.ForRangeStatement)


def test_repeat_and_while():
    prog = parse("repeat 5 times\n    say 1\n")
    assert isinstance(prog.statements[0], A.RepeatStatement)
    prog2 = parse("while true\n    say 1\n")
    assert isinstance(prog2.statements[0], A.WhileStatement)


def test_function_def_with_default():
    prog = parse("function greet name, greeting = \"Hi\"\n    say greeting\n")
    fn = prog.statements[0]
    assert isinstance(fn, A.FunctionDef)
    assert fn.params[0] == ("name", None)
    assert fn.params[1][0] == "greeting"
    assert isinstance(fn.params[1][1], A.Literal)


def test_try_catch():
    src = "try\n    say 1\ncatch err\n    say err.message\n"
    prog = parse(src)
    assert isinstance(prog.statements[0], A.TryStatement)
    assert prog.statements[0].error_name == "err"


def test_operator_precedence():
    prog = parse("x = 1 + 2 * 3\n")
    value = prog.statements[0].value
    assert isinstance(value, A.BinaryOp)
    assert value.op == "PLUS"
    assert isinstance(value.right, A.BinaryOp)
    assert value.right.op == "STAR"


def test_comparison_and_logic():
    prog = parse("x = a > 1 and b < 2 or not c\n")
    value = prog.statements[0].value
    assert isinstance(value, A.LogicalOp)
    assert value.op == "or"


def test_list_and_map_literals():
    prog = parse('x = [1, 2, 3]\ny = {"a": 1, "b": 2}\n')
    assert isinstance(prog.statements[0].value, A.ListLiteral)
    assert isinstance(prog.statements[1].value, A.MapLiteral)


def test_member_and_index_access():
    prog = parse("x = a.b[0].c\n")
    value = prog.statements[0].value
    assert isinstance(value, A.MemberAccess)
    assert value.name == "c"


def test_call_expression():
    prog = parse("x = add(1, 2)\n")
    value = prog.statements[0].value
    assert isinstance(value, A.Call)
    assert len(value.args) == 2


def test_string_interpolation_ast():
    prog = parse('say "Hi {name}, you are {age} years old"\n')
    expr = prog.statements[0].expr
    assert isinstance(expr, A.InterpolatedString)
    assert expr.parts[0] == "Hi "
    assert isinstance(expr.parts[1], A.Identifier)


def test_http_get_with_modifiers():
    src = 'response = get url with header {"Authorization": "Bearer x"} with timeout 5 seconds\n'
    prog = parse(src)
    req = prog.statements[0].value
    assert isinstance(req, A.HttpRequest)
    assert req.method == "GET"
    assert req.modifiers[0][0] == "header_map"
    assert req.modifiers[1][0] == "timeout"


def test_http_post_send_json():
    src = 'response = post url send json {"name": "Ayush"}\n'
    prog = parse(src)
    req = prog.statements[0].value
    assert req.modifiers[0][0] == "json_body"


def test_run_process_with_arguments():
    src = 'result = run "git" with arguments ["status"]\n'
    prog = parse(src)
    node = prog.statements[0].value
    assert isinstance(node, A.RunProcess)
    assert node.modifiers[0][0] == "arguments"


def test_file_statements():
    prog = parse('create file "a.txt"\nwrite "hi" to "a.txt"\nappend "!" to "a.txt"\ndelete file "a.txt"\n')
    assert isinstance(prog.statements[0], A.CreateFileStatement)
    assert isinstance(prog.statements[1], A.WriteStatement)
    assert prog.statements[2].append is True
    assert isinstance(prog.statements[3], A.DeleteStatement)


def test_file_exists_expression():
    prog = parse('if file "x" exists\n    say 1\n')
    cond = prog.statements[0].condition
    assert isinstance(cond, A.FileExistsCheck)
    assert cond.kind == "file"


def test_download_statement():
    prog = parse('download "http://x/file.zip"\nsave as "file.zip"\n')
    assert isinstance(prog.statements[0], A.DownloadStatement)


def test_parallel_block():
    src = "parallel\n    a = get url1\n    b = get url2\n"
    prog = parse(src)
    assert isinstance(prog.statements[0], A.ParallelStatement)
    assert len(prog.statements[0].assignments) == 2


def test_parallel_rejects_non_assignment():
    src = "parallel\n    say 1\n"
    with pytest.raises(EzySyntaxError):
        parse(src)


def test_pipeline_expression():
    prog = parse('x = files -> filter(it, is_python) -> sort(it)\n')
    value = prog.statements[0].value
    assert isinstance(value, A.PipelineExpr)
    assert len(value.stages) == 3


def test_matches_operator():
    prog = parse('if text matches "^hello"\n    say 1\n')
    assert isinstance(prog.statements[0].condition, A.MatchesOp)


def test_is_successful_postfix():
    prog = parse('if response is successful\n    say 1\n')
    cond = prog.statements[0].condition
    assert isinstance(cond, A.Call)
    assert cond.callee.name == "is_successful"


def test_syntax_error_reports_location():
    with pytest.raises(EzySyntaxError) as exc_info:
        parse("x = \n")
    assert exc_info.value.line == 1


def test_use_statement():
    prog = parse('use "http"\n')
    assert isinstance(prog.statements[0], A.UseStatement)
    assert prog.statements[0].module == "http"


def test_wait_statement():
    prog = parse("wait 5 seconds\n")
    assert isinstance(prog.statements[0], A.WaitStatement)
