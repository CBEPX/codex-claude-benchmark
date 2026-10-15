import unittest
from decimal import Decimal, localcontext

from aggregate import aggregate


HEADER = "id,currency,kind,amount\n"


class AggregateTests(unittest.TestCase):
    def test_empty_and_header_only(self):
        for text in ("", "\n\r\n", HEADER, "\n" + HEADER + "\n"):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_order_whitespace_blank_lines_and_zero(self):
        result = aggregate(
            "amount,kind,id,currency\n\n"
            " 1.005 , payment , a , EUR \n"
            "\n1.01,refund,b,EUR\n0,payment,c,USD\n"
        )
        self.assertEqual(result, {"EUR": Decimal("0.00"), "USD": Decimal("0.00")})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_round_each_row_and_refund(self):
        self.assertEqual(
            aggregate(HEADER + "a,RUB,payment,0.005\nb,RUB,payment,0.005\nc,EUR,refund,0.005\n"),
            {"RUB": Decimal("0.02"), "EUR": Decimal("-0.01")},
        )

    def test_duplicate_after_quantization(self):
        self.assertEqual(
            aggregate(HEADER + "a,USD,payment,1.001\n a , USD , payment ,1.004\n"),
            {"USD": Decimal("1.00")},
        )
        for row in ("a,EUR,payment,1", "a,USD,refund,1", "a,USD,payment,1.005"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + "a,USD,payment,1\n" + row)

    def test_invalid_headers(self):
        for header in (
            "id,currency,kind", "id,currency,kind,amount,extra",
            "id,currency,amount,amount", "id,currency,kind,value",
        ):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + "\n")

    def test_invalid_rows(self):
        for row in (
            ",USD,payment,1", " ,USD,payment,1", "a,GBP,payment,1",
            "a,usd,payment,1", "a,USD,other,1", "a,USD,payment",
            "a,USD,payment,1,extra", ",,,", 'a,USD,payment,"1',
            'a,USD,payment,"1"x',
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + row)

    def test_invalid_amounts(self):
        for amount in (
            "", "-1", "+1", ".1", "1.", "1e2", "NaN", "Infinity",
            "1_000", "1 0", "١", "１", "1.2.3",
        ):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                aggregate(HEADER + "a,USD,payment," + amount)

    def test_exact_large_amounts_with_small_decimal_context(self):
        amount = "9999999999999999999999999999999999999999.995"
        with localcontext() as context:
            context.prec = 3
            result = aggregate(HEADER + f"a,USD,payment,{amount}\nb,USD,payment,0.01\n")
            self.assertEqual(context.prec, 3)
        self.assertEqual(result, {"USD": Decimal("10000000000000000000000000000000000000000.01")})
