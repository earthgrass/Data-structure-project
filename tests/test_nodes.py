"""``Node`` 数据模型的单元测试。

全部使用 Python 标准库 ``unittest``，不依赖任何第三方库。
"""

from __future__ import annotations

import math
import unittest

from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node


class TestNodeCreation(unittest.TestCase):
    def test_basic_node_creation(self) -> None:
        node = Node(id="A", name="仓库A", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0)
        self.assertEqual(node.id, "A")
        self.assertEqual(node.name, "仓库A")
        self.assertIs(node.node_type, NodeType.WAREHOUSE)
        self.assertEqual(node.x, 0.0)
        self.assertEqual(node.y, 0.0)
        self.assertEqual(node.metadata, {})

    def test_metadata_default_is_per_instance(self) -> None:
        n1 = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0, y=0)
        n1.metadata["k"] = 1
        n2 = Node(id="B", name="b", node_type=NodeType.CUSTOMER, x=0, y=0)
        self.assertEqual(n2.metadata, {})

    def test_node_is_frozen(self) -> None:
        node = Node(id="A", name="n", node_type=NodeType.WAREHOUSE, x=0, y=0)
        with self.assertRaises(Exception):
            node.id = "B"  # type: ignore[misc]


class TestNodeValidation(unittest.TestCase):
    def test_blank_id_rejected(self) -> None:
        for bad in ("", "   ", "\t"):
            with self.subTest(bad_id=bad):
                with self.assertRaises(ValueError):
                    Node(id=bad, name="n", node_type=NodeType.CUSTOMER, x=0, y=0)

    def test_non_string_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id=123, name="n", node_type=NodeType.CUSTOMER, x=0, y=0)  # type: ignore[arg-type]

    def test_blank_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id="A", name="", node_type=NodeType.CUSTOMER, x=0, y=0)

    def test_non_enum_node_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id="A", name="n", node_type="warehouse", x=0, y=0)  # type: ignore[arg-type]

    def test_nan_x_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id="A", name="n", node_type=NodeType.CUSTOMER, x=math.nan, y=0)

    def test_inf_y_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id="A", name="n", node_type=NodeType.CUSTOMER, x=0, y=math.inf)

    def test_non_numeric_coordinate_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Node(id="A", name="n", node_type=NodeType.CUSTOMER, x="0", y=0)  # type: ignore[arg-type]


class TestNodeDistance(unittest.TestCase):
    def test_euclidean_distance(self) -> None:
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0)
        b = Node(id="B", name="b", node_type=NodeType.CUSTOMER, x=3.0, y=4.0)
        self.assertAlmostEqual(a.distance_to(b), 5.0)
        self.assertAlmostEqual(b.distance_to(a), 5.0)

    def test_distance_to_self(self) -> None:
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=1.5, y=2.5)
        self.assertAlmostEqual(a.distance_to(a), 0.0)

    def test_distance_to_invalid_type(self) -> None:
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0, y=0)
        with self.assertRaises(TypeError):
            a.distance_to("not a node")  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
