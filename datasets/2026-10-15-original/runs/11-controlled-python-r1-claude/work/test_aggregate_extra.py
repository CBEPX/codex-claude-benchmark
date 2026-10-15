from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate(H), {})
        self.assertEqual(aggregate(H + '\n\n'), {})

    def test_column_order_and_whitespace(self):
        r = aggregate(' amount , kind ,id,currency\n 1.005 , payment , a , EUR \n\n')
        self.assertEqual(r, {'EUR': Decimal('1.01')})
        self.assertIsInstance(r['EUR'], Decimal)

    def test_per_row_rounding(self):
        r = aggregate(H + 'a,RUB,payment,0.005\nb,RUB,payment,0.005\n')
        self.assertEqual(r, {'RUB': Decimal('0.02')})

    def test_zero_kept(self):
        r = aggregate(H + 'a,USD,payment,0\nb,USD,refund,0.004\n')
        self.assertEqual(r, {'USD': Decimal('0.00')})
        self.assertEqual(str(r['USD']), '0.00')

    def test_negative_total(self):
        self.assertEqual(aggregate(H + 'a,USD,refund,5\n'), {'USD': Decimal('-5.00')})

    def test_duplicate_exact(self):
        r = aggregate(H + 'a,RUB,payment,1.001\na,RUB,payment,1.00\n')
        self.assertEqual(r, {'RUB': Decimal('1.00')})

    def test_duplicate_conflict(self):
        for row in ('a,RUB,payment,2', 'a,USD,payment,1', 'a,RUB,refund,1'):
            with self.assertRaises(ValueError):
                aggregate(H + 'a,RUB,payment,1\n' + row + '\n')

    def test_bad_amounts(self):
        for amt in ('-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '5.', '', '1,0', '١'):
            with self.assertRaises(ValueError, msg=amt):
                aggregate(H + f'a,RUB,payment,"{amt}"\n')

    def test_bad_values(self):
        for row in (',RUB,payment,1', 'a,GBP,payment,1', 'a,rub,payment,1',
                    'a,RUB,charge,1', 'a,RUB,payment', 'a,RUB,payment,1,x'):
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + row + '\n')

    def test_bad_headers(self):
        for h in ('id,currency,kind', 'id,currency,kind,amount,x',
                  'id,id,kind,amount', 'id,currency,kind,sum'):
            with self.assertRaises(ValueError, msg=h):
                aggregate(h + '\n')

    def test_malformed_quote(self):
        with self.assertRaises(ValueError):
            aggregate(H + 'a,RUB,payment,"1\n')

    def test_huge_amount(self):
        big = '9' * 40 + '.995'
        r = aggregate(H + f'a,RUB,payment,{big}\n')
        self.assertEqual(r, {'RUB': Decimal('1' + '0' * 40 + '.00')})


if __name__ == '__main__':
    unittest.main()
