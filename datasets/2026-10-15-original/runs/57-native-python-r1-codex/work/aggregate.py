import csv
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from io import StringIO


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    rows = csv.reader(StringIO(text, newline=''), strict=True)
    try:
        header = next((row for row in rows if row), None)
        if header is None:
            return {}
        if len(header) != 4 or set(header) != {'id', 'currency', 'kind', 'amount'}:
            raise ValueError('Invalid CSV header')
        for row in rows:
            if not row:
                continue
            if len(row) != 4:
                raise ValueError('Invalid column count')
            values = dict(zip(header, (value.strip() for value in row)))
            identifier, currency, kind, raw_amount = (
                values[key] for key in ('id', 'currency', 'kind', 'amount')
            )
            if (not identifier or currency not in {'RUB', 'USD', 'EUR'}
                    or kind not in {'payment', 'refund'}
                    or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', raw_amount) is None):
                raise ValueError('Invalid CSV value')
            total = totals.get(currency, Decimal('0.00'))
            with localcontext() as context:
                context.prec = max(len(raw_amount), len(total.as_tuple().digits)) + 3
                amount = Decimal(raw_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                transaction = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != transaction:
                        raise ValueError('Conflicting ID')
                    continue
                seen[identifier] = transaction
                totals[currency] = total + amount if kind == 'payment' else total - amount
    except csv.Error as error:
        raise ValueError('Invalid CSV') from error
    return totals
