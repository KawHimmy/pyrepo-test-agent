def add(left: int, right: int) -> int:
    """返回两个整数之和。"""
    return left + right


class Counter:
    """示例项目使用的小型可变计数器。"""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def increment(self) -> int:
        self.value += 1
        return self.value
