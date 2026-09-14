import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ezy.interpreter import Interpreter
from ezy.parser import parse


class Runner:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.lines = []
        self.interp = Interpreter(filename="<test>", script_dir=str(tmp_path), output=self.lines.append)

    def run(self, source):
        program = parse(source, "<test>")
        self.interp.run(program)
        return self.lines

    def out(self):
        return "\n".join(self.lines)


@pytest.fixture
def ezy(tmp_path):
    return Runner(tmp_path)
