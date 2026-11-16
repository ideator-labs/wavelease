"""Static Python code graph: which file defines each symbol, and who calls whom."""
import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CodeGraph:
    files: dict = field(default_factory=dict)      # qualname (module or module.func) -> repo-relative file
    calls: dict = field(default_factory=dict)      # caller qualname -> set of callee qualnames
    imports: dict = field(default_factory=dict)    # module -> set of imported qualnames

    def callers(self, symbol):
        return {c for c, callees in self.calls.items() if symbol in callees}


def _module_name(root, path):
    return ".".join(path.relative_to(root).with_suffix("").parts).removesuffix(".__init__")


def build(root):
    root = Path(root)
    g = CodeGraph()
    for path in sorted(root.rglob("*.py")):
        rel = str(path.relative_to(root))
        if rel.startswith("tests/"):
            continue
        mod = _module_name(root, path)
        tree = ast.parse(path.read_text())
        g.files[mod] = rel
        names = {}  # local name -> qualname
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    names[a.asname or a.name] = f"{node.module}.{a.name}"
            elif isinstance(node, ast.Import):
                for a in node.names:
                    names[a.asname or a.name] = a.name
            elif isinstance(node, ast.FunctionDef):
                names[node.name] = f"{mod}.{node.name}"
        g.imports[mod] = {q for q in names.values() if not q.startswith(mod + ".")}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            qual = f"{mod}.{node.name}"
            g.files[qual] = rel
            callees = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                f = sub.func
                if isinstance(f, ast.Name) and f.id in names:
                    callees.add(names[f.id])
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in names:
                    callees.add(f"{names[f.value.id]}.{f.attr}")
            g.calls[qual] = callees
    return g
