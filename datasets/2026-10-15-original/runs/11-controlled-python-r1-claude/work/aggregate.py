import csv
import re
from decimal import Decimal, ROUND_HALF_UP, MAX_PREC, localcontext
from io import StringIO

COLUMNS = frozenset(('id', 'currency', 'kind', 'amount'))
CURRENCIES = frozenset(('RUB', 'USD', 'EUR'))
KINDS = frozenset(('payment', 'refund'))
AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def _is_blank(row):
    return all(not field.strip() for field in row) and len(row) <= 1


def aggregate(text):
    if not isinstance(text, str):
        raise TypeError('text must be str')
    try:
        rows = list(csv.reader(StringIO(text, newline=''), strict=True))
    except csv.Error as exc:
        raise ValueError(f'malformed CSV: {exc}') from exc

    rows = [row for row in rows if not _is_blank(row)]
    if not rows:
        return {}

    header = [name.strip() for name in rows[0]]
    if len(header) != len(COLUMNS) or set(header) != COLUMNS:
        raise ValueError(f'invalid header: {rows[0]!r}')
    index = {name: i for i, name in enumerate(header)}

    totals = {}
    seen = {}
    with localcontext() as ctx:
        ctx.prec = MAX_PREC
        for line_no, row in enumerate(rows[1:], start=2):
            if len(row) != len(header):
                raise ValueError(f'row {line_no}: expected {len(header)} columns, got {len(row)}')
            values = [field.strip() for field in row]
            row_id = values[index['id']]
            currency = values[index['currency']]
            kind = values[index['kind']]
            raw_amount = values[index['amount']]

            if not row_id:
                raise ValueError(f'row {line_no}: empty id')
            if currency not in CURRENCIES:
                raise ValueError(f'row {line_no}: invalid currency {currency!r}')
            if kind not in KINDS:
                raise ValueError(f'row {line_no}: invalid kind {kind!r}')
            if not AMOUNT_RE.fullmatch(raw_amount):
                raise ValueError(f'row {line_no}: invalid amount {raw_amount!r}')

            amount = Decimal(raw_amount).quantize(CENT, rounding=ROUND_HALF_UP)
            key = (currency, kind, amount)
            if row_id in seen:
                if seen[row_id] != key:
                    raise ValueError(f'row {line_no}: conflicting duplicate id {row_id!r}')
                continue
            seen[row_id] = key

            signed = amount if kind == 'payment' else -amount
            totals[currency] = totals.get(currency, Decimal('0.00')) + signed

        # Adding 0.00 normalizes a possible -0.00 to 0.00.
        return {currency: total.quantize(CENT) + Decimal('0.00') for currency, total in totals.items()}
