from __future__ import annotations

from pathlib import Path

from app.core.state import SymbolInfo, TestGenState


def generated_tests_dir(state: TestGenState) -> Path:
    path = state.ensure_output_dir() / "generated_tests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_generated_file(state: TestGenState, filename: str, content: str) -> str:
    path = generated_tests_dir(state) / filename
    path.write_text(content, encoding="utf-8")
    state.generated_files[str(path)] = content
    return str(path)


def header(repo_path: str) -> str:
    return f'''"""由 pyrepo-test-agent 生成。

这些测试会保持审慎：验证可导入性、符号存在性和框架注册状态，
不猜测静态分析无法证明的业务输出。
"""

from pathlib import Path
import importlib
import inspect
import sys

import pytest


REPO_ROOT = Path({str(repo_path)!r})
SRC_ROOT = REPO_ROOT / "src"
for candidate in (REPO_ROOT, SRC_ROOT):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


'''


def compact_symbol_rows(symbols: list[SymbolInfo]) -> list[tuple[str, str, str, str]]:
    rows = []
    for symbol in symbols:
        rows.append((symbol.module_name, symbol.name, symbol.kind, symbol.signature))
    return rows
