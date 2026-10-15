import csv
import decimal
import re
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

COLUMNS = {'id', 'currency', 'kind', 'amount'}
CURRENCIES = {'RUB', 'USD', 'EUR'}
SIGNS = {'payment': 1, 'refund': -1}
AMOUNT = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def aggregate(text: str) -> dict[str, Decimal]:
    totals = {}
    seen = {}
    index = None
    try:
        with decimal.localcontext() as ctx:
            ctx.prec = decimal.MAX_PREC
            for row in csv.reader(StringIO(text, newline=''), strict=True):
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                cells = [c.strip() for c in row]
                if index is None:
                    if len(cells) != 4 or set(cells) != COLUMNS:
                        raise ValueError(f'bad header: {row!r}')
                    index = {name: i for i, name in enumerate(cells)}
                    continue
                if len(cells) != 4:
                    raise ValueError(f'bad column count: {row!r}')
                id_, currency, kind, amount = (cells[index[k]] for k in ('id', 'currency', 'kind', 'amount'))
                if not id_ or currency not in CURRENCIES or kind not in SIGNS or not AMOUNT.fullmatch(amount):
                    raise ValueError(f'bad row: {row!r}')
                value = Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
                key = (currency, kind, value)
                if id_ in seen:
                    if seen[id_] != key:
                        raise ValueError(f'conflicting duplicate id: {id_!r}')
                    continue
                seen[id_] = key
                totals[currency] = totals.get(currency, Decimal('0.00')) + SIGNS[kind] * value
    except csv.Error as e:
        raise ValueError(str(e)) from e
    return totals
