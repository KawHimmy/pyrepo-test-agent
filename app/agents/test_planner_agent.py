from __future__ import annotations

import json
from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.core.state import TestGenState, TestPlanItem
from app.llm.json_utils import strip_json_fence
from app.llm.zai_client import ChatClient


class TestPlannerAgent(BaseAgent):
    """将推断出的规格转换为带优先级的测试任务。"""

    def __init__(self, llm_client: ChatClient) -> None:
        super().__init__()
        self.llm_client = llm_client

    async def execute(self, state: TestGenState) -> TestGenState:
        repo = state.repository_info
        if repo is None:
            raise RuntimeError("repository_info is missing")

        if not repo.target_symbols:
            state.test_plan = []
            return state

        symbol_payload = []
        root = Path(repo.repo_path).resolve()
        for symbol in repo.target_symbols:
            spec = state.inferred_specs.get(symbol.symbol_id)
            rel_path = Path(symbol.file_path).resolve().relative_to(root).as_posix()
            symbol_payload.append(
                {
                    "symbol_id": symbol.symbol_id,
                    "module": symbol.module_name,
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "file": rel_path,
                    "is_api_route": symbol.is_api_route,
                    "spec": spec.behavior if spec else "",
                    "risk": spec.risk if spec else "medium",
                    "boundaries": spec.boundaries if spec else [],
                }
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Python 测试规划 Agent。请根据仓库结构和规格生成测试计划。"
                    "只输出 JSON，不要 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请输出 JSON：{\"plan\": [{\"symbol_id\": \"...\", "
                    "\"test_type\": \"unit|api|regression\", \"priority\": 1, "
                    "\"rationale\": \"...\"}]}。\n"
                    "要求：\n"
                    "1. 普通函数/类至少规划 unit 测试。\n"
                    "2. API 路由规划 api 测试。\n"
                    "3. changed_files 涉及的符号必须额外规划 regression 测试。\n"
                    "4. priority 只能是 1、2、3，数字越小优先级越高。\n\n"
                    f"changed_files={json.dumps(repo.changed_files, ensure_ascii=False)}\n"
                    f"symbols={json.dumps(symbol_payload, ensure_ascii=False)}"
                ),
            },
        ]
        payload = json.loads(strip_json_fence(await self.llm_client.complete(messages, temperature=0.1)))
        plan = _parse_plan(payload, {symbol.symbol_id for symbol in repo.target_symbols})
        state.test_plan = sorted(plan, key=lambda item: (item.priority, item.test_type, item.symbol_id))
        return state


def _parse_plan(payload: dict, valid_symbol_ids: set[str]) -> list[TestPlanItem]:
    raw_items = payload.get("plan")
    if not isinstance(raw_items, list):
        raise ValueError("LLM planner response must contain a plan list.")

    items: list[TestPlanItem] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        symbol_id = str(raw.get("symbol_id") or "")
        test_type = str(raw.get("test_type") or "")
        if symbol_id not in valid_symbol_ids:
            continue
        if test_type not in {"unit", "api", "regression"}:
            continue
        key = (symbol_id, test_type)
        if key in seen:
            continue
        seen.add(key)
        priority = int(raw.get("priority") or 2)
        priority = min(max(priority, 1), 3)
        items.append(
            TestPlanItem(
                plan_id=f"{test_type}:{symbol_id}",
                symbol_id=symbol_id,
                test_type=test_type,
                priority=priority,
                rationale=str(raw.get("rationale") or "Planned by GLM."),
            )
        )

    if not items:
        raise ValueError("LLM planner returned no usable test plan items.")
    return items
