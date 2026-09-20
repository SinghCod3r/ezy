from ezy.parser import parse

def test_columns():
    src = """\
let count = 42
say "hello"
if count > 10
    count = count - 1
"""
    # 012345678901234567
    # 1: let count = 42
    # 2: say "hello"
    # 3: if count > 10
    # 4:     count = count - 1

    prog = parse(src)
    
    # let count = 42
    # 'let' is at 1, 'count' is at 5, '42' is at 13
    assign1 = prog.statements[0]
    assert assign1.line == 1
    assert assign1.col == 1
    assert assign1.target.name == "count"
    assert assign1.target.line == 1
    assert assign1.target.col == 5
    assert assign1.value.value == 42
    assert assign1.value.line == 1
    assert assign1.value.col == 13

    # say "hello"
    # 'say' is at 1, '"hello"' is at 5
    say = prog.statements[1]
    assert say.line == 2
    assert say.col == 1
    assert say.expr.value == "hello"
    assert say.expr.line == 2
    assert say.expr.col == 5

    # if count > 10
    # 'if' is at 1, 'count' is at 4, '>' is at 10, '10' is at 12
    if_s = prog.statements[2]
    assert if_s.line == 3
    assert if_s.col == 1
    assert if_s.condition.left.name == "count"
    assert if_s.condition.left.col == 4
    assert if_s.condition.op == "GT"
    assert if_s.condition.col == 10
    assert if_s.condition.right.value == 10
    assert if_s.condition.right.col == 12

    # count = count - 1
    # 'count' (target) is at 5, 'count' (left) is at 13, '-' is at 19, '1' is at 21
    assign2 = if_s.then_body[0]
    assert assign2.line == 4
    assert assign2.col == 5
    assert assign2.target.name == "count"
    assert assign2.target.col == 5
    assert assign2.value.left.name == "count"
    assert assign2.value.left.col == 13
    assert assign2.value.op == "MINUS"
    assert assign2.value.col == 19
    assert assign2.value.right.value == 1
    assert assign2.value.right.col == 21

