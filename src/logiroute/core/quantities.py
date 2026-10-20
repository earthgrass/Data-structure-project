"""Exact scalar weight arithmetic; no floating-point intermediate totals."""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, localcontext

Quantity = int | float | Decimal


def decimal_quantity(value: Quantity, name: str = "quantity") -> Decimal:
    """Validate a single original scalar and convert it. Time/Space O(digits)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a finite non-negative numeric quantity")
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def exact_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum aligned decimal scalars without ambient precision truncation.

    Supports internal signed subtraction as well. Time O(K*D); Space O(K+D),
    where D is the aligned decimal precision; no binary float is introduced.
    """
    items = list(values)
    if not items:
        return Decimal(0)
    exponent = min(value.as_tuple().exponent for value in items)
    adjusted = max(value.adjusted() for value in items)
    precision = max(1, adjusted - exponent + len(str(len(items))) + 2)
    with localcontext() as context:
        context.prec = precision
        context.Emax = max(context.Emax, adjusted + len(str(len(items))) + 2)
        context.Emin = min(context.Emin, exponent)
        result = Decimal(0)
        for value in items:
            result += value
    return result


def exact_difference(left: Decimal, right: Decimal) -> Decimal:
    """Exact scalar subtraction. Time/Space O(aligned digits)."""
    return exact_sum((left, right.copy_negate()))
