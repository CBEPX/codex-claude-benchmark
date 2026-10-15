import csv
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    try:
        rows = (row for row in csv.reader(StringIO(text, newline=""), strict=True) if row)
        header = next(rows, None)
        if header is None:
            return {}
        if len(header) != 4 or set(header) != {"id", "currency", "kind", "amount"}:
            raise ValueError("Invalid CSV header")
        with localcontext() as context:
            for row in rows:
                if len(row) != 4:
                    raise ValueError("Invalid number of columns")
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
                    raise ValueError("Invalid CSV row")
                total = totals.get(currency, Decimal("0.00"))
                context.prec = max(len(amount_text) + 3, len(total.as_tuple().digits) + 1)
                amount = Decimal(amount_text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                signature = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != signature:
                        raise ValueError("Conflicting duplicate ID")
                    continue
                seen[identifier] = signature
                totals[currency] = total + amount if kind == "payment" else total - amount
    except csv.Error as exc:
        raise ValueError("Invalid CSV") from exc
    return totals
