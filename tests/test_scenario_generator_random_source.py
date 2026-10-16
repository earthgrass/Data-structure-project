"""``tests/test_scenario_generator_random_source.py`` —— RandomSource + Fisher-Yates。"""
from __future__ import annotations

import random as _stdlib_random
import unittest

from logiroute.scenario_generator.random_source import RandomSource


class TestRandomSourceBasic(unittest.TestCase):
    def test_seed_reproducible(self):
        a = RandomSource(42)
        b = RandomSource(42)
        seq_a = [a.randint(0, 1000) for _ in range(50)]
        seq_b = [b.randint(0, 1000) for _ in range(50)]
        self.assertEqual(seq_a, seq_b)

    def test_different_seed_different_seq(self):
        a = RandomSource(1)
        b = RandomSource(2)
        seq_a = [a.randint(0, 1000) for _ in range(20)]
        seq_b = [b.randint(0, 1000) for _ in range(20)]
        self.assertNotEqual(seq_a, seq_b)

    def test_randint_inclusive(self):
        r = RandomSource(0)
        for _ in range(100):
            x = r.randint(0, 5)
            self.assertIn(x, (0, 1, 2, 3, 4, 5))

    def test_uniform_range(self):
        r = RandomSource(0)
        for _ in range(100):
            x = r.uniform(-1.0, 1.0)
            self.assertGreaterEqual(x, -1.0)
            self.assertLessEqual(x, 1.0)

    def test_choice_nonempty(self):
        r = RandomSource(0)
        self.assertEqual(r.choice([42]), 42)
        # raises on empty
        with self.assertRaises(ValueError):
            r.choice([])

    def test_sample_without_replacement(self):
        r = RandomSource(0)
        result = r.sample_without_replacement(range(10), 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(len(set(result)), 5)
        # rejects too-large k
        with self.assertRaises(ValueError):
            r.sample_without_replacement(range(3), 5)


class TestFisherYates(unittest.TestCase):
    """手写 Fisher-Yates 必须与 ``random.shuffle`` 等价（同 seed 输入）。"""

    def test_fisher_yates_in_place(self):
        r = RandomSource(7)
        items = list(range(20))
        result = r.shuffle(items)
        self.assertIs(result, items, "shuffle should mutate in place and return same list")
        self.assertEqual(sorted(result), list(range(20)), "shuffle is a permutation")

    def test_fisher_yates_reproducible(self):
        a = RandomSource(123)
        b = RandomSource(123)
        items_a = list(range(10))
        items_b = list(range(10))
        a.shuffle(items_a)
        b.shuffle(items_b)
        self.assertEqual(items_a, items_b)

    def test_fisher_yates_no_shuffle_call_in_module(self):
        """守护：``random.shuffle`` 调用绝不允许。

        仅 ban 顶层名为 ``random``（或别名 ``_stdlib_random``）的属性访问
        ``.shuffle`` 调用。``self.shuffle(...)`` 等我们手写的方法调用合法。
        """
        import ast
        import inspect
        import logiroute.scenario_generator.random_source as m
        src = inspect.getsource(m)
        tree = ast.parse(src)
        bad_aliases = {"random", "_stdlib_random"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr != "shuffle":
                    continue
                if isinstance(func.value, ast.Name) and func.value.id in bad_aliases:
                    self.fail(
                        f"forbidden {func.value.id}.shuffle(...) call at line {node.lineno}; "
                        "use the hand-written Fisher-Yates in RandomSource.shuffle"
                    )

    def test_fisher_yates_matches_stdlib_shuffle(self):
        """同 seed 下，``rng.shuffle`` 与 stdlib ``random.shuffle(seq,
        random.Random(seed)).shuffle(seq)`` 应得到相同结果。

        这等价于把我们的 Fisher-Yates 实现与参考实现做属性测试 —— 同 seed
        给出相同输出。
        """
        for seed in (1, 7, 42, 999):
            seq_ours = list(range(20))
            seq_ref = list(range(20))
            ours_rng = RandomSource(seed)
            ref_rng = _stdlib_random.Random(seed)
            ours_rng.shuffle(seq_ours)
            ref_rng.shuffle(seq_ref)
            self.assertEqual(
                seq_ours, seq_ref,
                msg=f"fisher-yates drift for seed={seed}: ours={seq_ours} ref={seq_ref}",
            )


class TestRandomSourceEmptyAndEdgeCases(unittest.TestCase):
    def test_shuffle_one_element(self):
        r = RandomSource(0)
        items = ["only"]
        r.shuffle(items)
        self.assertEqual(items, ["only"])

    def test_shuffle_empty(self):
        r = RandomSource(0)
        items = []
        r.shuffle(items)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
