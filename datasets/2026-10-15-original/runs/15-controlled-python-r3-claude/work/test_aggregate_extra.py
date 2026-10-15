from decimal import Decimal
import unittest

from aggregate import aggregate

HEADER = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def assertExact(self, result, expected):
        self.assertEqual(result, expected)
        for currency, value in result.items():
            self.assertIs(type(value), Decimal)
            self.assertEqual(str(value), str(expected[currency]))

    def test_empty_and_header_only(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate('\n\n'), {})
        self.assertEqual(aggregate(HEADER), {})
        self.assertEqual(aggregate('id,currency,kind,amount'), {})

    def test_column_order_and_whitespace(self):
        text = ' amount , kind ,id,currency\n 1.005 , payment , a , EUR \n'
        self.assertExact(aggregate(text), {'EUR': Decimal('1.01')})

    def test_blank_lines_skipped(self):
        text = HEADER + '\na,RUB,payment,1\n\r\n   \nb,RUB,payment,2\n\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('3.00')})

    def test_per_row_rounding(self):
        text = HEADER + 'a,USD,payment,0.005\nb,USD,payment,0.005\n'
        self.assertExact(aggregate(text), {'USD': Decimal('0.02')})
        text = HEADER + 'a,USD,payment,0.004\nb,USD,payment,0.004\n'
        self.assertExact(aggregate(text), {'USD': Decimal('0.00')})

    def test_zero_and_negative_totals_kept(self):
        text = HEADER + 'a,RUB,payment,0\nb,USD,payment,1\nc,USD,refund,1\nd,EUR,refund,2.5\n'
        self.assertExact(aggregate(text), {
            'RUB': Decimal('0.00'), 'USD': Decimal('0.00'), 'EUR': Decimal('-2.50')})

    def test_duplicates(self):
        text = HEADER + 'a,RUB,payment,1.001\na,RUB,payment,1.00\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('1.00')})
        for dup in ('a,USD,payment,1', 'a,RUB,refund,1', 'a,RUB,payment,1.01'):
            with self.assertRaises(ValueError):
                aggregate(HEADER + 'a,RUB,payment,1\n' + dup + '\n')

    def test_large_amount(self):
        big = '9' * 60 + '.995'
        expected = Decimal('1' + '0' * 60 + '.00')
        self.assertExact(aggregate(HEADER + 'a,RUB,payment,' + big + '\n'), {'RUB': expected})

    def test_invalid_headers(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,extra',
                       'id,currency,kind,kind', 'id,currency,type,amount',
                       'ID,currency,kind,amount', 'id,currency,kind,amount,amount'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + '\na,RUB,payment,1\n')

    def test_invalid_rows(self):
        rows = [
            ',RUB,payment,1', '  ,RUB,payment,1', 'a,rub,payment,1', 'a,GBP,payment,1',
            'a,RUB,Payment,1', 'a,RUB,charge,1', 'a,RUB,payment,', 'a,RUB,payment,-1',
            'a,RUB,payment,+1', 'a,RUB,payment,1e2', 'a,RUB,payment,NaN',
            'a,RUB,payment,Infinity', 'a,RUB,payment,.5', 'a,RUB,payment,5.',
            'a,RUB,payment,1,000', 'a,RUB,payment', 'a,RUB,payment,1,', 'a,RUB,payment,١',
            'a,RUB,payment,1_000', 'a,RUB,payment,1 000', ',,,',
            'a,RUB,payment,"1',
        ]
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + row + '\n')


if __name__ == '__main__':
    unittest.main()
