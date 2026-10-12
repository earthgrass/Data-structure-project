"""``Node`` 数据模型的单元测试。"""

from __future__ import annotations

import math

import pytest

from logiroute.core.enums import NodeType
from logiroute.core.nodes import Node


pytestmark = pytest.mark.phase1


class TestNodeCreation:
    def test_basic_node_creation(self):
        node = Node(id="A", name="仓库A", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0)
        assert node.id == "A"
        assert node.name == "仓库A"
        assert node.node_type is NodeType.WAREHOUSE
        assert node.x == 0.0
        assert node.y == 0.0
        assert node.metadata == {}

    def test_metadata_default_is_per_instance(self):
        n1 = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0, y=0)
        n1.metadata["k"] = 1
        n2 = Node(id="B", name="b", node_type=NodeType.CUSTOMER, x=0, y=0)
        assert n2.metadata == {}

    def test_node_is_frozen(self):
        node = Node(id="A", name="n", node_type=NodeType.WAREHOUSE, x=0, y=0)
        with pytest.raises(Exception):
            node.id = "B"  # type: ignore[misc]


class TestNodeValidation:
    @pytest.mark.parametrize("bad_id", ["", "   ", "\t"])
    def test_empty_or_blank_id_rejected(self, bad_id):
        with pytest.raises(ValueError, match="non-empty"):
            Node(id=bad_id, name="n", node_type=NodeType.CUSTOMER, x=0, y=0)

    def test_non_string_id_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            Node(id=123, name="n", node_type=NodeType.CUSTOMER, x=0, y=0)  # type: ignore[arg-type]

    def test_blank_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            Node(id="A", name="", node_type=NodeType.CUSTOMER, x=0, y=0)

    def test_non_enum_node_type_rejected(self):
        with pytest.raises(ValueError, match="node_type"):
            Node(id="A", name="n", node_type="warehouse", x=0, y=0)  # type: ignore[arg-type]

    @pytest.mark.parametrize("axis", ["x", "y"])
    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
    def test_non_finite_coordinate_rejected(self, axis, value):
        with pytest.raises(ValueError, match=axis):
            Node(id="A", name="n", node_type=NodeType.CUSTOMER, x=value if axis == "x" else 0, y=value if axis == "y" else 0)

    def test_non_number_coordinate_rejected(self):
        with pytest.raises(ValueError):
            Node(id="A", name="n", node_type=NodeType.CUSTOMER, x="0", y=0)  # type: ignore[arg-type]


class TestNodeDistance:
    def test_euclidean_distance(self):
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0.0, y=0.0)
        b = Node(id="B", name="b", node_type=NodeType.CUSTOMER, x=3.0, y=4.0)
        assert a.distance_to(b) == pytest.approx(5.0)
        assert b.distance_to(a) == pytest.approx(5.0)

    def test_distance_to_self(self):
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=1.5, y=2.5)
        assert a.distance_to(a) == pytest.approx(0.0)

    def test_distance_to_invalid_type(self):
        a = Node(id="A", name="a", node_type=NodeType.WAREHOUSE, x=0, y=0)
        with pytest.raises(TypeError):
            a.distance_to("not a node")  # type: ignore[arg-type]
