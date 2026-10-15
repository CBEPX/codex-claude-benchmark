import csv
from decimal import Decimal, ROUND_HALF_UP, localcontext
from io import StringIO
import re


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    header = None
    cent = Decimal('0.01')
    try:
        for row in csv.reader(StringIO(text, newline=''), strict=True):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if header is None:
                if len(row) != 4 or set(row) != {'id', 'currency', 'kind', 'amount'}:
                    raise ValueError('Invalid CSV header')
                header = row
                continue
            if len(row) != 4:
                raise ValueError('Invalid column count')
            values = dict(zip(header, (value.strip() for value in row)))
            identifier = values['id']
            currency = values['currency']
            kind = values['kind']
            amount_text = values['amount']
            if (not identifier or currency not in {'RUB', 'USD', 'EUR'}
                    or kind not in {'payment', 'refund'}
                    or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', amount_text) is None):
                raise ValueError('Invalid CSV values')

            total = totals.get(currency, Decimal('0.00'))
            # Allow every input digit, cents and an addition carry, independently
            # of the caller's decimal precision. Do not change global settings.
            with localcontext() as context:
                context.prec = max(len(amount_text), len(total.as_tuple().digits)) + 3
                amount = Decimal(amount_text).quantize(cent, rounding=ROUND_HALF_UP)
                transaction = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != transaction:
                        raise ValueError('Conflicting duplicate ID')
                    continue
                seen[identifier] = transaction
                totals[currency] = total + amount if kind == 'payment' else total - amount
    except csv.Error as error:
        raise ValueError('Invalid CSV') from error
    return totals
