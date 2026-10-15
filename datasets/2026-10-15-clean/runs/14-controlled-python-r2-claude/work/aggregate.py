import csv
import re
from decimal import (
    MAX_EMAX,
    MAX_PREC,
    MIN_EMIN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    localcontext,
)
from io import StringIO

COLUMNS = frozenset(('id', 'currency', 'kind', 'amount'))
CURRENCIES = frozenset(('RUB', 'USD', 'EUR'))
KINDS = frozenset(('payment', 'refund'))
AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def _is_blank(row):
    return not row or (len(row) == 1 and not row[0].strip())


def aggregate(text: str) -> dict[str, Decimal]:
    if not isinstance(text, str):
        raise ValueError('text must be str')
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

    ctx = Context(prec=MAX_PREC, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN)
    totals = {}
    seen = {}
    with localcontext(ctx):
        for line_no, raw in enumerate(rows[1:], start=2):
            if len(raw) != len(header):
                raise ValueError(f'row {line_no}: expected {len(header)} columns, got {len(raw)}')
            row = {name: raw[i].strip() for name, i in index.items()}

            row_id = row['id']
            if not row_id:
                raise ValueError(f'row {line_no}: empty id')
            currency = row['currency']
            if currency not in CURRENCIES:
                raise ValueError(f'row {line_no}: invalid currency {currency!r}')
            kind = row['kind']
            if kind not in KINDS:
                raise ValueError(f'row {line_no}: invalid kind {kind!r}')
            amount_text = row['amount']
            if not AMOUNT_RE.fullmatch(amount_text):
                raise ValueError(f'row {line_no}: invalid amount {amount_text!r}')
            amount = Decimal(amount_text).quantize(CENT, rounding=ROUND_HALF_UP)

            key = (currency, kind, amount)
            if row_id in seen:
                if seen[row_id] != key:
                    raise ValueError(f'row {line_no}: conflicting duplicate id {row_id!r}')
                continue
            seen[row_id] = key

            delta = amount if kind == 'payment' else -amount
            totals[currency] = totals.get(currency, Decimal('0.00')) + delta

        return {currency: total.quantize(CENT) for currency, total in totals.items()}
