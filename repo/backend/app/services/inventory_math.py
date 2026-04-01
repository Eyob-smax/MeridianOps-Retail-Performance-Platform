from decimal import Decimal


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))
