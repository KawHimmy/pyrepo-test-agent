from __future__ import annotations

from app.agents.failure_analyst_agent import FailureAnalystAgent
from app.agents.repair_agent import RepairAgent
from app.agents.sandbox_runner_agent import SandboxRunnerAgent
from app.core.state import TestGenState
from app.llm.zai_client import ChatClient


class RepairLoop:
    """Execute pytest, analyze failures, and apply bounded test repairs."""

    def __init__(
        self,
        llm_client: ChatClient,
        runner: SandboxRunnerAgent | None = None,
        analyst: FailureAnalystAgent | None = None,
        repairer: RepairAgent | None = None,
    ) -> None:
        self.runner = runner or SandboxRunnerAgent()
        self.analyst = analyst or FailureAnalystAgent()
        self.repairer = repairer or RepairAgent(llm_client=llm_client)

    async def run(self, state: TestGenState) -> TestGenState:
        while True:
            state = await self.runner.run(state)
            if state.all_tests_passed:
                return state

            state = await self.analyst.run(state)
            if not state.failure_reports:
                return state
            if all(not report.recoverable for report in state.failure_reports):
                return state
            if state.repair_round >= state.max_repair_rounds:
                state.add_warning("Reached max repair rounds; stopping repair loop.")
                return state

            before_round = state.repair_round
            state = await self.repairer.run(state)
            if state.repair_round == before_round:
                state.add_warning("Repair Agent made no change; stopping repair loop.")
                return state
