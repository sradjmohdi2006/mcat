"""Build a static knowledge graph of the mcat codebase.

Outputs (written next to this script):
  knowledge_graph.json  - machine-readable graph: nodes + edges
  knowledge_graph.md    - human-readable reference summary

Run:  python build_knowledge_graph.py
"""
import ast
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
EXCLUDE = {"build", "dist", "__pycache__", ".git", "tests", ".pytest_cache"}


def iter_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def module_name(path):
    rel = os.path.relpath(path, ROOT).replace("\\", "/").replace("/", ".")
    return rel[:-3] if rel.endswith(".py") else rel


def short_doc(node):
    d = ast.get_docstring(node)
    if not d:
        return ""
    return d.strip().splitlines()[0][:100]


class ModuleInfo:
    def __init__(self, path):
        self.path = path
        self.mod = module_name(path)
        self.imports = []          # (target_module, symbol, alias)
        self.classes = []          # (name, line, bases, methods, doc)
        self.functions = []        # (name, line, doc)
        self.calls = []            # (caller_name, callee_name, line)
        self.defined = set()       # names defined locally (funcs, classes, imports)
        self.defined_kind = {}     # name -> "function" | "class" | "import"


def parse_file(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"  ! syntax error in {path}: {e}")
        return None
    info = ModuleInfo(path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                info.imports.append((a.name, None, a.asname))
                info.defined.add(a.asname or a.name.split(".")[0])
                info.defined_kind[a.asname or a.name.split(".")[0]] = "import"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                info.imports.append((mod, a.name, a.asname))
                info.defined.add(a.asname or a.name)
                info.defined_kind[a.asname or a.name] = "import"

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                bases.append(ast.unparse(b))
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append((item.name, item.lineno, short_doc(item)))
                    info.defined.add(item.name)
                    info.defined_kind[item.name] = "method"
            info.classes.append((node.name, node.lineno, bases, methods, short_doc(node)))
            info.defined.add(node.name)
            info.defined_kind[node.name] = "class"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions.append((node.name, node.lineno, short_doc(node)))
            info.defined.add(node.name)
            info.defined_kind[node.name] = "function"

    # Call edges: resolve Name/Attribute callees against locally defined names.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                callee = fn.id
            elif isinstance(fn, ast.Attribute):
                callee = fn.attr
            else:
                continue
            if callee in info.defined:
                # find enclosing function/class for caller
                caller = "module"
                for parent in ast.walk(tree):
                    pass
                info.calls.append((caller, callee, node.lineno))
    return info


def enclosing_name(tree, lineno):
    """Find the innermost function/method name containing line `lineno`."""
    best = ("module", None)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= (getattr(node, "end_lineno", node.lineno) or node.lineno):
                best = (node.name, node)
    return best[0]


def main():
    infos = []
    for path in sorted(iter_py_files()):
        info = parse_file(path)
        if info:
            infos.append(info)

    nodes = []
    edges = []
    node_ids = set()

    def add_node(nid, ntype, name, file, line, doc=""):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({"id": nid, "type": ntype, "name": name,
                          "file": file, "line": line, "doc": doc})

    for info in infos:
        add_node(info.mod, "module", info.mod, info.path, 1)
        # imports
        for mod, sym, alias in info.imports:
            target = mod if mod else sym
            edges.append({"source": info.mod, "target": target,
                          "type": "imports", "symbol": sym, "alias": alias})
        # classes + methods
        for cname, cline, bases, methods, cdoc in info.classes:
            cid = f"{info.mod}.{cname}"
            add_node(cid, "class", cname, info.path, cline, cdoc)
            edges.append({"source": info.mod, "target": cid, "type": "contains"})
            for b in bases:
                edges.append({"source": cid, "target": b, "type": "inherits"})
            for mname, mline, mdoc in methods:
                mid = f"{cid}.{mname}"
                add_node(mid, "method", mname, info.path, mline, mdoc)
                edges.append({"source": cid, "target": mid, "type": "contains"})
        # module-level functions
        for fname, fline, fdoc in info.functions:
            fid = f"{info.mod}.{fname}"
            add_node(fid, "function", fname, info.path, fline, fdoc)
            edges.append({"source": info.mod, "target": fid, "type": "contains"})

    # Call edges: re-walk with enclosing-name resolution
    for path in sorted(iter_py_files()):
        with open(path, encoding="utf-8") as f:
            src = f.read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        info = next(i for i in infos if i.path == path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    callee = fn.id
                elif isinstance(fn, ast.Attribute):
                    callee = fn.attr
                else:
                    continue
                if callee in info.defined:
                    caller = enclosing_name(tree, node.lineno)
                    caller_id = f"{info.mod}.{caller}"
                    callee_id = f"{info.mod}.{callee}"
                    if caller_id in node_ids and callee_id in node_ids:
                        edges.append({"source": caller_id, "target": callee_id,
                                      "type": "calls", "line": node.lineno})

    graph = {
        "project": "mcat",
        "root": ROOT,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    out_json = os.path.join(ROOT, "knowledge_graph.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1, ensure_ascii=False)
    print(f"Wrote {out_json}: {len(nodes)} nodes, {len(edges)} edges")

    # ---- Markdown summary ----
    md = ["# mcat Knowledge Graph", "",
          f"Auto-generated by `build_knowledge_graph.py` — {len(nodes)} nodes, {len(edges)} edges.", "",
          "## Modules", ""]
    for info in sorted(infos, key=lambda i: i.mod):
        md.append(f"### `{info.mod}`  ({os.path.relpath(info.path, ROOT)})")
        if info.classes:
            md.append("")
            md.append("**Classes**")
            for cname, cline, bases, methods, cdoc in info.classes:
                bstr = f"  ← {', '.join(bases)}" if bases else ""
                md.append(f"- `{cname}`{bstr}  — {cdoc or 'no doc'}")
                for mname, mline, mdoc in methods:
                    md.append(f"  - `{mname}()`  — {mdoc or ''}")
        if info.functions:
            md.append("")
            md.append("**Functions**")
            for fname, fline, fdoc in info.functions:
                md.append(f"- `{fname}()`  — {fdoc or ''}")
        md.append("")

    # import graph section
    md.append("## Import Graph")
    md.append("")
    for info in sorted(infos, key=lambda i: i.mod):
        if info.imports:
            targets = sorted({t for t, _, _ in info.imports})
            md.append(f"- `{info.mod}` → {', '.join(f'`{t}`' for t in targets)}")
    md.append("")

    # call graph: most-called internal functions
    md.append("## Top Internal Call Targets")
    md.append("")
    call_counts = defaultdict(int)
    for e in edges:
        if e["type"] == "calls":
            call_counts[e["target"]] += 1
    for target, cnt in sorted(call_counts.items(), key=lambda kv: -kv[1])[:25]:
        md.append(f"- `{target}` — {cnt} call(s)")
    md.append("")

    out_md = os.path.join(ROOT, "knowledge_graph.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()