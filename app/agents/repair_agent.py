from __future__ import annotations

import ast
import json

from app.agents.base_agent import BaseAgent
from app.agents.test_writer_utils import generated_tests_dir
from app.core.state import TestGenState
from app.llm.code_utils import extract_python_code, looks_like_pytest_file
from app.llm.json_utils import strip_json_fence
from app.llm.zai_client import ChatClient


class RepairAgent(BaseAgent):
    """Apply bounded, test-only repairs for common generated-test failures."""

    def __init__(self, llm_client: ChatClient) -> None:
        super().__init__()
        self.llm_client = llm_client

    async def execute(self, state: TestGenState) -> TestGenState:
        if not state.failure_reports:
            return state

        recoverable = [report for report in state.failure_reports if report.recoverable]
        if not recoverable:
            state.add_warning("Failure is marked unrecoverable; repair was skipped.")
            return state

        state.repair_round += 1
        changed = await self._repair_with_llm(state)
        if not changed:
            state.add_warning("LLM Repair Agent returned no test-file changes.")
        return state

    async def _repair_with_llm(self, state: TestGenState) -> bool:
        generated_dir = generated_tests_dir(state)
        files = {}
        for path in generated_dir.glob("test_*.py"):
            files[path.name] = path.read_text(encoding="utf-8")[:12000]
        if not files:
            return False

        reports = [
            {
                "category": report.category,
                "summary": report.summary,
                "evidence": report.evidence[:6000],
            }
            for report in state.failure_reports
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Python pytest 修复助手。只能修复生成的测试文件，不能改业务代码。"
                    "请只输出 JSON，不要 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是 pytest 失败归因和生成测试文件。请返回需要替换的测试文件内容。"
                    "JSON 格式必须是 {\"files\": {\"test_x.py\": \"完整 Python 内容\"}}。"
                    "不要新增非测试依赖，不要删除路径注入。\n\n"
                    f"repo_path={state.repo_path!r}\n"
                    f"failure_reports={json.dumps(reports, ensure_ascii=False)}\n"
                    f"files={json.dumps(files, ensure_ascii=False)}"
                ),
            },
        ]

        raw = await self.llm_client.complete(messages, temperature=0.1)
        payload = json.loads(strip_json_fence(raw))
        replacements = payload.get("files", {})
        if not isinstance(replacements, dict):
            raise ValueError("LLM repair response must contain a files object.")
        changed = False
        for name, content in replacements.items():
            if not isinstance(name, str) or not name.startswith("test_") or not name.endswith(".py"):
                continue
            if not isinstance(content, str):
                continue
            code = extract_python_code(content)
            if not looks_like_pytest_file(code):
                continue
            ast.parse(code)
            path = generated_dir / name
            path.write_text(code, encoding="utf-8")
            state.generated_files[str(path)] = code
            changed = True
        return changed
