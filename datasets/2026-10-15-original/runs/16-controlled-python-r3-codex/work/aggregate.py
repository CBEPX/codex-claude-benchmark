import csv
import re
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    header = None
    cent = Decimal("0.01")
    with localcontext(Context(rounding=ROUND_HALF_UP)) as context:
        try:
            for row in csv.reader(StringIO(text, newline=""), strict=True):
                if not row:
                    continue
                if header is None:
                    if len(row) != 4 or set(row) != {"id", "currency", "kind", "amount"}:
                        raise ValueError("Invalid CSV header")
                    header = row
                    continue
                if len(row) != 4:
                    raise ValueError("Invalid number of columns")
                values = dict(zip(header, (value.strip() for value in row)))
                identifier = values["id"]
                currency = values["currency"]
                kind = values["kind"]
                raw_amount = values["amount"]
                if (
                    not identifier
                    or currency not in {"RUB", "USD", "EUR"}
                    or kind not in {"payment", "refund"}
                    or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw_amount) is None
                ):
                    raise ValueError("Invalid CSV value")

                total = totals.get(currency, Decimal("0.00"))
                # Include room for cents and a carry when adding large amounts.
                context.prec = max(len(raw_amount), len(total.as_tuple().digits)) + 3
                amount = Decimal(raw_amount).quantize(cent, rounding=ROUND_HALF_UP)
                record = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != record:
                        raise ValueError("Conflicting duplicate ID")
                    continue
                seen[identifier] = record
                totals[currency] = total + amount if kind == "payment" else total - amount
        except csv.Error as exc:
            raise ValueError("Invalid CSV") from exc
    return totals
