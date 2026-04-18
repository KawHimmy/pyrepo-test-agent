from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.core.env_loader import load_dotenv
from app.core.pipeline import TestGenerationPipeline
from app.core.state import TestGenState
from app.llm.zai_client import build_chat_client
from app.reports.report_builder import ReportBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pyrepo-test-agent",
        description="Generate conservative pytest coverage for a Python repository.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the Python repository to scan.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Directory for generated tests and report. Defaults to <repo>/.agent_test_output.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path for regression-focused test planning. Can be passed multiple times.",
    )
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=2,
        help="Maximum number of generated-test repair rounds.",
    )
    parser.add_argument(
        "--llm-model",
        default="glm-4.7",
        help="ZAI/GLM model name. Use glm-4.7 or glm-5 depending on your account.",
    )
    parser.add_argument(
        "--llm-concurrency",
        type=int,
        default=5,
        help="Maximum concurrent GLM API calls. Both glm-4.7 and glm-5 default to 5.",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each GLM API call.",
    )
    parser.add_argument(
        "--llm-retries",
        type=int,
        default=3,
        help="Retry count for transient GLM errors such as rate limits.",
    )
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve() if args.output else repo / ".agent_test_output"
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(repo / ".env")

    state = TestGenState(
        repo_path=str(repo),
        output_dir=str(output),
        max_repair_rounds=max(0, args.max_repair_rounds),
        changed_files=args.changed_file,
    )
    llm_client = build_chat_client(
        model=args.llm_model,
        max_concurrency=args.llm_concurrency,
        request_timeout_seconds=args.llm_timeout,
        max_retries=args.llm_retries,
    )

    pipeline = TestGenerationPipeline(llm_client=llm_client)
    state = await pipeline.run(state)
    report_path = ReportBuilder().write(state)

    latest = state.latest_run
    status = "passed" if latest and latest.passed else "failed"
    print(f"Generated tests: {output / 'generated_tests'}")
    print(f"Report: {report_path}")
    print(f"Pytest status: {status}")
    if state.error_messages:
        print("Agent errors:")
        for message in state.error_messages:
            print(f"- {message}")
    return 0 if latest and latest.passed else 1


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
