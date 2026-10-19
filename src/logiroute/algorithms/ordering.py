"""Deterministic string ordering for scenario generation, implemented by hand."""
from __future__ import annotations

from collections.abc import Iterable


def ordered_strings(values: Iterable[str]) -> list[str]:
    """Stable insertion sort. Time O(N²); Space O(N)."""
    result = list(values)
    for index in range(1, len(result)):
        value = result[index]
        previous = index - 1
        while previous >= 0 and result[previous] > value:
            result[previous + 1] = result[previous]
            previous -= 1
        result[previous + 1] = value
    return result
