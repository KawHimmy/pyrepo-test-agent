from __future__ import annotations

import ast
from pathlib import Path

from app.core.state import SymbolInfo


def symbol_source(symbol: SymbolInfo, max_chars: int = 6000) -> str:
    path = Path(symbol.file_path)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return source[:max_chars]

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol.name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment[:max_chars]
    return source[:max_chars]

