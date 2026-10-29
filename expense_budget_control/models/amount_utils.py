# -*- coding: utf-8 -*-
"""Preserve imported expense amounts, without rounding at intermediate stages.

The budget projection has an explicit rounding precision for its annual
allocation. The actual expense and available balance never use that rounding.
"""
from decimal import Decimal


def exact_sum(values):
    """Use decimal addition rather than cumulative binary-float additions."""
    return float(sum((Decimal(str(value or 0.0)) for value in values), Decimal('0')))


def exact_difference(planned, actual):
    """Subtract using all significant decimals of the stored values."""
    return float(Decimal(str(planned or 0.0)) - Decimal(str(actual or 0.0)))


def exact_display(value, minimum_digits=2):
    """Do not cut real consumption/balance at the budget presentation precision.

    The selected precision is a MINIMUM for actuals, not a maximum. For
    example, at 2 decimals the value 12.3456 still displays 12.3456.
    """
    decimal_value = Decimal(str(value or 0.0))
    required = max(0, -decimal_value.normalize().as_tuple().exponent)
    digits = max(int(minimum_digits), required)
    return format(decimal_value, ',.%df' % digits)
