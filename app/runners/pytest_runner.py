from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from app.core.state import RunResult


class PytestRunner:
    """Run pytest against generated tests in a controlled subprocess."""

    def __init__(self, timeout_seconds: int = 120) -> None:
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        repo_path: str,
        tests_path: str,
        coverage_json_path: str | None = None,
    ) -> RunResult:
        repo = Path(repo_path).resolve()
        tests = Path(tests_path).resolve()
        command = [sys.executable, "-m", "pytest", str(tests), "-q"]
        if coverage_json_path:
            coverage_path = Path(coverage_json_path).resolve()
            coverage_path.parent.mkdir(parents=True, exist_ok=True)
            command.extend(
                [
                    "--cov=.",
                    "--cov-report=term-missing",
                    f"--cov-report=json:{coverage_path}",
                ]
            )
        env = os.environ.copy()
        python_path = [str(repo)]
        src = repo / "src"
        if src.exists():
            python_path.append(str(src))
        if env.get("PYTHONPATH"):
            python_path.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_path)

        start = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(repo),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
            return_code = process.returncode
        except asyncio.TimeoutError:
            return RunResult(
                command=command,
                return_code=124,
                stdout="",
                stderr=f"pytest timed out after {self.timeout_seconds} seconds",
                duration_seconds=time.perf_counter() - start,
                coverage_json_path=coverage_json_path,
            )
        except OSError as exc:
            return RunResult(
                command=command,
                return_code=126,
                stdout="",
                stderr=f"could not start pytest subprocess: {exc}",
                duration_seconds=time.perf_counter() - start,
                coverage_json_path=coverage_json_path,
            )

        return RunResult(
            command=command,
            return_code=return_code if return_code is not None else 1,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_seconds=time.perf_counter() - start,
            coverage_json_path=coverage_json_path,
        )


def load_coverage_summary(path: str) -> dict:
    coverage_path = Path(path)
    if not coverage_path.exists():
        return {}
    data = json.loads(coverage_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    return {
        "covered_lines": totals.get("covered_lines"),
        "num_statements": totals.get("num_statements"),
        "missing_lines": totals.get("missing_lines"),
        "percent_covered": totals.get("percent_covered"),
        "percent_covered_display": totals.get("percent_covered_display"),
    }
