import unittest
from decimal import Decimal, Inexact, localcontext

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    header = "id,currency,kind,amount\n"

    def test_empty_and_blank_rows(self):
        for text in ("", "\n\r\n", self.header, "\n" + self.header + "\n"):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_column_order_whitespace_and_rounding(self):
        text = (
            "amount,kind,currency,id\n"
            " 0.005 , payment , RUB , a \n"
            "0.005,payment,RUB,b\n"
            "\n"
            "0.004,refund,USD,c\n"
            "2.675,refund,EUR,d\n"
        )
        result = aggregate(text)
        self.assertEqual(result, {
            "RUB": Decimal("0.02"), "USD": Decimal("0.00"), "EUR": Decimal("-2.68")
        })
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicates_use_quantized_amount(self):
        self.assertEqual(
            aggregate(self.header + "a,RUB,payment,1.001\na,RUB,payment,1.004\n"),
            {"RUB": Decimal("1.00")},
        )

    def test_duplicate_conflicts(self):
        for row in ("a,USD,payment,1", "a,RUB,refund,1", "a,RUB,payment,1.005"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + "a,RUB,payment,1\n" + row)

    def test_invalid_headers(self):
        for header in (
            "id,currency,amount", "id,currency,kind,amount,extra",
            "id,currency,kind,kind", "ID,currency,kind,amount",
        ):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + "\n")

    def test_invalid_values_and_column_counts(self):
        rows = [
            ",RUB,payment,1", "a,GBP,payment,1", "a,rub,payment,1",
            "a,RUB,charge,1", "a,RUB,payment", "a,RUB,payment,1,extra",
            ",,,", 'a,RUB,payment,"1', 'a,RUB,payment,"1"extra',
        ]
        rows.extend("a,RUB,payment," + amount for amount in (
            "", "-1", "+1", "1e2", "NaN", "Infinity", ".5", "1.",
            "1_000", "١", "1 0", "1\x00",
        ))
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + row + "\n")

    def test_quoted_id_and_crlf(self):
        self.assertEqual(
            aggregate(self.header + '"a,b\r\nc",USD,payment,001.230\r\n'),
            {"USD": Decimal("1.23")},
        )

    def test_large_amounts_and_private_decimal_context(self):
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            result = aggregate(
                self.header
                + "a,EUR,payment,999999999999999999999999999999.995\n"
                + "b,EUR,refund,0.01\n"
            )
            self.assertEqual(result, {"EUR": Decimal("999999999999999999999999999999.99")})
            self.assertEqual(context.prec, 3)
            self.assertTrue(context.traps[Inexact])
