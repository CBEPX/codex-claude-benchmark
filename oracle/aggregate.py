import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from io import StringIO
import re


def aggregate(text):
    if not text:
        return {}
    reader = csv.DictReader(StringIO(text), strict=True)
    seen, totals = {}, {}
    try:
        fields = reader.fieldnames
        if fields is None or len(fields) != 4 or set(fields) != {'id', 'currency', 'kind', 'amount'}:
            raise ValueError('invalid headers')
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('wrong column count')
            identifier, currency, kind, raw = (row[k].strip() for k in ('id', 'currency', 'kind', 'amount'))
            if not identifier or currency not in {'RUB', 'USD', 'EUR'} or kind not in {'payment', 'refund'}:
                raise ValueError('invalid identity, currency or kind')
            if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', raw) is None:
                raise ValueError('invalid amount')
            with localcontext() as context:
                context.prec = max(28, len(raw)+2, len(totals.get(currency, Decimal(0)).as_tuple().digits)+2)
                amount = Decimal(raw).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                record = (currency, kind, amount)
                if identifier in seen:
                    if seen[identifier] != record:
                        raise ValueError('conflicting ID')
                    continue
                seen[identifier] = record
                totals[currency] = totals.get(currency, Decimal('0.00')) + (amount if kind == 'payment' else -amount)
    except (csv.Error, InvalidOperation) as error:
        raise ValueError(str(error)) from error
    return totals
