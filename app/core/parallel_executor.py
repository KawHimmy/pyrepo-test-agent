from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseAgent
from app.core.state import TestGenState


class ParallelExecutor:
    """并发运行彼此独立的 Agent，并保留部分执行结果。"""

    def __init__(self, agents: list[BaseAgent]) -> None:
        self.agents = agents

    async def run(self, state: TestGenState) -> TestGenState:
        results = await asyncio.gather(
            *(agent.run(state) for agent in self.agents),
            return_exceptions=True,
        )
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                state.add_error(f"{agent.name}: {result}")
        return state
