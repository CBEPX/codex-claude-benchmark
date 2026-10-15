import csv
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from io import StringIO

COLUMNS = ('id', 'currency', 'kind', 'amount')
CURRENCIES = frozenset({'RUB', 'USD', 'EUR'})
KINDS = frozenset({'payment', 'refund'})
AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def _is_blank(row):
    return not row or (len(row) == 1 and not row[0].strip())


def _rows(text):
    try:
        for row in csv.reader(StringIO(text, newline=''), strict=True):
            if not _is_blank(row):
                yield row
    except csv.Error as exc:
        raise ValueError(f'malformed CSV: {exc}') from exc


def aggregate(text: str) -> dict[str, Decimal]:
    if not isinstance(text, str):
        raise ValueError('text must be str')

    rows = _rows(text)
    header = next(rows, None)
    if header is None:
        return {}

    names = [name.strip() for name in header]
    if len(names) != len(COLUMNS) or len(set(names)) != len(names) or set(names) != set(COLUMNS):
        raise ValueError(f'invalid header: {header!r}')
    index = {name: i for i, name in enumerate(names)}

    totals = {}
    seen = {}
    with localcontext() as ctx:
        ctx.prec = 1000
        ctx.rounding = ROUND_HALF_UP
        for row in rows:
            if len(row) != len(COLUMNS):
                raise ValueError(f'invalid column count: {row!r}')
            values = {name: row[i].strip() for name, i in index.items()}
            row_id = values['id']
            currency = values['currency']
            kind = values['kind']
            raw_amount = values['amount']

            if not row_id:
                raise ValueError(f'empty id: {row!r}')
            if currency not in CURRENCIES:
                raise ValueError(f'invalid currency: {currency!r}')
            if kind not in KINDS:
                raise ValueError(f'invalid kind: {kind!r}')
            if not AMOUNT_RE.fullmatch(raw_amount):
                raise ValueError(f'invalid amount: {raw_amount!r}')

            try:
                amount = Decimal(raw_amount).quantize(CENT, rounding=ROUND_HALF_UP)
            except InvalidOperation as exc:
                raise ValueError(f'amount out of range: {raw_amount!r}') from exc
            key = (currency, kind, amount)
            if row_id in seen:
                if seen[row_id] != key:
                    raise ValueError(f'conflicting duplicate id: {row_id!r}')
                continue
            seen[row_id] = key

            total = totals.get(currency, Decimal('0.00'))
            totals[currency] = total + amount if kind == 'payment' else total - amount

    return totals
