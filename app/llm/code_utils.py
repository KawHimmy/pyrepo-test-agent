from __future__ import annotations


def extract_python_code(text: str) -> str:
    """Extract Python from a fenced block, or return stripped text."""

    stripped = text.strip()
    if "```" not in stripped:
        return stripped

    parts = stripped.split("```")
    for index in range(1, len(parts), 2):
        block = parts[index].strip()
        if block.startswith("python"):
            return block.removeprefix("python").strip()
        if block.startswith("py"):
            return block.removeprefix("py").strip()
    return parts[1].strip()


def looks_like_pytest_file(code: str) -> bool:
    return "def test_" in code or "@pytest.mark.parametrize" in code

