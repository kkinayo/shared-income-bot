"""Pure money helpers: parsing user input and splitting a balance into buckets."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("10000000")


def parse_amount(text: str) -> Decimal | None:
    """Turn '1 500,50' / '1500.5' into Decimal('1500.50').

    Returns None when the text is not a positive amount with at most 2 decimals.
    """
    cleaned = text.replace(" ", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0 or value >= MAX_AMOUNT:
        return None
    if value != value.quantize(CENT):
        return None
    return value.quantize(CENT)


def parse_split(spec: str) -> list[tuple[str, int]]:
    """Parse 'Общий счёт:40,Накопления:40,Личное:20' into [(name, percent), ...]."""
    parts: list[tuple[str, int]] = []
    for chunk in spec.split(","):
        name, _, pct = chunk.rpartition(":")
        name = name.strip()
        if not name or not pct.strip().isdigit():
            raise ValueError(f"Bad split entry: {chunk!r}")
        parts.append((name, int(pct)))
    if not parts or sum(p for _, p in parts) != 100:
        raise ValueError("Split percentages must add up to 100")
    return parts


def split_amount(total: Decimal, parts: list[tuple[str, int]]) -> list[tuple[str, Decimal]]:
    """Split total by percentages, rounded to cents.

    Rounding leftovers go to the last bucket, so the parts always add up
    to the total exactly.
    """
    result: list[tuple[str, Decimal]] = []
    allocated = Decimal("0")
    for i, (name, pct) in enumerate(parts):
        if i == len(parts) - 1:
            share = total - allocated
        else:
            share = (total * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
            allocated += share
        result.append((name, share))
    return result
