import csv
from decimal import Decimal, ROUND_HALF_UP, localcontext
from io import StringIO
import re


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    try:
        rows = (row for row in csv.reader(StringIO(text, newline=''), strict=True) if row)
        header = next(rows, None)
        if header is None:
            return {}
        if len(header) != 4 or set(header) != {'id', 'currency', 'kind', 'amount'}:
            raise ValueError('Invalid CSV header')
        for row in rows:
            if len(row) != 4:
                raise ValueError('Invalid CSV column count')
            values = dict(zip(header, (value.strip() for value in row)))
            identifier, currency, kind, raw_amount = (
                values[name] for name in ('id', 'currency', 'kind', 'amount')
            )
            if (not identifier or currency not in {'RUB', 'USD', 'EUR'}
                    or kind not in {'payment', 'refund'}
                    or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', raw_amount) is None):
                raise ValueError('Invalid CSV value')
            total = totals.get(currency, Decimal('0.00'))
            with localcontext() as context:
                # Keep quantization and addition exact even beyond default precision.
                context.prec = max(len(raw_amount) + 2, len(total.as_tuple().digits) + 1)
                amount = Decimal(raw_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                entry = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != entry:
                        raise ValueError('Conflicting duplicate ID')
                    continue
                seen[identifier] = entry
                totals[currency] = total + amount if kind == 'payment' else total - amount
    except csv.Error as error:
        raise ValueError('Invalid CSV') from error
    return totals
