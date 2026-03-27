from decimal import Decimal, ROUND_DOWN


def calculate_points(pre_tax_amount: Decimal) -> int:
    if pre_tax_amount <= Decimal("0"):
        return 0
    return int(pre_tax_amount.quantize(Decimal("1"), rounding=ROUND_DOWN))
