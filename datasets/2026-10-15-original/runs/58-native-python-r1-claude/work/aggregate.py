import csv
import re
from decimal import Decimal, ROUND_HALF_UP, MAX_EMAX, MIN_EMIN, localcontext
from io import StringIO

COLUMNS = {'id', 'currency', 'kind', 'amount'}
CURRENCIES = {'RUB', 'USD', 'EUR'}
SIGNS = {'payment': 1, 'refund': -1}
AMOUNT = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def aggregate(text: str) -> dict[str, Decimal]:
    try:
        rows = [r for r in csv.reader(StringIO(text, newline=''), strict=True)
                if r and not (len(r) == 1 and not r[0].strip())]
    except csv.Error as e:
        raise ValueError(f'bad CSV: {e}') from e
    if not rows:
        return {}
    header = [h.strip() for h in rows[0]]
    if len(header) != len(COLUMNS) or set(header) != COLUMNS:
        raise ValueError(f'bad header: {rows[0]!r}')
    totals, seen = {}, {}
    with localcontext() as ctx:
        # Enough digits for exact add/sub/quantize of any amount in this input.
        ctx.prec, ctx.Emax, ctx.Emin = len(text) + 32, MAX_EMAX, MIN_EMIN
        for row in rows[1:]:
            if len(row) != len(header):
                raise ValueError(f'bad column count: {row!r}')
            rec = dict(zip(header, (v.strip() for v in row)))
            id_, cur, kind, amount = rec['id'], rec['currency'], rec['kind'], rec['amount']
            if not id_ or cur not in CURRENCIES or kind not in SIGNS or not AMOUNT.fullmatch(amount):
                raise ValueError(f'bad row: {row!r}')
            q = Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)
            key = (cur, kind, q)
            if id_ in seen:
                if seen[id_] != key:
                    raise ValueError(f'conflicting duplicate id: {id_!r}')
                continue
            seen[id_] = key
            totals[cur] = totals.get(cur, Decimal('0.00')) + SIGNS[kind] * q
    return totals
