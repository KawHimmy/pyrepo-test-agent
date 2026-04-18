from __future__ import annotations

from app.agents.api_test_writer_agent import ApiTestWriterAgent
from app.agents.regression_case_agent import RegressionCaseAgent
from app.agents.repo_scanner_agent import RepoScannerAgent
from app.agents.spec_inference_agent import SpecInferenceAgent
from app.agents.test_planner_agent import TestPlannerAgent
from app.agents.unit_test_writer_agent import UnitTestWriterAgent
from app.core.parallel_executor import ParallelExecutor
from app.core.repair_loop import RepairLoop
from app.core.state import TestGenState
from app.llm.zai_client import ChatClient


class TestGenerationPipeline:
    """Pipeline、并行 Writer 分叉与执行修复循环的组合编排。"""

    __test__ = False

    def __init__(self, llm_client: ChatClient) -> None:
        self.llm_client = llm_client
        self.scanner = RepoScannerAgent()
        self.spec_inference = SpecInferenceAgent(llm_client=self.llm_client)
        self.planner = TestPlannerAgent(llm_client=self.llm_client)
        self.writer_executor = ParallelExecutor(
            [
                UnitTestWriterAgent(llm_client=self.llm_client),
                ApiTestWriterAgent(llm_client=self.llm_client),
                RegressionCaseAgent(llm_client=self.llm_client),
            ]
        )
        self.repair_loop = RepairLoop(llm_client=self.llm_client)

    async def run(self, state: TestGenState) -> TestGenState:
        state = await self.scanner.run(state)
        state = await self.spec_inference.run(state)
        state = await self.planner.run(state)
        state = await self.writer_executor.run(state)
        state = await self.repair_loop.run(state)
        return state
