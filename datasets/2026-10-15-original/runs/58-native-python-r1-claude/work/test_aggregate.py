from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Aggregate(unittest.TestCase):
    def bad(self, text):
        with self.assertRaises(ValueError):
            aggregate(text)

    def test_empty(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate('\n\n'), {})
        self.assertEqual(aggregate(H), {})

    def test_header(self):
        self.assertEqual(aggregate('amount,kind,id,currency\n1,payment,a,EUR\n'), {'EUR': Decimal('1.00')})
        self.assertEqual(aggregate(' id , currency,kind ,amount\na,RUB,payment,1\n'), {'RUB': Decimal('1.00')})
        for h in ('id,id,kind,amount', 'id,currency,kind', 'id,currency,kind,amount,x', 'ID,currency,kind,amount'):
            self.bad(h + '\n')

    def test_rows(self):
        self.bad(H + 'a,RUB,payment\n')
        self.bad(H + 'a,RUB,payment,1,x\n')
        self.bad(H + ',,,\n')
        self.bad(H + ' ,RUB,payment,1\n')
        self.bad(H + 'a,rub,payment,1\n')
        self.bad(H + 'a,GBP,payment,1\n')
        self.bad(H + 'a,RUB,Payment,1\n')
        self.bad(H + 'a,RUB,"payment,1\n')
        self.assertEqual(aggregate(H + '\n a , RUB , payment , 1 \n\n  \nb,RUB,refund,0.5\n'), {'RUB': Decimal('0.50')})

    def test_amount(self):
        for a in ('-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '5.', '1_000', '٣', '', '1.2.3', '0x1'):
            self.bad(H + 'a,RUB,payment,' + a + '\n')

    def test_rounding(self):
        self.assertEqual(aggregate(H + 'a,RUB,payment,0.004\nb,RUB,payment,0.004\n'), {'RUB': Decimal('0.00')})
        self.assertEqual(aggregate(H + 'a,RUB,payment,0.005\n'), {'RUB': Decimal('0.01')})
        self.assertEqual(aggregate(H + 'a,RUB,payment,0.015\nb,USD,refund,2.675\n'),
                         {'RUB': Decimal('0.02'), 'USD': Decimal('-2.68')})

    def test_zero_and_negative(self):
        self.assertEqual(aggregate(H + 'a,RUB,payment,0\n'), {'RUB': Decimal('0.00')})
        self.assertEqual(aggregate(H + 'a,RUB,payment,5\nb,RUB,refund,5\n'), {'RUB': Decimal('0.00')})
        self.assertEqual(str(aggregate(H + 'a,RUB,refund,0\n')['RUB']), '0.00')
        self.assertEqual(aggregate(H + 'a,USD,refund,3\n'), {'USD': Decimal('-3.00')})

    def test_duplicates(self):
        self.assertEqual(aggregate(H + 'a,RUB,payment,1.004\na,RUB,payment,1.00\n'), {'RUB': Decimal('1.00')})
        self.bad(H + 'a,RUB,payment,1\na,USD,payment,1\n')
        self.bad(H + 'a,RUB,payment,1\na,RUB,refund,1\n')
        self.bad(H + 'a,RUB,payment,1\na,RUB,payment,1.01\n')

    def test_big_and_types(self):
        big = '1' + '0' * 30
        r = aggregate(H + 'a,EUR,payment,' + big + '.005\nb,EUR,payment,0.01\n')
        self.assertEqual(r, {'EUR': Decimal(big + '.02')})
        for v in r.values():
            self.assertIsInstance(v, Decimal)
            self.assertEqual(v.as_tuple().exponent, -2)


if __name__ == '__main__':
    unittest.main()
