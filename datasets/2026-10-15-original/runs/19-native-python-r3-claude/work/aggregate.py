import csv
import decimal
import re
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

COLUMNS = {'id', 'currency', 'kind', 'amount'}
CURRENCIES = {'RUB', 'USD', 'EUR'}
KINDS = {'payment', 'refund'}
AMOUNT = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')
# Exact arithmetic for any amount length: quantize/add never round or overflow.
EXACT = decimal.Context(prec=decimal.MAX_PREC, Emax=decimal.MAX_EMAX, Emin=decimal.MIN_EMIN)


def aggregate(text: str) -> dict[str, Decimal]:
    try:
        rows = [[v.strip() for v in r] for r in csv.reader(StringIO(text, newline=''), strict=True)]
    except csv.Error as e:
        raise ValueError(f'malformed CSV: {e}') from e
    rows = [r for r in rows if r and r != ['']]
    if not rows:
        return {}
    header, *rows = rows
    if len(header) != 4 or set(header) != COLUMNS:
        raise ValueError(f'invalid header: {header!r}')
    col = {name: i for i, name in enumerate(header)}

    totals = {}
    seen = {}
    with decimal.localcontext(EXACT):
        for row in rows:
            if len(row) != 4:
                raise ValueError(f'expected 4 columns: {row!r}')
            id_, currency, kind, amount = (row[col[c]] for c in ('id', 'currency', 'kind', 'amount'))
            if not id_ or currency not in CURRENCIES or kind not in KINDS or not AMOUNT.fullmatch(amount):
                raise ValueError(f'invalid row: {row!r}')
            value = Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
            key = (currency, kind, value)
            if id_ in seen:
                if seen[id_] != key:
                    raise ValueError(f'conflicting duplicate id: {id_!r}')
                continue
            seen[id_] = key
            total = totals.get(currency, Decimal('0.00'))
            totals[currency] = total + value if kind == 'payment' else total - value
    return totals
