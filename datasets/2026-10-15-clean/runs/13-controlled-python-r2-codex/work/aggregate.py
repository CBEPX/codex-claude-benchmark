import csv
import re
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    fields = {"id", "currency", "kind", "amount"}
    cent = Decimal("0.01")
    reader = csv.reader(StringIO(text, newline=""), strict=True)

    try:
        header = next((row for row in reader if row), None)
        if header is None:
            return {}
        if len(header) != 4 or set(header) != fields:
            raise ValueError("Expected exactly id,currency,kind,amount columns")

        # Keep rounding and arithmetic independent of the caller's context.
        with localcontext(Context(prec=28)) as context:
            for row in reader:
                if not row:
                    continue
                if len(row) != 4:
                    raise ValueError("Expected exactly four values per row")
                values = dict(zip(header, (value.strip() for value in row)))
                identifier = values["id"]
                currency = values["currency"]
                kind = values["kind"]
                raw_amount = values["amount"]
                if not identifier:
                    raise ValueError("ID must not be empty")
                if currency not in {"RUB", "USD", "EUR"}:
                    raise ValueError("Unsupported currency")
                if kind not in {"payment", "refund"}:
                    raise ValueError("Unsupported kind")
                if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw_amount) is None:
                    raise ValueError("Invalid amount")

                total = totals.get(currency, Decimal("0.00"))
                # Allow two fractional digits and a carry without losing digits
                # on amounts or totals larger than Decimal's default precision.
                context.prec = max(
                    context.prec, len(raw_amount) + 2,
                    len(total.as_tuple().digits) + 1,
                )
                amount = Decimal(raw_amount).quantize(cent, rounding=ROUND_HALF_UP)
                record = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != record:
                        raise ValueError("Conflicting duplicate ID")
                    continue
                seen[identifier] = record
                totals[currency] = total + amount if kind == "payment" else total - amount
    except csv.Error as error:
        raise ValueError("Invalid CSV") from error

    return totals
