from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from app.core.state import ApiRouteInfo, SymbolInfo


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "output",
}


@dataclass(slots=True)
class ModuleAnalysis:
    file_path: str
    module_name: str
    imports: list[str] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    api_routes: list[ApiRouteInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def discover_python_files(repo_path: str) -> list[Path]:
    root = Path(repo_path).resolve()
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS or part.startswith(".agent") for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py") or "tests" in path.parts


def module_name_from_path(path: Path, repo_path: str) -> str | None:
    root = Path(repo_path).resolve()
    rel = path.resolve().relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return None
    if not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts)


def analyze_python_file(path: Path, repo_path: str) -> ModuleAnalysis:
    module_name = module_name_from_path(path, repo_path) or path.stem
    analysis = ModuleAnalysis(file_path=str(path), module_name=module_name)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        analysis.errors.append(f"{path}: syntax error at line {exc.lineno}: {exc.msg}")
        return analysis

    analysis.imports.extend(_collect_imports(tree))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            route = _route_from_function(node, path, module_name)
            symbol = _symbol_from_function(node, path, repo_path, module_name, route is not None)
            analysis.symbols.append(symbol)
            if route:
                analysis.api_routes.append(route)
        elif isinstance(node, ast.ClassDef):
            analysis.symbols.append(_symbol_from_class(node, path, repo_path, module_name))

    return analysis


def _collect_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return sorted(set(imports))


def _symbol_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: Path,
    repo_path: str,
    module_name: str,
    is_api_route: bool,
) -> SymbolInfo:
    qualified_name = node.name
    symbol_id = _symbol_id(path, repo_path, qualified_name)
    return SymbolInfo(
        symbol_id=symbol_id,
        name=node.name,
        qualified_name=qualified_name,
        kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
        file_path=str(path),
        module_name=module_name,
        lineno=node.lineno,
        signature=_format_signature(node),
        docstring=ast.get_docstring(node),
        parameters=_parameter_names(node.args),
        returns=ast.unparse(node.returns) if node.returns else None,
        decorators=[ast.unparse(decorator) for decorator in node.decorator_list],
        is_api_route=is_api_route,
    )


def _symbol_from_class(node: ast.ClassDef, path: Path, repo_path: str, module_name: str) -> SymbolInfo:
    methods = [
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_")
    ]
    qualified_name = node.name
    symbol_id = _symbol_id(path, repo_path, qualified_name)
    return SymbolInfo(
        symbol_id=symbol_id,
        name=node.name,
        qualified_name=qualified_name,
        kind="class",
        file_path=str(path),
        module_name=module_name,
        lineno=node.lineno,
        signature=f"class {node.name}",
        docstring=ast.get_docstring(node),
        parameters=methods,
        decorators=[ast.unparse(decorator) for decorator in node.decorator_list],
    )


def _route_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    path: Path,
    module_name: str,
) -> ApiRouteInfo | None:
    for decorator in node.decorator_list:
        method, route_path = _parse_route_decorator(decorator)
        if method and route_path:
            return ApiRouteInfo(
                route_id=f"{module_name}.{node.name}:{method}:{route_path}",
                file_path=str(path),
                module_name=module_name,
                function_name=node.name,
                method=method,
                path=route_path,
                lineno=node.lineno,
            )
    return None


def _parse_route_decorator(decorator: ast.AST) -> tuple[str | None, str | None]:
    if not isinstance(decorator, ast.Call):
        return None, None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None, None
    method = func.attr.lower()
    if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
        return None, None
    if not decorator.args:
        return method.upper(), None
    first_arg = decorator.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return method.upper(), first_arg.value
    return method.upper(), None


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [arg.arg for arg in node.args.posonlyargs + node.args.args]
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    args.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"


def _parameter_names(args: ast.arguments) -> list[str]:
    names = [arg.arg for arg in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        names.append(f"*{args.vararg.arg}")
    if args.kwarg:
        names.append(f"**{args.kwarg.arg}")
    return names


def _symbol_id(path: Path, repo_path: str, qualified_name: str) -> str:
    rel = path.resolve().relative_to(Path(repo_path).resolve()).as_posix()
    return f"{rel}::{qualified_name}"

