from __future__ import annotations

import ast
import json

from app.agents.base_agent import BaseAgent
from app.agents.test_writer_utils import compact_symbol_rows, header, write_generated_file
from app.core.state import TestGenState
from app.llm.code_utils import extract_python_code, looks_like_pytest_file
from app.llm.zai_client import ChatClient


class RegressionCaseAgent(BaseAgent):
    """为变更文件生成回归保护测试。"""

    def __init__(self, llm_client: ChatClient) -> None:
        super().__init__()
        self.llm_client = llm_client

    async def execute(self, state: TestGenState) -> TestGenState:
        repo = state.repository_info
        if repo is None:
            raise RuntimeError("repository_info is missing")

        planned_ids = {item.symbol_id for item in state.test_plan if item.test_type == "regression"}
        symbols = [symbol for symbol in repo.target_symbols if symbol.symbol_id in planned_ids]
        content = await self._render_with_llm(state, symbols)
        if content is None:
            content = self._render(str(repo.repo_path), compact_symbol_rows(symbols))
        path = write_generated_file(state, "test_regression_generated.py", content)
        state.generated_regression_tests.append(path)
        return state

    async def _render_with_llm(self, state: TestGenState, symbols) -> str | None:
        repo = state.repository_info
        if repo is None or not symbols:
            return None
        payload = []
        for symbol in symbols:
            spec = state.inferred_specs.get(symbol.symbol_id)
            payload.append(
                {
                    "module": symbol.module_name,
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "signature": symbol.signature,
                    "spec": spec.behavior if spec else "",
                    "changed_file": symbol.file_path,
                }
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深回归测试工程师。请生成可运行 pytest 文件。"
                    "只输出 Python 代码，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "为下面变更符号生成回归测试。要求：\n"
                    "1. 文件必须可直接由 pytest 执行。\n"
                    "2. 必须包含 repo/src 路径注入。\n"
                    "3. 不确定业务输出时不要编造断言，使用 import/callable/签名/路由注册等稳定断言。\n\n"
                    f"repo_path={repo.repo_path!r}\n"
                    f"symbols={json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ]
        code = extract_python_code(await self.llm_client.complete(messages, temperature=0.2))
        _validate_generated_code(code)
        return code

    def _render(self, repo_path: str, rows: list[tuple[str, str, str, str]]) -> str:
        if not rows:
            return header(repo_path) + '''
def test_no_regression_targets_discovered():
    pytest.skip("No changed-file regression targets were provided.")
'''
        return header(repo_path) + f'''
REGRESSION_SYMBOLS = {rows!r}


@pytest.mark.parametrize("module_name,symbol_name,kind,signature", REGRESSION_SYMBOLS)
def test_changed_symbol_still_imports(module_name, symbol_name, kind, signature):
    module = importlib.import_module(module_name)
    target = getattr(module, symbol_name)
    assert target is not None
    assert symbol_name in signature
'''


def _validate_generated_code(code: str) -> None:
    if not looks_like_pytest_file(code):
        raise ValueError("model output does not look like a pytest file")
    ast.parse(code)
