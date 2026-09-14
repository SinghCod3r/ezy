import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from ezy.lexer import tokenize
from ezy.errors import EzySyntaxError


def types(tokens):
    return [t.type for t in tokens]


def test_empty_input():
    assert types(tokenize("")) == ["EOF"]


def test_whitespace_only():
    assert types(tokenize("   \n\n   \n")) == ["EOF"]


def test_comment_only():
    assert types(tokenize("# just a comment\n")) == ["EOF"]


def test_simple_assignment():
    toks = tokenize('name = "Ayush"\n')
    assert types(toks) == ["NAME", "ASSIGN", "STRING", "NEWLINE", "EOF"]


def test_numbers():
    toks = tokenize("x = 42\ny = 3.14\n")
    values = [t.value for t in toks if t.type == "NUMBER"]
    assert values == [42, 3.14]
    assert isinstance(values[0], int)
    assert isinstance(values[1], float)


def test_string_escapes():
    toks = tokenize('s = "line1\\nline2"\n')
    string_tok = toks[2]
    assert string_tok.value == ["line1\nline2"]


def test_string_interpolation_parts():
    toks = tokenize('s = "Hello {name}!"\n')
    string_tok = toks[2]
    assert string_tok.value[0] == "Hello "
    assert string_tok.value[1] == ("expr", "name")
    assert string_tok.value[2] == "!"


def test_unterminated_string_raises():
    with pytest.raises(EzySyntaxError):
        tokenize('s = "unterminated\n')


def test_indent_dedent():
    src = "if true\n    say 1\nsay 2\n"
    toks = tokenize(src)
    t = types(toks)
    assert "INDENT" in t
    assert "DEDENT" in t
    assert t.index("INDENT") < t.index("DEDENT")


def test_inconsistent_indentation_raises():
    src = "if true\n  say 1\n say 2\n"
    with pytest.raises(EzySyntaxError):
        tokenize(src)


def test_tabs_rejected():
    with pytest.raises(EzySyntaxError):
        tokenize("if true\n\tsay 1\n")


def test_blank_lines_between_dedented_blocks():
    src = "if true\n    say 1\n\nsay 2\n"
    toks = tokenize(src)
    # should not raise, and should produce exactly one DEDENT before 'say 2'
    assert types(toks).count("DEDENT") == 1


def test_unicode_arrow_and_ascii_arrow_equivalent():
    a = types(tokenize('x -> y\n'))
    b = types(tokenize('x \u2192 y\n'))
    assert a == b


def test_symbols():
    toks = tokenize("a == b != c <= d >= e\n")
    assert types(toks) == ["NAME", "EQ", "NAME", "NEQ", "NAME", "LE", "NAME", "GE", "NAME", "NEWLINE", "EOF"]
