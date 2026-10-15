import csv
import re
from decimal import MAX_EMAX, MAX_PREC, MIN_EMIN, ROUND_HALF_UP, Context, Decimal, localcontext
from io import StringIO

COLUMNS = frozenset(('id', 'currency', 'kind', 'amount'))
CURRENCIES = frozenset(('RUB', 'USD', 'EUR'))
KINDS = frozenset(('payment', 'refund'))
AMOUNT_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
CENT = Decimal('0.01')


def _is_blank(row):
    return not row or (len(row) == 1 and not row[0].strip())


def _rows(text):
    reader = csv.reader(StringIO(text, newline=''), strict=True)
    try:
        for row in reader:
            if not _is_blank(row):
                yield [value.strip() for value in row]
    except csv.Error as exc:
        raise ValueError(f'malformed CSV: {exc}') from exc


def aggregate(text):
    if not isinstance(text, str):
        raise TypeError('text must be str')
    if text.startswith('﻿'):
        text = text[1:]

    rows = _rows(text)
    header = next(rows, None)
    if header is None:
        return {}
    if len(header) != len(COLUMNS) or set(header) != COLUMNS:
        raise ValueError(f'invalid header: {header!r}')
    index = {name: i for i, name in enumerate(header)}

    totals = {}
    seen = {}
    # Exact arithmetic: no precision cap, so large amounts are never rounded silently.
    context = Context(prec=MAX_PREC, Emax=MAX_EMAX, Emin=MIN_EMIN, rounding=ROUND_HALF_UP)
    with localcontext(context):
        for line, row in enumerate(rows, start=2):
            if len(row) != len(COLUMNS):
                raise ValueError(f'row {line}: expected {len(COLUMNS)} columns, got {len(row)}')
            id_ = row[index['id']]
            currency = row[index['currency']]
            kind = row[index['kind']]
            raw_amount = row[index['amount']]

            if not id_:
                raise ValueError(f'row {line}: empty id')
            if currency not in CURRENCIES:
                raise ValueError(f'row {line}: invalid currency {currency!r}')
            if kind not in KINDS:
                raise ValueError(f'row {line}: invalid kind {kind!r}')
            if not AMOUNT_RE.fullmatch(raw_amount):
                raise ValueError(f'row {line}: invalid amount {raw_amount!r}')
            amount = Decimal(raw_amount).quantize(CENT, rounding=ROUND_HALF_UP)

            record = (currency, kind, amount)
            if id_ in seen:
                if seen[id_] != record:
                    raise ValueError(f'row {line}: conflicting duplicate id {id_!r}')
                continue
            seen[id_] = record

            total = totals.get(currency, Decimal('0.00'))
            totals[currency] = total + amount if kind == 'payment' else total - amount
    return totals
