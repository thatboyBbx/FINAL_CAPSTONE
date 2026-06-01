"""Ad-hoc cleanup scanner. Not part of the application.
Run from EXPERIMENT/ as:
    .venv/Scripts/python.exe _cleanup_scan.py
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SCAN_DIRS = ["app", "scripts", "tests"]
SKIP_DIRS = {"__pycache__", ".venv", ".git", ".pytest_cache", "node_modules"}


def walk_py(base: Path):
    for p in base.rglob("*.py"):
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        yield p


def used_names(tree: ast.AST) -> set[str]:
    used: set[str] = set()

    class V(ast.NodeVisitor):
        def visit_Name(self, n):
            used.add(n.id)
        def visit_Attribute(self, n):
            # walk to the root Name
            cur = n
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                used.add(cur.id)
            self.generic_visit(n)
        def visit_arg(self, n):
            if n.annotation:
                self.visit(n.annotation)

    V().visit(tree)
    # Also pick up names referenced in string annotations (PEP 563/604) — heuristic only
    return used


def is_noqa(line: str) -> bool:
    return "noqa" in line


def imports_in(tree: ast.AST):
    """Yield (lineno, end_lineno, alias_name, original_module, kind)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                name = a.asname or a.name.split(".")[0]
                yield (node.lineno, node.end_lineno or node.lineno, name, a.name, "import")
        elif isinstance(node, ast.ImportFrom):
            # __future__ imports are required side-effect imports — skip
            if node.module == "__future__":
                continue
            for a in node.names:
                if a.name == "*":
                    continue
                name = a.asname or a.name
                yield (node.lineno, node.end_lineno or node.lineno, name, f"{node.module}.{a.name}", "from")


def scan_file(p: Path) -> list[tuple[int, str, str]]:
    src = p.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [(0, "<syntax>", f"syntax error: {e}")]
    lines = src.splitlines()
    used = used_names(tree)
    # also check raw text for string-based usage (forward refs)
    raw = src
    results = []
    for lineno, end, name, full, kind in imports_in(tree):
        if name in used:
            continue
        # skip noqa-marked lines
        if any(is_noqa(lines[i]) for i in range(lineno - 1, min(end, len(lines)))):
            continue
        # skip __init__ side-effect re-exports if module exposes __all__ containing name
        # heuristic: check if name appears anywhere else in file (e.g. __all__)
        if f"\"{name}\"" in raw or f"'{name}'" in raw:
            continue
        results.append((lineno, name, full))
    return results


def main():
    total = 0
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in walk_py(base):
            findings = scan_file(p)
            if findings:
                rel = p.relative_to(ROOT).as_posix()
                for lineno, name, full in findings:
                    print(f"{rel}:{lineno}: unused '{name}' (from '{full}')")
                    total += 1
    print(f"\n{total} unused-import findings")


if __name__ == "__main__":
    main()
