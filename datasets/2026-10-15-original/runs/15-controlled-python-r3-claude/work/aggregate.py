import csv
import re
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, ROUND_HALF_UP, Context, Decimal, localcontext
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
                yield [value.strip() for value in row]
    except csv.Error as exc:
        raise ValueError(f'malformed CSV: {exc}') from exc


def aggregate(text: str) -> dict[str, Decimal]:
    if not isinstance(text, str):
        raise TypeError('text must be str')
    rows = _rows(text)
    header = next(rows, None)
    if header is None:
        return {}
    if len(header) != len(COLUMNS) or len(set(header)) != len(header) or set(header) != set(COLUMNS):
        raise ValueError(f'invalid header: {header!r}')
    index = {name: header.index(name) for name in COLUMNS}

    totals = {}
    seen = {}
    ctx = Context(prec=MAX_PREC, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN)
    with localcontext(ctx):
        for line, row in enumerate(rows, start=2):
            if len(row) != len(COLUMNS):
                raise ValueError(f'row {line}: expected {len(COLUMNS)} columns, got {len(row)}')
            id_, currency, kind, amount = (row[index[name]] for name in COLUMNS)
            if not id_:
                raise ValueError(f'row {line}: empty id')
            if currency not in CURRENCIES:
                raise ValueError(f'row {line}: invalid currency {currency!r}')
            if kind not in KINDS:
                raise ValueError(f'row {line}: invalid kind {kind!r}')
            if not AMOUNT_RE.fullmatch(amount):
                raise ValueError(f'row {line}: invalid amount {amount!r}')
            value = Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP)

            record = (currency, kind, value)
            if id_ in seen:
                if seen[id_] != record:
                    raise ValueError(f'row {line}: conflicting duplicate id {id_!r}')
                continue
            seen[id_] = record

            signed = value if kind == 'payment' else -value
            totals[currency] = totals.get(currency, Decimal('0.00')) + signed
        return {currency: total.quantize(CENT) for currency, total in totals.items()}
