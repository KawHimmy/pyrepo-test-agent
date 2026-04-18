from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.core.state import TestGenState


class BaseAgent(ABC):
    """Template-method base class shared by all agents."""

    name: str

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    async def run(self, state: TestGenState) -> TestGenState:
        start = time.perf_counter()
        self.log_start(state)
        try:
            state = await self.execute(state)
            self.log_success(state, time.perf_counter() - start)
        except Exception as exc:  # noqa: BLE001 - agent boundary catches all errors.
            message = f"{self.name}: {exc}"
            state.add_error(message)
            self.log_error(state, message)
        return state

    @abstractmethod
    async def execute(self, state: TestGenState) -> TestGenState:
        """Run agent-specific behavior."""

    def log_start(self, state: TestGenState) -> None:
        state.agent_events.append(f"{self.name}: start")

    def log_success(self, state: TestGenState, duration_seconds: float) -> None:
        state.agent_events.append(f"{self.name}: success ({duration_seconds:.2f}s)")

    def log_error(self, state: TestGenState, message: str) -> None:
        state.agent_events.append(f"{self.name}: error - {message}")

