from ezy.parser import parse
from ezy.formatter import format_source
import sys

source = """cli "deploy" desc "deploy app"
    flag "verbose" alias "v" desc "verbose logging"
    option "env" alias "e" default "prod" required desc "env"

say "hello"
"""

f1 = format_source(source, "test")
f2 = format_source(f1, "test")

if f1 != f2:
    print("FORMATTER NOT IDEMPOTENT")
    sys.exit(1)
print("FORMATTER OK")
