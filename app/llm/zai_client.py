from __future__ import annotations

import asyncio
import os
import random
from typing import Protocol


class ChatClient(Protocol):
    model: str

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        ...


class ZaiChatClient:
    """对同步 ZAI chat completions API 的异步封装。

    本项目将 GLM 账号按 5 个并发请求处理。所有 Agent 共享同一个客户端，
    因此信号量会保护整条 Pipeline，包括并行 Writer 阶段。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "glm-4.7",
        max_concurrency: int = 5,
        request_timeout_seconds: int = 120,
        max_retries: int = 3,
    ) -> None:
        try:
            from zai import ZhipuAiClient
        except ImportError as exc:  # pragma: no cover - 依赖本地环境。
            raise RuntimeError("Package 'zai' is not installed. Install with: python -m pip install zai") from exc

        self.model = model
        self._client = ZhipuAiClient(api_key=api_key)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._request_timeout_seconds = max(1, request_timeout_seconds)
        self._max_retries = max(0, max_retries)

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with self._semaphore:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self._client.chat.completions.create,
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                        ),
                        timeout=self._request_timeout_seconds,
                    )
                return response.choices[0].message.content
            except Exception as exc:  # noqa: BLE001 - SDK 异常类型会随版本变化。
                last_error = exc
                if attempt >= self._max_retries or not _is_retryable_error(exc):
                    raise
                await asyncio.sleep(min(60.0, (2**attempt) * 5.0 + random.random()))
        raise RuntimeError(f"GLM request failed: {last_error}")


def build_chat_client(
    *,
    api_key: str | None = None,
    model: str = "glm-4.7",
    max_concurrency: int = 5,
    request_timeout_seconds: int = 120,
    max_retries: int = 3,
) -> ChatClient:
    key = api_key or os.getenv("ZAI_API_KEY")
    if not key:
        raise RuntimeError("ZAI_API_KEY is not set. Put it in .env or the shell environment.")
    return ZaiChatClient(
        api_key=key,
        model=model,
        max_concurrency=max_concurrency,
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
    )


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ("429", "rate limit", "速率限制", "timeout", "timed out"))
