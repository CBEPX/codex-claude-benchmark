import unittest
from decimal import Decimal, localcontext

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    header = 'id,currency,kind,amount\n'

    def test_empty_and_blank_rows(self):
        for text in ('', '\n\r\n', self.header, '\n' + self.header + '\n'):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_reordered_columns_and_trimmed_values(self):
        self.assertEqual(
            aggregate('amount,kind,id,currency\n 1.005 , payment , a , EUR \n'),
            {'EUR': Decimal('1.01')},
        )

    def test_round_each_row_and_keep_zero(self):
        result = aggregate(self.header +
                           'a,RUB,payment,0.005\n'
                           'b,RUB,payment,0.005\n'
                           'c,USD,refund,1.005\n'
                           'd,USD,payment,1.01\n'
                           'e,EUR,refund,0\n')
        self.assertEqual(result, {'RUB': Decimal('0.02'),
                                  'USD': Decimal('0.00'),
                                  'EUR': Decimal('0.00')})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicate_ids_use_quantized_amount(self):
        self.assertEqual(aggregate(self.header +
                                   ' a ,RUB,payment,1.004\n'
                                   'a,RUB,payment,1.00\n'),
                         {'RUB': Decimal('1.00')})
        for row in ('a,USD,payment,1', 'a,RUB,refund,1', 'a,RUB,payment,1.005'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + 'a,RUB,payment,1\n' + row + '\n')

    def test_invalid_headers(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,extra',
                       'id,currency,amount,amount', 'ID,currency,kind,amount',
                       'a,RUB,payment,1'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + '\n')

    def test_invalid_rows(self):
        rows = ['a,RUB,payment', 'a,RUB,payment,1,extra', ',RUB,payment,1',
                'a,GBP,payment,1', 'a,RUB,charge,1', ',,,',
                '"a,RUB,payment,1', '"a"x,RUB,payment,1']
        rows += ['a,RUB,payment,' + amount for amount in
                 ('', '-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '1.',
                  '1_000', '1,2', '１２', '1 2')]
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(self.header + row + '\n')

    def test_large_totals_ignore_decimal_precision(self):
        with localcontext() as context:
            context.prec = 3
            result = aggregate(self.header +
                               'a,RUB,payment,999999999999999999999999999999.995\n'
                               'b,RUB,payment,0.01\n'
                               'c,RUB,refund,0.02\n')
        self.assertEqual(result, {'RUB': Decimal('999999999999999999999999999999.99')})
