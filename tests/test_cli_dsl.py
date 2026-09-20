import pytest
from ezy.parser import parse
from ezy.interpreter import Interpreter
from ezy.errors import EzyCliHelpRequest, EzyCliArgumentError
from ezy.ast_nodes import CliDef, CliFlag, CliOption

def test_parse_cli_def():
    source = """cli "deploy" desc "deploy app"
    flag "verbose" alias "v" desc "verbose logging"
    option "env" alias "e" default "prod" required desc "env"
"""
    prog = parse(source, "test")
    assert len(prog.statements) == 1
    cli = prog.statements[0]
    assert isinstance(cli, CliDef)
    assert cli.name == "deploy"
    assert cli.desc == "deploy app"
    assert len(cli.body) == 2
    
    flag = cli.body[0]
    assert isinstance(flag, CliFlag)
    assert flag.name == "verbose"
    assert flag.alias == "v"
    
    opt = cli.body[1]
    assert isinstance(opt, CliOption)
    assert opt.name == "env"
    assert opt.alias == "e"
    assert opt.required == True

def test_cli_execution_help_request():
    source = """cli "deploy"
    flag "verbose" alias "v"
"""
    interp = Interpreter()
    interp.arguments = ["--help"]
    prog = parse(source, "test")
    with pytest.raises(EzyCliHelpRequest):
        interp.run(prog)

def test_cli_execution_argument_error():
    source = """cli "deploy"
    option "env" required
"""
    interp = Interpreter()
    interp.arguments = []
    prog = parse(source, "test")
    with pytest.raises(EzyCliArgumentError):
        interp.run(prog)

def test_cli_execution_success():
    source = """cli "deploy"
    flag "verbose" alias "v"
    option "env" default "prod"
say cli.verbose
say cli.env
say cli.args
"""
    interp = Interpreter()
    interp.arguments = ["-v", "--env", "dev", "--", "app1", "app2"]
    prog = parse(source, "test")
    # Redirect output or just check global env
    interp.run(prog)
    cli_map = interp.global_env.get("cli")
    assert cli_map["verbose"] == True
    assert cli_map["env"] == "dev"
    assert cli_map["args"] == ["app1", "app2"]
