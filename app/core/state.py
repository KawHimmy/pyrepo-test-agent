from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass(slots=True)
class SymbolInfo:
    """Static description of a Python symbol discovered in a repository."""

    symbol_id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str
    module_name: str
    lineno: int
    signature: str
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)
    returns: str | None = None
    decorators: list[str] = field(default_factory=list)
    is_api_route: bool = False


@dataclass(slots=True)
class ApiRouteInfo:
    route_id: str
    file_path: str
    module_name: str
    function_name: str
    method: str
    path: str
    lineno: int


@dataclass(slots=True)
class RepositoryInfo:
    repo_path: str
    python_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    module_graph: dict[str, list[str]] = field(default_factory=dict)
    target_symbols: list[SymbolInfo] = field(default_factory=list)
    api_routes: list[ApiRouteInfo] = field(default_factory=list)


@dataclass(slots=True)
class InferredSpec:
    symbol_id: str
    title: str
    behavior: str
    boundaries: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risk: str = "medium"


@dataclass(slots=True)
class TestPlanItem:
    plan_id: str
    symbol_id: str
    test_type: str
    priority: int
    rationale: str


@dataclass(slots=True)
class RunResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    coverage_json_path: str | None = None

    @property
    def passed(self) -> bool:
        return self.return_code == 0


@dataclass(slots=True)
class FailureReport:
    category: str
    summary: str
    evidence: str
    recoverable: bool = True


@dataclass(slots=True)
class TestGenState:
    __test__: ClassVar[bool] = False

    repo_path: str
    output_dir: str
    max_repair_rounds: int = 2
    changed_files: list[str] = field(default_factory=list)

    repository_info: RepositoryInfo | None = None
    inferred_specs: dict[str, InferredSpec] = field(default_factory=dict)
    test_plan: list[TestPlanItem] = field(default_factory=list)

    generated_unit_tests: list[str] = field(default_factory=list)
    generated_api_tests: list[str] = field(default_factory=list)
    generated_regression_tests: list[str] = field(default_factory=list)
    generated_files: dict[str, str] = field(default_factory=dict)

    run_results: list[RunResult] = field(default_factory=list)
    failure_reports: list[FailureReport] = field(default_factory=list)
    repair_round: int = 0

    coverage_summary: dict[str, Any] = field(default_factory=dict)
    coverage_report_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    agent_events: list[str] = field(default_factory=list)
    final_report_path: str | None = None

    @property
    def latest_run(self) -> RunResult | None:
        return self.run_results[-1] if self.run_results else None

    @property
    def all_tests_passed(self) -> bool:
        latest = self.latest_run
        return latest is not None and latest.passed

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.error_messages.append(message)

    def ensure_output_dir(self) -> Path:
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
