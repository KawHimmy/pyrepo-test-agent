from pathlib import Path

from app.parsers.ast_parser import analyze_python_file, discover_python_files


def test_ast_parser_discovers_symbols_and_docstrings(tmp_path: Path) -> None:
    module = tmp_path / "math_tools.py"
    module.write_text(
        '''
def add(left: int, right: int) -> int:
    """返回两数之和。"""
    return left + right


class Box:
    def value(self):
        return 1
''',
        encoding="utf-8",
    )

    files = discover_python_files(str(tmp_path))
    assert files == [module]

    analysis = analyze_python_file(module, str(tmp_path))
    assert analysis.module_name == "math_tools"
    assert [symbol.name for symbol in analysis.symbols] == ["add", "Box"]
    assert analysis.symbols[0].docstring == "返回两数之和。"
