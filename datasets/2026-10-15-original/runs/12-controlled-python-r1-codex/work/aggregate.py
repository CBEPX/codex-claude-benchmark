import csv
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from io import StringIO
import re


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    header = None
    cent = Decimal('0.01')
    zero = Decimal('0.00')
    try:
        for row in csv.reader(StringIO(text, newline=''), strict=True):
            if not row:
                continue
            if header is None:
                if len(row) != 4 or set(row) != {'id', 'currency', 'kind', 'amount'}:
                    raise ValueError('Invalid CSV header')
                header = row
                continue
            if len(row) != 4:
                raise ValueError('Invalid number of columns')
            values = dict(zip(header, (value.strip() for value in row)))
            identifier = values['id']
            currency = values['currency']
            kind = values['kind']
            raw_amount = values['amount']
            if not identifier:
                raise ValueError('Empty id')
            if currency not in {'RUB', 'USD', 'EUR'}:
                raise ValueError('Invalid currency')
            if kind not in {'payment', 'refund'}:
                raise ValueError('Invalid kind')
            if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', raw_amount) is None:
                raise ValueError('Invalid amount')

            previous = totals.get(currency, zero)
            # Allow both rounding carry and addition carry without losing digits,
            # independently of the caller's decimal context.
            precision = max(len(raw_amount), len(previous.as_tuple().digits)) + 3
            with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
                amount = Decimal(raw_amount).quantize(cent, rounding=ROUND_HALF_UP)
                transaction = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != transaction:
                        raise ValueError('Conflicting duplicate id')
                    continue
                seen[identifier] = transaction
                totals[currency] = (
                    previous + amount if kind == 'payment' else previous - amount
                )
    except csv.Error as exc:
        raise ValueError('Invalid CSV') from exc
    return totals
