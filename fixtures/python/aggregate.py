import csv
from io import StringIO

def aggregate(text):
    totals = {}
    for row in csv.DictReader(StringIO(text)):
        currency = row['currency']
        totals[currency] = totals.get(currency, 0.0) + float(row['amount'])
    return totals
