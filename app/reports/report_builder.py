from __future__ import annotations

from pathlib import Path

from app.core.state import TestGenState


class ReportBuilder:
    """Build a concise Markdown report for the generated test run."""

    def build(self, state: TestGenState) -> str:
        repo = state.repository_info
        latest = state.latest_run
        lines: list[str] = [
            "# pyrepo-test-agent report",
            "",
            "## Summary",
            "",
            f"- Repository: `{state.repo_path}`",
            f"- Generated files: {len(state.generated_files)}",
            f"- Repair rounds: {state.repair_round}/{state.max_repair_rounds}",
        ]

        if repo:
            lines.extend(
                [
                    f"- Python files scanned: {len(repo.python_files)}",
                    f"- Existing test files: {len(repo.test_files)}",
                    f"- Target symbols: {len(repo.target_symbols)}",
                    f"- API routes: {len(repo.api_routes)}",
                    f"- Planned test items: {len(state.test_plan)}",
                ]
            )

        if latest:
            status = "passed" if latest.passed else "failed"
            lines.extend(
                [
                    f"- Latest pytest status: **{status}**",
                    f"- Latest pytest return code: `{latest.return_code}`",
                    f"- Latest pytest duration: {latest.duration_seconds:.2f}s",
                ]
            )
        if state.coverage_summary:
            percent = state.coverage_summary.get("percent_covered_display")
            covered = state.coverage_summary.get("covered_lines")
            statements = state.coverage_summary.get("num_statements")
            lines.append(f"- Coverage: {percent}% ({covered}/{statements} lines)")
            if state.coverage_report_path:
                lines.append(f"- Coverage JSON: `{state.coverage_report_path}`")

        lines.extend(["", "## Inferred Specs", ""])
        if state.inferred_specs:
            for spec in state.inferred_specs.values():
                lines.extend(
                    [
                        f"### {spec.title}",
                        "",
                        f"- Risk: `{spec.risk}`",
                        f"- Behavior: {spec.behavior}",
                    ]
                )
                if spec.boundaries:
                    lines.append(f"- Boundaries: {', '.join(spec.boundaries)}")
                if spec.dependencies:
                    lines.append(f"- Dependencies: {', '.join(spec.dependencies)}")
                lines.append("")
        else:
            lines.append("No specs were inferred.")

        lines.extend(["", "## Test Plan", ""])
        if state.test_plan:
            lines.extend(["| Priority | Type | Symbol | Rationale |", "| --- | --- | --- | --- |"])
            for item in state.test_plan:
                lines.append(
                    f"| {item.priority} | `{item.test_type}` | `{item.symbol_id}` | {item.rationale} |"
                )
        else:
            lines.append("No test plan items were produced.")

        lines.extend(["", "## Generated Test Files", ""])
        if state.generated_files:
            for path in sorted(state.generated_files):
                lines.append(f"- `{path}`")
        else:
            lines.append("- No test files generated.")

        lines.extend(["", "## Failure Analysis", ""])
        if state.failure_reports:
            for report in state.failure_reports:
                lines.extend(
                    [
                        f"### {report.category}",
                        "",
                        report.summary,
                        "",
                        "```text",
                        report.evidence,
                        "```",
                        "",
                    ]
                )
        else:
            lines.append("No failures were reported.")

        lines.extend(["", "## Warnings", ""])
        if state.warnings:
            for warning in state.warnings:
                lines.append(f"- {warning}")
        else:
            lines.append("- None")

        lines.extend(["", "## Agent Events", ""])
        for event in state.agent_events:
            lines.append(f"- {event}")

        lines.extend(["", "## Run History", ""])
        if state.run_results:
            lines.extend(["| Round | Status | Return Code | Duration | Command |", "| --- | --- | --- | --- | --- |"])
            for index, result in enumerate(state.run_results, start=1):
                status = "passed" if result.passed else "failed"
                command = " ".join(result.command)
                lines.append(
                    f"| {index} | {status} | `{result.return_code}` | {result.duration_seconds:.2f}s | `{command}` |"
                )
        else:
            lines.append("No pytest run was recorded.")

        if latest:
            lines.extend(
                [
                    "",
                    "## Latest Pytest Output",
                    "",
                    "```text",
                    latest.stdout.strip() or "(no stdout)",
                    "```",
                ]
            )
            if latest.stderr.strip():
                lines.extend(["", "```text", latest.stderr.strip(), "```"])

        return "\n".join(lines).rstrip() + "\n"

    def write(self, state: TestGenState, filename: str = "report.md") -> str:
        output_dir = state.ensure_output_dir()
        path = output_dir / filename
        path.write_text(self.build(state), encoding="utf-8")
        state.final_report_path = str(path)
        return str(path)
