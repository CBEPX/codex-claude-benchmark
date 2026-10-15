import csv
import re
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, ROUND_HALF_UP, Context, Decimal
from io import StringIO

COLUMNS = frozenset(('id', 'currency', 'kind', 'amount'))
CURRENCIES = frozenset(('RUB', 'USD', 'EUR'))
KINDS = frozenset(('payment', 'refund'))
AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')
# Exact arithmetic: no precision loss for very long amounts or large totals.
CONTEXT = Context(prec=MAX_PREC, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN)


def _is_blank(row):
    return all(not field.strip() for field in row) and len(row) <= 1


def _parse_amount(raw):
    if not AMOUNT_RE.fullmatch(raw):
        raise ValueError(f'invalid amount: {raw!r}')
    return CONTEXT.quantize(Decimal(raw), CENT)


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
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise ValueError(f'row {line_no}: expected {len(header)} columns, got {len(row)}')
        values = {name: row[i].strip() for name, i in index.items()}

        row_id = values['id']
        currency = values['currency']
        kind = values['kind']
        if not row_id:
            raise ValueError(f'row {line_no}: empty id')
        if currency not in CURRENCIES:
            raise ValueError(f'row {line_no}: invalid currency {currency!r}')
        if kind not in KINDS:
            raise ValueError(f'row {line_no}: invalid kind {kind!r}')
        amount = _parse_amount(values['amount'])

        record = (currency, kind, amount)
        if row_id in seen:
            if seen[row_id] != record:
                raise ValueError(f'row {line_no}: conflicting duplicate id {row_id!r}')
            continue
        seen[row_id] = record

        signed = amount if kind == 'payment' else CONTEXT.minus(amount)
        totals[currency] = CONTEXT.add(totals.get(currency, Decimal('0.00')), signed)
    return totals
