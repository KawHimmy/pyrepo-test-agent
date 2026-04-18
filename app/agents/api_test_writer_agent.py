from __future__ import annotations

import ast
import json

from app.agents.base_agent import BaseAgent
from app.agents.test_writer_utils import header, write_generated_file
from app.core.state import ApiRouteInfo, TestGenState
from app.llm.code_utils import extract_python_code, looks_like_pytest_file
from app.llm.zai_client import ChatClient


class ApiTestWriterAgent(BaseAgent):
    """Generate tests that verify FastAPI-style route registration when possible."""

    def __init__(self, llm_client: ChatClient) -> None:
        super().__init__()
        self.llm_client = llm_client

    async def execute(self, state: TestGenState) -> TestGenState:
        repo = state.repository_info
        if repo is None:
            raise RuntimeError("repository_info is missing")

        planned_ids = {item.symbol_id for item in state.test_plan if item.test_type == "api"}
        route_by_function = {f"{route.file_path}::{route.function_name}": route for route in repo.api_routes}
        routes: list[ApiRouteInfo] = []
        for symbol in repo.target_symbols:
            key = f"{symbol.file_path}::{symbol.name}"
            if symbol.symbol_id in planned_ids and key in route_by_function:
                routes.append(route_by_function[key])

        content = await self._render_with_llm(state, routes)
        if content is None:
            content = self._render(str(repo.repo_path), routes)
        path = write_generated_file(state, "test_api_generated.py", content)
        state.generated_api_tests.append(path)
        return state

    async def _render_with_llm(self, state: TestGenState, routes: list[ApiRouteInfo]) -> str | None:
        repo = state.repository_info
        if repo is None or not routes:
            return None
        payload = [
            {
                "module": route.module_name,
                "function": route.function_name,
                "method": route.method,
                "path": route.path,
            }
            for route in routes
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深 FastAPI/Flask 测试工程师。请生成可运行 pytest 文件。"
                    "只输出 Python 代码，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "为下面 API 路由生成测试。要求：\n"
                    "1. 文件必须可直接由 pytest 执行。\n"
                    "2. 必须包含 repo/src 路径注入。\n"
                    "3. 如果无法构造 TestClient，应跳过而不是失败。\n"
                    "4. 至少验证路由函数可导入，并尽量验证路由注册。\n\n"
                    f"repo_path={repo.repo_path!r}\n"
                    f"routes={json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ]
        code = extract_python_code(await self.llm_client.complete(messages, temperature=0.2))
        _validate_generated_code(code)
        return code

    def _render(self, repo_path: str, routes: list[ApiRouteInfo]) -> str:
        rows = [(route.module_name, route.function_name, route.method, route.path) for route in routes]
        if not rows:
            return header(repo_path) + '''
def test_no_api_routes_discovered():
    pytest.skip("No FastAPI-style routes were discovered.")
'''
        return header(repo_path) + f'''
ROUTES = {rows!r}


def _find_fastapi_apps(module):
    apps = []
    for value in vars(module).values():
        routes = getattr(value, "routes", None)
        if value.__class__.__name__ == "FastAPI" and routes is not None:
            apps.append(value)
    return apps


@pytest.mark.parametrize("module_name,function_name,method,path", ROUTES)
def test_generated_api_route_is_registered(module_name, function_name, method, path):
    module = importlib.import_module(module_name)
    assert callable(getattr(module, function_name))

    apps = _find_fastapi_apps(module)
    if not apps:
        pytest.skip("Route function found, but no FastAPI app object is exposed in the module.")

    registered = []
    for app in apps:
        for route in app.routes:
            registered.append((getattr(route, "path", None), set(getattr(route, "methods", []) or [])))

    assert any(route_path == path and method in methods for route_path, methods in registered)
'''


def _validate_generated_code(code: str) -> None:
    if not looks_like_pytest_file(code):
        raise ValueError("model output does not look like a pytest file")
    ast.parse(code)
