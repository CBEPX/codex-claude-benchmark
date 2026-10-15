import csv
import re
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    cent = Decimal("0.01")
    try:
        rows = (row for row in csv.reader(StringIO(text, newline=""), strict=True) if row)
        header = next(rows, None)
        if header is None:
            return {}
        if len(header) != 4 or set(header) != {"id", "currency", "kind", "amount"}:
            raise ValueError("Invalid CSV header")

        # Use a private context so callers' Decimal settings cannot round totals.
        with localcontext(Context(rounding=ROUND_HALF_UP)) as context:
            for row in rows:
                if len(row) != 4:
                    raise ValueError("Invalid number of CSV columns")
                values = dict(zip(header, (value.strip() for value in row)))
                identifier = values["id"]
                currency = values["currency"]
                kind = values["kind"]
                amount_text = values["amount"]
                if (
                    not identifier
                    or currency not in {"RUB", "USD", "EUR"}
                    or kind not in {"payment", "refund"}
                    or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount_text) is None
                ):
                    raise ValueError("Invalid CSV value")

                # Allow arbitrary monetary precision, including a rounding carry.
                context.prec = max(28, len(amount_text) + 2)
                amount = Decimal(amount_text).quantize(cent, rounding=ROUND_HALF_UP)
                record = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != record:
                        raise ValueError("Conflicting duplicate ID")
                    continue
                seen[identifier] = record

                previous = totals.get(currency, Decimal("0.00"))
                context.prec = max(
                    28, len(previous.as_tuple().digits) + 1, len(amount.as_tuple().digits) + 1
                )
                totals[currency] = previous + amount if kind == "payment" else previous - amount
    except csv.Error as error:
        raise ValueError("Invalid CSV") from error
    return totals
