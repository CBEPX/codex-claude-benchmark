import unittest
from decimal import Decimal, Inexact, localcontext

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    def test_empty_and_blank_records(self):
        for text in ("", "\n\r\n", "id,currency,kind,amount", "\nid,currency,kind,amount\n\n"):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_reordered_columns_and_trimmed_values(self):
        self.assertEqual(
            aggregate('amount,kind,id,currency\n" 1.005 ", payment , a , USD \n'),
            {"USD": Decimal("1.01")},
        )

    def test_round_each_row_and_keep_zero(self):
        result = aggregate(
            "id,currency,kind,amount\n"
            "a,RUB,payment,0.005\n\n"
            "b,RUB,payment,0.005\n"
            "c,USD,refund,1.005\n"
            "d,EUR,payment,0\n"
            "e,EUR,refund,0.004\n"
        )
        self.assertEqual(result, {"RUB": Decimal("0.02"), "USD": Decimal("-1.01"), "EUR": Decimal("0.00")})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicate_uses_quantized_amount(self):
        self.assertEqual(
            aggregate("id,currency,kind,amount\na,USD,payment,1.004\na,USD,payment,1.00\n"),
            {"USD": Decimal("1.00")},
        )

    def test_duplicate_conflicts(self):
        for row in ("a,EUR,payment,1", "a,USD,refund,1", "a,USD,payment,1.005"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate("id,currency,kind,amount\na,USD,payment,1\n" + row)

    def test_invalid_headers(self):
        for header in ("id,currency,kind", "id,currency,kind,amount,extra", "id,currency,id,amount", "id,currency,kind,other"):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header)

    def test_invalid_rows(self):
        for row in (",USD,payment,1", "a,GBP,payment,1", "a,usd,payment,1", "a,USD,other,1", "a,USD,payment", "a,USD,payment,1,extra", ",,,", '"unterminated'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate("id,currency,kind,amount\n" + row)

    def test_invalid_amounts(self):
        for amount in ("", "-1", "+1", "1e2", "NaN", "Infinity", ".1", "1.", "1_000", "١", "1 2"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                aggregate("id,currency,kind,amount\na,USD,payment," + amount)

    def test_large_amounts_and_context_independence(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            result = aggregate(
                "id,currency,kind,amount\n"
                "a,USD,payment,9999999999999999999999999999999999999999.995\n"
                "b,USD,payment,0.01\n"
                "c,USD,refund,10000000000000000000000000000000000000000\n"
            )
            self.assertEqual(result, {"USD": Decimal("0.01")})
            self.assertEqual(context.prec, 2)
            self.assertTrue(context.traps[Inexact])
