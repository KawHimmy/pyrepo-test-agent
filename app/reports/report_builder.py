from __future__ import annotations

from pathlib import Path

from app.core.state import TestGenState


class ReportBuilder:
    """为生成测试的执行过程构建简洁的 Markdown 报告。"""

    def build(self, state: TestGenState) -> str:
        repo = state.repository_info
        latest = state.latest_run
        lines: list[str] = [
            "# pyrepo-test-agent 报告",
            "",
            "## 摘要",
            "",
            f"- 仓库路径: `{state.repo_path}`",
            f"- 生成文件数: {len(state.generated_files)}",
            f"- 修复轮次: {state.repair_round}/{state.max_repair_rounds}",
        ]

        if repo:
            lines.extend(
                [
                    f"- 扫描到的 Python 文件数: {len(repo.python_files)}",
                    f"- 已有测试文件数: {len(repo.test_files)}",
                    f"- 目标符号数: {len(repo.target_symbols)}",
                    f"- API 路由数: {len(repo.api_routes)}",
                    f"- 测试计划项数: {len(state.test_plan)}",
                ]
            )

        if latest:
            status = "通过" if latest.passed else "失败"
            lines.extend(
                [
                    f"- 最新 pytest 状态: **{status}**",
                    f"- 最新 pytest 返回码: `{latest.return_code}`",
                    f"- 最新 pytest 耗时: {latest.duration_seconds:.2f}s",
                ]
            )
        if state.coverage_summary:
            percent = state.coverage_summary.get("percent_covered_display")
            covered = state.coverage_summary.get("covered_lines")
            statements = state.coverage_summary.get("num_statements")
            lines.append(f"- 覆盖率: {percent}% ({covered}/{statements} 行)")
            if state.coverage_report_path:
                lines.append(f"- 覆盖率 JSON: `{state.coverage_report_path}`")

        lines.extend(["", "## 推断规格", ""])
        if state.inferred_specs:
            for spec in state.inferred_specs.values():
                lines.extend(
                    [
                        f"### {spec.title}",
                        "",
                        f"- 风险等级: `{spec.risk}`",
                        f"- 行为描述: {spec.behavior}",
                    ]
                )
                if spec.boundaries:
                    lines.append(f"- 边界条件: {', '.join(spec.boundaries)}")
                if spec.dependencies:
                    lines.append(f"- 依赖假设: {', '.join(spec.dependencies)}")
                lines.append("")
        else:
            lines.append("未推断出规格。")

        lines.extend(["", "## 测试计划", ""])
        if state.test_plan:
            lines.extend(["| 优先级 | 类型 | 符号 | 规划理由 |", "| --- | --- | --- | --- |"])
            for item in state.test_plan:
                lines.append(
                    f"| {item.priority} | `{item.test_type}` | `{item.symbol_id}` | {item.rationale} |"
                )
        else:
            lines.append("未生成测试计划项。")

        lines.extend(["", "## 生成的测试文件", ""])
        if state.generated_files:
            for path in sorted(state.generated_files):
                lines.append(f"- `{path}`")
        else:
            lines.append("- 未生成测试文件。")

        lines.extend(["", "## 失败归因", ""])
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
            lines.append("未报告失败。")

        lines.extend(["", "## 警告", ""])
        if state.warnings:
            for warning in state.warnings:
                lines.append(f"- {warning}")
        else:
            lines.append("- 无")

        lines.extend(["", "## Agent 事件", ""])
        for event in state.agent_events:
            lines.append(f"- {event}")

        lines.extend(["", "## 执行历史", ""])
        if state.run_results:
            lines.extend(["| 轮次 | 状态 | 返回码 | 耗时 | 命令 |", "| --- | --- | --- | --- | --- |"])
            for index, result in enumerate(state.run_results, start=1):
                status = "通过" if result.passed else "失败"
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
                    "## 最新 pytest 输出",
                    "",
                    "```text",
                    latest.stdout.strip() or "(无标准输出)",
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
