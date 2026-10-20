"""Handwritten ordered priority array; logical front is the physical tail."""
from __future__ import annotations

from dataclasses import dataclass

from logiroute.core.enums import OrderPriority, OrderStatus
from logiroute.core.orders import Order


PRIORITY_RANK: dict[OrderPriority, int] = {
    OrderPriority.URGENT: 0, OrderPriority.NORMAL: 1,
}


class OrderQueueError(ValueError):
    """Empty queue, missing/duplicate IDs or a violated queue ownership contract."""


@dataclass(frozen=True)
class _Entry:
    key: tuple[int, float, str]
    order: Order


def _key(order: Order) -> tuple[int, float, str]:
    order.__post_init__()
    return PRIORITY_RANK[order.priority], order.time_window_end, order.id


class OrderPriorityQueue:
    """Snapshot keys; callers remove before modifying ID/priority/deadline.

    A stale or nonpending logical head raises without removal or implicit status
    changes. Explicit remove(original_id) still works for invalidated records.
    Other entries are not scanned for unauthorized external key changes.
    Space O(K); dictionary lookups are O(1) average.
    """

    __slots__ = ("_items", "_by_id")

    def __init__(self) -> None:
        self._items: list[_Entry] = []
        self._by_id: dict[str, _Entry] = {}

    def __len__(self) -> int:
        """Number of stored records, including invalidated ones. Time/Space O(1)."""
        return len(self._items)

    def is_empty(self) -> bool:
        """Time / Space O(1)."""
        return not self._items

    def enqueue(self, order: Order) -> None:
        """Handwritten insertion, worst Time O(K); additional Space O(1)."""
        if not isinstance(order, Order):
            raise OrderQueueError("enqueue requires an Order")
        key = _key(order)
        if order.id in self._by_id:
            raise OrderQueueError(f"duplicate order id: {order.id!r}")
        if order.status is not OrderStatus.PENDING:
            raise OrderQueueError("only pending orders can be enqueued")
        entry = _Entry(key, order)
        self._items.append(entry)
        index = len(self._items) - 1
        while index > 0 and self._items[index - 1].key < key:
            self._items[index] = self._items[index - 1]
            index -= 1
        self._items[index] = entry
        self._by_id[order.id] = entry

    def peek_next(self) -> Order:
        """Logical front; invalid head raises and remains stored. Time/Space O(1)."""
        if not self._items:
            raise OrderQueueError("peek from empty order queue")
        entry = self._items[-1]
        if entry.order.status is not OrderStatus.PENDING or _key(entry.order) != entry.key:
            raise OrderQueueError("invalid or mutated head; remove by original ID before updating")
        return entry.order

    def pop_next(self) -> Order:
        """Return next task without lifecycle changes. Time O(1) amortized; Space O(1)."""
        order = self.peek_next()
        self._items.pop()
        del self._by_id[order.id]
        return order

    def contains(self, order_id: str) -> bool:
        """Membership by recorded ID. Time O(1) average; Space O(1)."""
        return order_id in self._by_id

    def get(self, order_id: str) -> Order:
        """Inspect a stored order, including invalidated records; not a dispatch.

        Time O(1) average; Space O(1).
        """
        entry = self._by_id.get(order_id)
        if entry is None:
            raise OrderQueueError(f"unknown order id: {order_id!r}")
        return entry.order

    def remove(self, order_id: str) -> Order:
        """Remove by original ID, even after invalidation. Time O(K); Space O(1)."""
        entry = self._by_id.get(order_id)
        if entry is None:
            raise OrderQueueError(f"unknown order id: {order_id!r}")
        for index, candidate in enumerate(self._items):
            if candidate is entry:
                del self._items[index]
                del self._by_id[order_id]
                return entry.order
        raise OrderQueueError("internal ID index mismatch")
