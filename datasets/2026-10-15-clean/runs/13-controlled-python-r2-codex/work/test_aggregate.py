import unittest
from decimal import Decimal, Inexact, localcontext

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    header = "id,currency,kind,amount\n"

    def test_empty_and_header_only(self):
        for text in ("", "\n\r\n", self.header, "\n" + self.header + "\n"):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_reordered_columns_whitespace_and_blank_rows(self):
        self.assertEqual(
            aggregate("amount,kind,currency,id\r\n\r\n 1.005 , payment , EUR , a \r\n"),
            {"EUR": Decimal("1.01")},
        )

    def test_round_each_row_and_keep_zero_totals(self):
        result = aggregate(self.header + (
            "a,RUB,payment,0.005\nb,RUB,payment,0.005\n"
            "c,USD,payment,1.005\nd,USD,refund,1.005\n"
            "e,EUR,refund,0.005\n"
        ))
        self.assertEqual(result, {
            "RUB": Decimal("0.02"), "USD": Decimal("0.00"),
            "EUR": Decimal("-0.01"),
        })
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicate_ids_compare_quantized_amounts(self):
        self.assertEqual(aggregate(self.header + (
            "a,RUB,payment,1.001\n a , RUB , payment , 1.004 \n"
        )), {"RUB": Decimal("1.00")})
        for row in ("a,USD,payment,1", "a,RUB,refund,1", "a,RUB,payment,1.005"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + "a,RUB,payment,1\n" + row)

    def test_invalid_headers(self):
        for header in (
            "id,currency,kind", "id,currency,kind,amount,extra",
            "id,currency,amount,amount", "id,currency,kind,other",
        ):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + "\n")

    def test_invalid_fields_and_column_counts(self):
        for row in (
            ",RUB,payment,1", "  ,RUB,payment,1", "a,GBP,payment,1",
            "a,rub,payment,1", "a,RUB,Payment,1", "a,RUB,other,1",
            "a,RUB,payment", "a,RUB,payment,1,extra", ",,,", " ",
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + row + "\n")

    def test_invalid_amounts(self):
        for amount in (
            "", "-1", "+1", "1e2", "NaN", "Infinity", ".1", "1.",
            "1_000", "1 0", "١", "１", "1.2.3",
        ):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                aggregate(self.header + "a,RUB,payment," + amount + "\n")

    def test_malformed_csv(self):
        for row in ('a,RUB,payment,"1', 'a,RUB,payment,"1"oops'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + row)

    def test_large_totals_and_external_decimal_context(self):
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            result = aggregate(self.header + (
                "a,RUB,payment,999999999999999999999999999999.995\n"
                "b,RUB,payment,0.01\nc,RUB,refund,0.005\n"
            ))
        self.assertEqual(result, {"RUB": Decimal("1000000000000000000000000000000.00")})
