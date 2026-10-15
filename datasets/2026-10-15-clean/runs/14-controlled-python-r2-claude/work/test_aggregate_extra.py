from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def assertExact(self, result, expected):
        self.assertEqual(result, expected)
        for currency, value in result.items():
            self.assertIs(type(value), Decimal)
            self.assertEqual(str(value), str(expected[currency]))

    def test_empty_and_header_only(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate('\n\n'), {})
        self.assertEqual(aggregate(H), {})
        self.assertEqual(aggregate('amount,kind,currency,id'), {})

    def test_reordered_columns_and_whitespace(self):
        text = ' amount , id ,kind,currency\n 1.005 , a , payment , EUR \n\n2,b,refund,EUR\n'
        self.assertExact(aggregate(text), {'EUR': Decimal('-0.99')})

    def test_per_row_rounding(self):
        text = H + 'a,RUB,payment,0.005\nb,RUB,payment,0.005\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('0.02')})

    def test_zero_kept(self):
        self.assertExact(aggregate(H + 'a,USD,payment,0\n'), {'USD': Decimal('0.00')})
        self.assertExact(aggregate(H + 'a,USD,refund,0.001\n'), {'USD': Decimal('0.00')})
        text = H + 'a,USD,payment,5\nb,USD,refund,5\n'
        self.assertExact(aggregate(text), {'USD': Decimal('0.00')})

    def test_exact_duplicate_counted_once(self):
        text = H + 'a,RUB,payment,1.004\na,RUB,payment,1.00\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('1.00')})

    def test_conflicting_duplicate(self):
        for second in ('a,RUB,payment,2', 'a,USD,payment,1', 'a,RUB,refund,1'):
            with self.subTest(second=second):
                with self.assertRaises(ValueError):
                    aggregate(H + 'a,RUB,payment,1\n' + second + '\n')

    def test_large_amount_exact(self):
        big = '1' * 60 + '.555'
        self.assertExact(aggregate(H + f'a,EUR,payment,{big}\n'),
                         {'EUR': Decimal('1' * 60 + '.56')})

    def test_invalid_header(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,extra',
                       'id,currency,kind,kind', 'id,currency,type,amount',
                       'id,id,currency,kind,amount'):
            with self.subTest(header=header):
                with self.assertRaises(ValueError):
                    aggregate(header + '\na,RUB,payment,1\n')

    def test_invalid_rows(self):
        bad = [
            ',RUB,payment,1', '  ,RUB,payment,1', 'a,GBP,payment,1', 'a,rub,payment,1',
            'a,RUB,Payment,1', 'a,RUB,charge,1', 'a,RUB,payment,', 'a,RUB,payment,-1',
            'a,RUB,payment,+1', 'a,RUB,payment,1e2', 'a,RUB,payment,NaN',
            'a,RUB,payment,Infinity', 'a,RUB,payment,.5', 'a,RUB,payment,5.',
            'a,RUB,payment,1_000', 'a,RUB,payment,1 000', 'a,RUB,payment,١',
            'a,RUB,payment', 'a,RUB,payment,1,x', ',,,', 'a,RUB,payment,"1',
        ]
        for row in bad:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    aggregate(H + row + '\n')


if __name__ == '__main__':
    unittest.main()
