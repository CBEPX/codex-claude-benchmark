from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def assertExact(self, result, expected):
        self.assertEqual(result, expected)
        for key, value in result.items():
            self.assertIs(type(value), Decimal)
            self.assertEqual(str(value), str(expected[key]))

    def test_empty_and_header_only(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate(H), {})
        self.assertEqual(aggregate('\n\n' + H + '\n'), {})

    def test_column_order_and_whitespace(self):
        text = ' amount , kind ,id, currency\n 1.005 , payment , a , EUR \n\n'
        self.assertExact(aggregate(text), {'EUR': Decimal('1.01')})

    def test_per_row_rounding(self):
        text = H + 'a,USD,payment,0.005\nb,USD,payment,0.005\nc,USD,refund,0.004\n'
        self.assertExact(aggregate(text), {'USD': Decimal('0.02')})

    def test_zero_kept(self):
        text = H + 'a,RUB,payment,5\nb,RUB,refund,5.00\nc,EUR,payment,0.001\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('0.00'), 'EUR': Decimal('0.00')})

    def test_negative_total(self):
        self.assertExact(aggregate(H + 'a,USD,refund,2.5\n'), {'USD': Decimal('-2.50')})

    def test_large_amount_exact(self):
        big = '1' * 40 + '.125'
        self.assertExact(aggregate(H + f'a,USD,payment,{big}\n'), {'USD': Decimal('1' * 40 + '.13')})

    def test_duplicates(self):
        text = H + 'a,USD,payment,1.004\na,USD,payment,1.00\n'
        self.assertExact(aggregate(text), {'USD': Decimal('1.00')})
        for dup in ('a,EUR,payment,1', 'a,USD,refund,1', 'a,USD,payment,1.01'):
            with self.assertRaises(ValueError):
                aggregate(H + 'a,USD,payment,1\n' + dup + '\n')

    def test_bad_headers(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,x',
                       'id,currency,kind,kind', 'id,currency,type,amount',
                       'id,id,currency,kind,amount'):
            with self.assertRaises(ValueError, msg=header):
                aggregate(header + '\na,USD,payment,1\n')

    def test_bad_rows(self):
        rows = ('a,USD,payment', 'a,USD,payment,1,2', ' ,USD,payment,1',
                'a,usd,payment,1', 'a,GBP,payment,1', 'a,USD,Payment,1',
                'a,USD,payment,', 'a,USD,payment,-1', 'a,USD,payment,+1',
                'a,USD,payment,1e2', 'a,USD,payment,NaN', 'a,USD,payment,Infinity',
                'a,USD,payment,.5', 'a,USD,payment,5.', 'a,USD,payment,1_000',
                'a,USD,payment,١', 'a,USD,payment,1 2', ',,,',
                'a,USD,payment,"1')
        for row in rows:
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + row + '\n')


if __name__ == '__main__':
    unittest.main()
