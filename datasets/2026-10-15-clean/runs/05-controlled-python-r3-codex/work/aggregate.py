import csv
import re
from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    seen: dict[str, tuple[str, str, Decimal]] = {}
    fields = {"id", "currency", "kind", "amount"}
    cent = Decimal("0.01")
    zero = Decimal("0.00")
    # The input length bounds the digits needed for any amount or total.
    # A fresh context also isolates rounding from the caller's Decimal settings.
    context = Context(prec=max(28, len(text) + 2), Emax=MAX_EMAX, Emin=MIN_EMIN)
    try:
        with localcontext(context):
            reader = csv.reader(StringIO(text, newline=""), strict=True)
            header = next((row for row in reader if row), None)
            if header is None:
                return {}
            if len(header) != 4 or set(header) != fields:
                raise ValueError("Invalid CSV header")

            for row in reader:
                if not row:
                    continue
                if len(row) != 4:
                    raise ValueError("Expected four CSV columns")
                values = dict(zip(header, (value.strip() for value in row)))
                identifier = values["id"]
                currency = values["currency"]
                kind = values["kind"]
                amount_text = values["amount"]
                if not identifier:
                    raise ValueError("ID must not be empty")
                if currency not in {"RUB", "USD", "EUR"}:
                    raise ValueError("Invalid currency")
                if kind not in {"payment", "refund"}:
                    raise ValueError("Invalid kind")
                if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount_text) is None:
                    raise ValueError("Invalid amount")
                amount = Decimal(amount_text).quantize(cent, rounding=ROUND_HALF_UP)
                record = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != record:
                        raise ValueError("Conflicting duplicate ID")
                    continue
                seen[identifier] = record
                total = totals.get(currency, zero)
                totals[currency] = total + amount if kind == "payment" else total - amount
    except csv.Error as error:
        raise ValueError("Invalid CSV") from error
    return totals
