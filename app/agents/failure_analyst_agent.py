from __future__ import annotations

import re

from app.agents.base_agent import BaseAgent
from app.core.state import FailureReport, TestGenState


class FailureAnalystAgent(BaseAgent):
    """在修复步骤前对 pytest 失败进行归因分类。"""

    async def execute(self, state: TestGenState) -> TestGenState:
        latest = state.latest_run
        if latest is None:
            raise RuntimeError("run_results is empty")
        if latest.passed:
            state.failure_reports = []
            return state

        output = f"{latest.stdout}\n{latest.stderr}"
        state.failure_reports = [self._classify(output)]
        return state

    def _classify(self, output: str) -> FailureReport:
        excerpt = _excerpt(output)
        lowered = output.lower()

        if "no module named pytest" in lowered:
            return FailureReport("EnvError", "pytest is not installed in this environment.", excerpt, recoverable=False)
        if "permissionerror" in lowered or "access is denied" in lowered or "拒绝访问" in output:
            return FailureReport("EnvError", "The environment blocked pytest subprocess execution.", excerpt, recoverable=False)
        if "timed out" in lowered:
            return FailureReport("EnvError", "The generated test run timed out.", excerpt, recoverable=False)
        if "modulenotfounderror" in lowered or "importerror" in lowered:
            return FailureReport("ImportError", "A module import failed while running generated tests.", excerpt)
        if "fixture" in lowered and "not found" in lowered:
            return FailureReport("FixtureError", "A pytest fixture referenced by a test was not found.", excerpt)
        if "assertionerror" in lowered or re.search(r"^E\s+assert", output, re.MULTILINE):
            return FailureReport("AssertionError", "A generated assertion did not match runtime behavior.", excerpt)
        return FailureReport("LogicMismatch", "The test outcome does not match the inferred behavior.", excerpt)


def _excerpt(output: str, max_lines: int = 40) -> str:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])
