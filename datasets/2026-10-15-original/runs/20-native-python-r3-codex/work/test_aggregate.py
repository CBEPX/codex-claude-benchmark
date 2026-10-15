from decimal import Decimal, localcontext
import unittest

from aggregate import aggregate


class AggregateTests(unittest.TestCase):
    def test_empty_and_blank_rows(self):
        for text in ('', '\n\n', 'id,currency,kind,amount\n\n'):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_rounding_duplicates_and_reordered_columns(self):
        text = ('amount,kind,id,currency\n\n'
                ' 1.005 , payment , a , RUB \n'
                '1.01,payment,a,RUB\n'
                '0.005,refund,b,RUB\n'
                '1,payment,c,EUR\n'
                '1,refund,d,EUR\n')
        result = aggregate(text)
        self.assertEqual(result, {'RUB': Decimal('1.00'), 'EUR': Decimal('0.00')})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_each_row_is_rounded(self):
        self.assertEqual(aggregate('id,currency,kind,amount\n'
                                   'a,USD,payment,0.005\n'
                                   'b,USD,payment,0.005\n'),
                         {'USD': Decimal('0.02')})

    def test_large_amounts_do_not_lose_precision(self):
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(aggregate('id,currency,kind,amount\n'
                                       'a,RUB,payment,999999999999999999999999999999.995\n'
                                       'b,RUB,payment,0.01\n'),
                             {'RUB': Decimal('1000000000000000000000000000000.01')})

    def test_invalid_headers(self):
        for header in ('id,currency,amount', 'id,currency,kind,amount,extra',
                       'id,currency,amount,amount', 'id,currency,kind,other'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + '\n')

    def test_invalid_rows(self):
        rows = ['a,RUB,payment', 'a,RUB,payment,1,extra', ',RUB,payment,1',
                'a,GBP,payment,1', 'a,RUB,other,1', ',,,',
                '"a,RUB,payment,1']
        rows += ['a,RUB,payment,' + amount for amount in
                 ('', '-1', '+1', '1e2', 'NaN', 'Infinity', '.1', '1.',
                  '1_000', '١', '1 0')]
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate('id,currency,kind,amount\n' + row + '\n')

    def test_duplicate_conflicts(self):
        for row in ('a,USD,payment,1', 'a,RUB,refund,1', 'a,RUB,payment,1.01'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate('id,currency,kind,amount\na,RUB,payment,1\n' + row)
