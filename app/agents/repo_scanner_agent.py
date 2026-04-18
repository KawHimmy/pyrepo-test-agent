from __future__ import annotations

from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.core.state import RepositoryInfo, TestGenState
from app.parsers.ast_parser import analyze_python_file, discover_python_files, is_test_file
from app.parsers.diff_parser import normalize_changed_files
from app.parsers.import_graph import build_import_graph


class RepoScannerAgent(BaseAgent):
    """识别 Python 文件、符号、API 路由、导入关系和测试缺口。"""

    async def execute(self, state: TestGenState) -> TestGenState:
        repo = Path(state.repo_path).resolve()
        if not repo.exists():
            raise FileNotFoundError(f"repo path does not exist: {repo}")
        if not repo.is_dir():
            raise NotADirectoryError(f"repo path is not a directory: {repo}")

        python_files = discover_python_files(str(repo))
        analyses = [analyze_python_file(path, str(repo)) for path in python_files]
        test_files = [path for path in python_files if is_test_file(path)]
        source_analyses = [analysis for analysis in analyses if not is_test_file(Path(analysis.file_path))]

        for analysis in analyses:
            for error in analysis.errors:
                state.add_warning(error)

        info = RepositoryInfo(
            repo_path=str(repo),
            python_files=[str(path) for path in python_files],
            test_files=[str(path) for path in test_files],
            changed_files=normalize_changed_files(str(repo), state.changed_files),
            module_graph=build_import_graph(source_analyses),
            target_symbols=[symbol for analysis in source_analyses for symbol in analysis.symbols],
            api_routes=[route for analysis in source_analyses for route in analysis.api_routes],
        )
        state.repository_info = info
        return state
