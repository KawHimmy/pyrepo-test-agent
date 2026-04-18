from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.env_loader import load_dotenv
from app.core.pipeline import TestGenerationPipeline
from app.core.state import TestGenState
from app.llm.zai_client import build_chat_client
from app.reports.report_builder import ReportBuilder


def test_pipeline_generates_and_runs_tests_with_real_glm(tmp_path: Path) -> None:
    load_dotenv(Path.cwd() / ".env")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        '''
def add(left: int, right: int) -> int:
    """返回两个整数之和。"""
    return left + right
''',
        encoding="utf-8",
    )

    state = TestGenState(
        repo_path=str(repo),
        output_dir=str(tmp_path / "out"),
        max_repair_rounds=0,
    )

    client = build_chat_client(
        model="glm-4.7",
        max_concurrency=5,
        request_timeout_seconds=120,
        max_retries=3,
    )
    result = asyncio.run(TestGenerationPipeline(llm_client=client).run(state))
    report_path = ReportBuilder().write(result)

    assert result.repository_info is not None
    assert len(result.repository_info.target_symbols) == 1
    assert result.generated_unit_tests
    assert result.latest_run is not None
    assert result.latest_run.passed
    assert result.coverage_summary
    assert Path(report_path).exists()
