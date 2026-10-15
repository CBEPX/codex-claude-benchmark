from decimal import Decimal, localcontext
import unittest

from aggregate import aggregate


HEADER = 'id,currency,kind,amount\n'


class AggregateTests(unittest.TestCase):
    def test_empty_input_and_blank_rows(self):
        for text in ('', '\n\n', HEADER, '\n' + HEADER + '\n\n'):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_reordered_columns_and_trimmed_values(self):
        self.assertEqual(
            aggregate('amount,kind,id,currency\r\n 1.005 , payment , a , EUR \r\n'),
            {'EUR': Decimal('1.01')},
        )

    def test_round_each_row_and_keep_zero(self):
        result = aggregate(HEADER + 'a,RUB,payment,0.005\n'
                           'b,RUB,payment,0.005\nc,USD,refund,1.005\n'
                           'd,EUR,payment,0.004\ne,EUR,refund,0.004\n')
        self.assertEqual(result, {'RUB': Decimal('0.02'),
                                  'USD': Decimal('-1.01'), 'EUR': Decimal('0.00')})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicate_id_compares_rounded_amount(self):
        self.assertEqual(
            aggregate(HEADER + 'a,USD,payment,1.001\na,USD,payment,1.004\n'),
            {'USD': Decimal('1.00')},
        )
        for row in ('a,EUR,payment,1', 'a,USD,refund,1', 'a,USD,payment,1.005'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + 'a,USD,payment,1\n' + row + '\n')

    def test_invalid_headers(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,extra',
                       'id,currency,amount,amount', 'id,currency,kind,unknown'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + '\n')

    def test_invalid_rows(self):
        rows = ('a,USD,payment', 'a,USD,payment,1,extra', ',USD,payment,1',
                'a,usd,payment,1', 'a,GBP,payment,1', 'a,USD,charge,1',
                'a,USD,payment,"1', ',,,')
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + row + '\n')

    def test_invalid_amounts(self):
        for amount in ('', '-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '1.',
                       '1_000', '1 000', '\u0661', '1.2.3'):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                aggregate(HEADER + 'a,USD,payment,' + amount + '\n')

    def test_large_amount_and_carry_ignore_context_precision(self):
        with localcontext() as context:
            context.prec = 2
            result = aggregate(HEADER + 'a,RUB,payment,9999999999999999999999999999.995\n'
                               'b,RUB,payment,0.01\nc,RUB,refund,0.02\n')
            self.assertEqual(context.prec, 2)
        self.assertEqual(result, {'RUB': Decimal('9999999999999999999999999999.99')})
