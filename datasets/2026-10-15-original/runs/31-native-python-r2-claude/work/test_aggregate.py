from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Aggregate(unittest.TestCase):
    def test_empty(self):
        for text in ('', H, '\n\n', '  \n' + H + '\n'):
            self.assertEqual(aggregate(text), {})

    def test_per_row_quantize_and_types(self):
        r = aggregate(H + 'a,RUB,payment,0.125\nb,RUB,payment,0.125\n')
        self.assertEqual(r, {'RUB': Decimal('0.26')})
        self.assertIsInstance(r['RUB'], Decimal)

    def test_order_strip_blank_zero(self):
        text = ' amount , kind,currency,id\n\n 5 , refund , EUR , x \n   \n0,payment,USD,y\n'
        self.assertEqual(aggregate(text), {'EUR': Decimal('-5.00'), 'USD': Decimal('0.00')})

    def test_duplicates(self):
        self.assertEqual(aggregate(H + 'a,USD,payment,1\na,USD,payment,1.004\n'), {'USD': Decimal('1.00')})
        for dup in ('a,USD,payment,2', 'a,EUR,payment,1', 'a,USD,refund,1'):
            with self.assertRaises(ValueError):
                aggregate(H + 'a,USD,payment,1\n' + dup + '\n')

    def test_invalid(self):
        bad_rows = [',RUB,payment,1', 'a,rub,payment,1', 'a,GBP,payment,1', 'a,RUB,pay,1',
                    'a,RUB,payment,1,2', 'a,RUB,payment', ',,,']
        bad_rows += ['a,RUB,payment,' + v for v in
                     ('-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '5.', '', '"1,5"', '١')]
        for row in bad_rows:
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + row + '\n')
        for header in ('id,currency,kind\n', 'id,currency,kind,amount,x\n',
                       'id,currency,kind,kind\n', 'id,currency,kind,sum\n'):
            with self.assertRaises(ValueError, msg=header):
                aggregate(header + 'a,RUB,payment,1\n')
        with self.assertRaises(ValueError):
            aggregate(H + 'a,RUB,payment,"1\n')

    def test_huge_amount(self):
        big = '9' * 40 + '.995'
        self.assertEqual(aggregate(H + 'a,RUB,payment,' + big + '\n'), {'RUB': Decimal('1' + '0' * 40 + '.00')})


if __name__ == '__main__':
    unittest.main()
