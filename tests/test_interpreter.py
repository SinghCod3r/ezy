import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from ezy.errors import EzyRuntimeError


def test_say_and_interpolation(ezy):
    out = ezy.run('name = "World"\nsay "Hello {name}"\n')
    assert out == ["Hello World"]


def test_arithmetic_int_vs_float(ezy):
    ezy.run("say 1 + 2\nsay 1 / 2\nsay 4 / 2\nsay 2.5 + 1\n")
    assert ezy.lines == ["3", "0.5", "2", "3.5"]


def test_division_by_zero(ezy):
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run("say 1 / 0\n")
    assert exc.value.error_type == "MathError"


def test_string_concat_with_number(ezy):
    ezy.run('say "Age: " + 22\n')
    assert ezy.lines == ["Age: 22"]


def test_boolean_and_null_display(ezy):
    ezy.run("say true\nsay false\nsay null\n")
    assert ezy.lines == ["true", "false", "null"]


def test_if_otherwise(ezy):
    ezy.run("if 1 > 2\n    say \"no\"\notherwise\n    say \"yes\"\n")
    assert ezy.lines == ["yes"]


def test_elif_chain(ezy):
    src = (
        "x = 2\n"
        "if x == 1\n    say \"one\"\n"
        "otherwise if x == 2\n    say \"two\"\n"
        "otherwise\n    say \"other\"\n"
    )
    ezy.run(src)
    assert ezy.lines == ["two"]


def test_for_each_list(ezy):
    ezy.run("for each n in [1, 2, 3]\n    say n\n")
    assert ezy.lines == ["1", "2", "3"]


def test_for_each_empty_list(ezy):
    ezy.run("for each n in []\n    say n\nsay \"done\"\n")
    assert ezy.lines == ["done"]


def test_for_range_descending(ezy):
    ezy.run("for n from 3 to 1\n    say n\n")
    assert ezy.lines == ["3", "2", "1"]


def test_repeat_times(ezy):
    ezy.run("repeat 3 times\n    say \"hi\"\n")
    assert ezy.lines == ["hi", "hi", "hi"]


def test_while_with_break_continue(ezy):
    src = (
        "n = 0\n"
        "while n < 10\n"
        "    n = n + 1\n"
        "    if n == 3\n"
        "        continue\n"
        "    if n == 5\n"
        "        break\n"
        "    say n\n"
    )
    ezy.run(src)
    assert ezy.lines == ["1", "2", "4"]


def test_function_call_and_recursion(ezy):
    src = (
        "function factorial n\n"
        "    if n <= 1\n"
        "        return 1\n"
        "    return n * factorial(n - 1)\n"
        "say factorial(5)\n"
    )
    ezy.run(src)
    assert ezy.lines == ["120"]


def test_function_default_argument(ezy):
    src = 'function greet name, greeting = "Hi"\n    say "{greeting}, {name}"\nsay greet("Ayush")\n'
    ezy.run('function greet name, greeting = "Hi"\n    say "{greeting}, {name}"\ngreet("Ayush")\n')
    assert ezy.lines == ["Hi, Ayush"]


def test_missing_argument_raises(ezy):
    with pytest.raises(EzyRuntimeError):
        ezy.run("function add a, b\n    return a + b\nsay add(1)\n")


def test_undefined_variable_raises(ezy):
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run("say missing_variable\n")
    assert exc.value.error_type == "NameError"


def test_type_mismatch_comparison_raises(ezy):
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run('if 1 > "a"\n    say "x"\n')
    assert exc.value.error_type == "TypeError"


def test_list_index_out_of_range(ezy):
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run("x = [1, 2]\nsay x[5]\n")
    assert exc.value.error_type == "IndexError"


def test_map_missing_key_is_null(ezy):
    ezy.run('x = {"a": 1}\nsay x.b\n')
    assert ezy.lines == ["null"]


def test_list_and_map_literals_display(ezy):
    ezy.run('say [1, 2, 3]\nsay {"a": 1}\n')
    assert ezy.lines == ["[1, 2, 3]", "{a: 1}"]


def test_try_catch_recovers(ezy):
    src = (
        "try\n"
        "    x = 1 / 0\n"
        "catch err\n"
        "    say \"caught: {err.type}\"\n"
    )
    ezy.run(src)
    assert ezy.lines == ["caught: MathError"]


def test_break_continue_outside_loop_raises(ezy):
    with pytest.raises(EzyRuntimeError):
        ezy.run("break\n")


def test_scope_function_level_not_block_level(ezy):
    src = (
        "if true\n"
        "    x = 42\n"
        "say x\n"
    )
    ezy.run(src)
    assert ezy.lines == ["42"]


def test_let_shadowing_inside_function(ezy):
    src = (
        "x = 1\n"
        "function f\n"
        "    let x = 2\n"
        "    say x\n"
        "f()\n"
        "say x\n"
    )
    ezy.run(src)
    assert ezy.lines == ["2", "1"]


def test_const_reassignment_raises(ezy):
    with pytest.raises(EzyRuntimeError):
        ezy.run("const x = 1\nx = 2\n")


def test_closures_capture_environment(ezy):
    src = (
        "function make_adder n\n"
        "    function add x\n"
        "        return x + n\n"
        "    return add\n"
        "adder = make_adder(10)\n"
        "say adder(5)\n"
    )
    ezy.run(src)
    assert ezy.lines == ["15"]


def test_matches_operator(ezy):
    ezy.run('if "hello world" matches "^hello"\n    say "matched"\n')
    assert ezy.lines == ["matched"]


def test_builtin_string_functions(ezy):
    ezy.run('say upper("abc")\nsay lower("ABC")\nsay trim("  hi  ")\nsay length("abcd")\n')
    assert ezy.lines == ["ABC", "abc", "hi", "4"]


def test_builtin_json_roundtrip(ezy):
    # Literal braces inside a string must be escaped since {...} is the
    # interpolation syntax; see docs/limitations.md.
    src = 'data = parse_json("\\{\\"a\\": 1, \\"b\\": [1,2,3]\\}")\nsay data.a\nsay length(data.b)\n'
    ezy.run(src)
    assert ezy.lines == ["1", "3"]


def test_map_filter_reduce(ezy):
    src = (
        "function is_even n\n    return n % 2 == 0\n"
        "function double n\n    return n * 2\n"
        "evens = filter([1,2,3,4,5,6], is_even)\n"
        "doubled = map(evens, double)\n"
        "say doubled\n"
    )
    ezy.run(src)
    assert ezy.lines == ["[4, 8, 12]"]


def test_pipeline_with_it(ezy):
    src = (
        "function double n\n    return n * 2\n"
        "x = 5 -> double(it)\n"
        "say x\n"
    )
    ezy.run(src)
    assert ezy.lines == ["10"]
