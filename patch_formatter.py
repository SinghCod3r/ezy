with open("src/ezy/formatter.py", "r") as f:
    c = f.read()

import re

new_funcs = """        elif isinstance(stmt, A.CliDef):
            res = f"cli \\"{stmt.name}\\""
            if stmt.desc:
                res += f" desc \\"{stmt.desc}\\""
            out_parts = [comments + indent + res + inline]
            
            for child in stmt.body:
                ind2 = indent + "    "
                cc = self.get_standalone_comments(child.line)
                if cc:
                    cc = "".join(ind2 + line + "\\n" for line in cc.strip().split("\\n"))
                ic = self.get_inline_comments(child.line)
                
                if isinstance(child, A.CliFlag):
                    line_str = f"flag \\"{child.name}\\""
                    if child.alias:
                        line_str += f" alias \\"{child.alias}\\""
                    if child.desc:
                        line_str += f" desc \\"{child.desc}\\""
                    out_parts.append(cc + ind2 + line_str + ic)
                elif isinstance(child, A.CliOption):
                    line_str = f"option \\"{child.name}\\""
                    if child.alias:
                        line_str += f" alias \\"{child.alias}\\""
                    if child.default:
                        line_str += f" default {self.format_expr(child.default)}"
                    if child.required:
                        line_str += " required"
                    if child.desc:
                        line_str += f" desc \\"{child.desc}\\""
                    out_parts.append(cc + ind2 + line_str + ic)
            return "\\n".join(out_parts)"""

c = c.replace("        raise ValueError(f\"Formatter unsupported statement: {type(stmt).__name__}\")", new_funcs + "\n        raise ValueError(f\"Formatter unsupported statement: {type(stmt).__name__}\")")

with open("src/ezy/formatter.py", "w") as f:
    f.write(c)

