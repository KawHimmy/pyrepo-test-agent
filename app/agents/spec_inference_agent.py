from __future__ import annotations

import json

from app.agents.base_agent import BaseAgent
from app.agents.source_context import symbol_source
from app.core.state import InferredSpec, TestGenState
from app.llm.json_utils import strip_json_fence
from app.llm.zai_client import ChatClient


class SpecInferenceAgent(BaseAgent):
    """基于静态符号元数据推断轻量行为规格。"""

    def __init__(self, llm_client: ChatClient) -> None:
        super().__init__()
        self.llm_client = llm_client

    async def execute(self, state: TestGenState) -> TestGenState:
        repo = state.repository_info
        if repo is None:
            raise RuntimeError("repository_info is missing")

        specs: dict[str, InferredSpec] = {}
        for symbol in repo.target_symbols:
            specs[symbol.symbol_id] = await self._infer_one(state, symbol)

        state.inferred_specs = specs
        return state

    async def _infer_one(self, state: TestGenState, symbol) -> InferredSpec:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 Python 测试架构师。请根据代码推断可测试行为，"
                    "只输出 JSON，不要输出 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请为下面 Python 符号推断测试规格。输出 JSON 格式："
                    '{"behavior": "...", "boundaries": ["..."], '
                    '"dependencies": ["..."], "risk": "low|medium|high"}\n\n'
                    f"模块: {symbol.module_name}\n"
                    f"符号: {symbol.qualified_name}\n"
                    f"类型: {symbol.kind}\n"
                    f"签名: {symbol.signature}\n"
                    f"源码:\n{symbol_source(symbol)}"
                ),
            },
        ]
        raw = await self.llm_client.complete(messages, temperature=0.1)
        data = json.loads(strip_json_fence(raw))
        return InferredSpec(
            symbol_id=symbol.symbol_id,
            title=symbol.qualified_name,
            behavior=str(data["behavior"]),
            boundaries=_string_list(data.get("boundaries")),
            dependencies=_string_list(data.get("dependencies")),
            risk=str(data.get("risk") or "medium"),
        )

def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
