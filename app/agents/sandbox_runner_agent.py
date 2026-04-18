from __future__ import annotations

from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.agents.test_writer_utils import generated_tests_dir
from app.core.state import TestGenState
from app.runners.pytest_runner import PytestRunner, load_coverage_summary


class SandboxRunnerAgent(BaseAgent):
    """运行生成的 pytest 文件并捕获执行结果。"""

    def __init__(self, timeout_seconds: int = 120) -> None:
        super().__init__()
        self.runner = PytestRunner(timeout_seconds=timeout_seconds)

    async def execute(self, state: TestGenState) -> TestGenState:
        tests_path = generated_tests_dir(state)
        if not any(Path(tests_path).glob("test_*.py")):
            state.add_warning("No generated pytest files were found.")
        coverage_path = state.ensure_output_dir() / "coverage.json"
        result = await self.runner.run(state.repo_path, str(tests_path), str(coverage_path))
        state.run_results.append(result)
        state.coverage_report_path = str(coverage_path)
        state.coverage_summary = load_coverage_summary(str(coverage_path))
        return state
