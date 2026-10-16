"""随机源 + 手写 Fisher-Yates Shuffle。

依据 ``AGENTS.md`` §2.1 算法核心禁表以及 # 二十六/# 二十七：

* **不** 使用 ``random.shuffle`` —— 手写 Fisher-Yates；
* **不** 使用全局 ``random`` 状态——所有随机由 :class:`RandomSource` 实例
  持有，外部调用方注入 seed；
* ``RandomSource(seed=42)`` 调用两次会得到完全一致的输出。

Fisher-Yates 伪代码：

::

    for i from n-1 down to 1:
        j = randint(0, i)         # inclusive
        swap(items[i], items[j])
"""
from __future__ import annotations

import random as _stdlib_random
from typing import Any, Iterable, Sequence, TypeVar

T = TypeVar("T")


class RandomSource:
    """封装随机性 —— 任何场景生成的随机动作都从这一处出。

    内部用 stdlib :class:`random.Random`，因为我们只需要"已 seed 的伪随机"，
    这不属于 §2.1 算法核心禁表（禁的是 **算法**；这里是基础设施）。
    """

    __slots__ = ("_rng",)

    def __init__(self, seed: int | None = None) -> None:
        # None 表示不可复现；显式整数 seed 完全可复现
        self._rng = _stdlib_random.Random(seed)

    # ------------------------------------------------------------------ #
    # 基础随机原语
    # ------------------------------------------------------------------ #

    def randint(self, lo: int, hi: int) -> int:
        """闭区间 ``[lo, hi]`` 上的均匀整数。"""
        if hi < lo:
            raise ValueError(f"randint: hi={hi} < lo={lo}")
        return self._rng.randint(lo, hi)

    def uniform(self, lo: float, hi: float) -> float:
        if hi < lo:
            raise ValueError(f"uniform: hi={hi} < lo={lo}")
        return self._rng.uniform(lo, hi)

    def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("choice: empty sequence")
        return self._rng.choice(seq)

    def sample_without_replacement(
        self, population: Sequence[T], k: int
    ) -> list[T]:
        if k < 0:
            raise ValueError(f"sample_without_replacement: k={k}")
        if k > len(population):
            raise ValueError(
                f"sample_without_replacement: k={k} > len(population)={len(population)}"
            )
        return self._rng.sample(population, k)

    # ------------------------------------------------------------------ #
    # 算法核心 —— 手写 Fisher-Yates Shuffle
    # ------------------------------------------------------------------ #

    def shuffle(self, items: list[T]) -> list[T]:
        """原地 + 返回 Fisher-Yates Shuffle。

        与 ``random.shuffle`` 等价但**完全手写**：从尾到头遍历，每次
        与 ``[0, i]`` 的随机位置交换；时间 O(n)，空间 O(1)。
        """
        n = len(items)
        for i in range(n - 1, 0, -1):
            j = self.randint(0, i)
            items[i], items[j] = items[j], items[i]
        return items

    def shuffled(self, items: Iterable[T]) -> list[T]:
        """非原地版本：返回新列表。"""
        return self.shuffle(list(items))

    # ------------------------------------------------------------------ #
    # 复现性 / 调试
    # ------------------------------------------------------------------ #

    @property
    def seed_value(self) -> int | None:
        try:
            return self._rng.random.__self__._seed  # type: ignore[attr-defined]
        except AttributeError:
            return None


__all__ = ["RandomSource"]
