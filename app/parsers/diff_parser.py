from __future__ import annotations

from pathlib import Path


def normalize_changed_files(repo_path: str, changed_files: list[str] | None) -> list[str]:
    if not changed_files:
        return []
    root = Path(repo_path).resolve()
    normalized: list[str] = []
    for item in changed_files:
        path = Path(item)
        if not path.is_absolute():
            path = root / path
        try:
            normalized.append(str(path.resolve().relative_to(root)))
        except ValueError:
            normalized.append(str(path.resolve()))
    return sorted(set(normalized))

