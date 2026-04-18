from __future__ import annotations

from app.parsers.ast_parser import ModuleAnalysis


def build_import_graph(analyses: list[ModuleAnalysis]) -> dict[str, list[str]]:
    known_modules = {analysis.module_name for analysis in analyses}
    graph: dict[str, list[str]] = {}
    for analysis in analyses:
        local_imports = []
        for imported in analysis.imports:
            if imported in known_modules or any(imported.startswith(f"{module}.") for module in known_modules):
                local_imports.append(imported)
        graph[analysis.module_name] = sorted(set(local_imports))
    return graph

