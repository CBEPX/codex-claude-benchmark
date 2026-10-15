import unittest
from decimal import Decimal, Inexact, localcontext

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    header = "id,currency,kind,amount\n"

    def test_empty_and_blank_rows(self):
        for text in ("", "\n\r\n", self.header, "\n" + self.header + "\n"):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_order_whitespace_and_quoted_id(self):
        text = 'amount,kind,currency,id\n 1.005 , payment , EUR ," a,b "\n\n'
        self.assertEqual(aggregate(text), {"EUR": Decimal("1.01")})

    def test_round_each_row_and_preserve_zero(self):
        result = aggregate(self.header + "a,RUB,payment,0.005\n"
                           "b,RUB,payment,0.005\nc,USD,refund,0.004\n"
                           "d,EUR,payment,1.005\ne,EUR,refund,1.005\n")
        self.assertEqual(result, {"RUB": Decimal("0.02"),
                                  "USD": Decimal("0.00"),
                                  "EUR": Decimal("0.00")})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))
        self.assertTrue(all(value.as_tuple().exponent == -2 for value in result.values()))

    def test_duplicate_uses_rounded_amount(self):
        self.assertEqual(aggregate(self.header + "a,USD,payment,1.001\n"
                                   " a , USD , payment , 1.004 \n"),
                         {"USD": Decimal("1.00")})

    def test_conflicting_duplicates(self):
        for row in ("a,EUR,payment,1", "a,USD,refund,1", "a,USD,payment,1.005"):
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    aggregate(self.header + "a,USD,payment,1\n" + row)

    def test_invalid_headers(self):
        for header in ("id,currency,kind", "id,currency,kind,amount,extra",
                       "id,currency,amount,amount", "id,currency,kind,other",
                       "ID,currency,kind,amount"):
            with self.subTest(header=header):
                with self.assertRaises(ValueError):
                    aggregate(header + "\n")

    def test_invalid_rows(self):
        for row in ("a,USD,payment", "a,USD,payment,1,extra", ",USD,payment,1",
                    "  ,USD,payment,1", "a,usd,payment,1", "a,GBP,payment,1",
                    "a,USD,charge,1", ",,,", '"a,USD,payment,1',
                    '"a"x,USD,payment,1'):
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    aggregate(self.header + row)

    def test_invalid_amounts(self):
        for amount in ("", "-0", "+1", "1e2", "NaN", "Infinity", ".5", "1.",
                       "1_000", "1 0", "١", "1\n2"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    aggregate(self.header + 'a,USD,payment,"' + amount + '"\n')

    def test_large_amount_and_caller_context(self):
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            result = aggregate(self.header + "a,USD,payment,9999999999999999999999999999.995\n"
                               "b,USD,payment,0.01\n")
            self.assertEqual(result, {"USD": Decimal("10000000000000000000000000000.01")})
            self.assertEqual(context.prec, 3)
            self.assertTrue(context.traps[Inexact])
