def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right


class Counter:
    """Small mutable counter used by the sample project."""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def increment(self) -> int:
        self.value += 1
        return self.value

