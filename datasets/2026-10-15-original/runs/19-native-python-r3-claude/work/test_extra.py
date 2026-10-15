from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def ok(self, body, expected, header=H):
        got = aggregate(header + body)
        self.assertEqual(got, expected)
        self.assertTrue(all(type(v) is Decimal for v in got.values()))
        for k, v in expected.items():
            self.assertEqual(str(got[k]), str(v))

    def bad(self, text):
        with self.assertRaises(ValueError):
            aggregate(text)

    def test_empty(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate(H), {})
        self.assertEqual(aggregate('id,currency,kind,amount'), {})
        self.assertEqual(aggregate('\n\n' + H + '\n'), {})

    def test_half_up_per_row(self):
        self.ok('a,RUB,payment,2.675\n', {'RUB': Decimal('2.68')})
        self.ok('a,RUB,payment,0.005\nb,RUB,payment,0.005\n', {'RUB': Decimal('0.02')})

    def test_zero_kept(self):
        self.ok('a,EUR,payment,0\n', {'EUR': Decimal('0.00')})
        self.ok('a,EUR,refund,0\n', {'EUR': Decimal('0.00')})
        self.ok('a,USD,payment,5\nb,USD,refund,5\n', {'USD': Decimal('0.00')})

    def test_refund_negative(self):
        self.ok('a,USD,refund,1.5\n', {'USD': Decimal('-1.50')})

    def test_duplicates(self):
        self.ok('a,RUB,payment,1\na,RUB,payment,1.00\n', {'RUB': Decimal('1.00')})
        self.ok('a,RUB,payment,1.001\na,RUB,payment,1.004\n', {'RUB': Decimal('1.00')})
        self.bad(H + 'a,RUB,payment,1\na,RUB,payment,2\n')
        self.bad(H + 'a,RUB,payment,1\na,USD,payment,1\n')
        self.bad(H + 'a,RUB,payment,1\na,RUB,refund,1\n')

    def test_bad_amounts(self):
        for amt in ['-1', '+1', '1e2', '1E2', 'NaN', 'Infinity', 'inf', '.5', '5.', 'abc', '', '1,0', '١']:
            self.bad(H + 'a,RUB,payment,"%s"\n' % amt)

    def test_bad_fields(self):
        self.bad(H + ',RUB,payment,1\n')
        self.bad(H + ',,,\n')
        self.bad(H + 'a,rub,payment,1\n')
        self.bad(H + 'a,GBP,payment,1\n')
        self.bad(H + 'a,RUB,Payment,1\n')
        self.bad(H + 'a,RUB,charge,1\n')

    def test_columns(self):
        self.bad(H + 'a,RUB,payment\n')
        self.bad(H + 'a,RUB,payment,1,x\n')
        self.bad('id,currency,kind\na,RUB,payment\n')
        self.bad('id,currency,kind,amount,x\na,RUB,payment,1,x\n')
        self.bad('id,id,kind,amount\na,b,payment,1\n')
        self.bad('id,currency,kind,value\na,RUB,payment,1\n')
        self.bad('a,RUB,payment,1\n')

    def test_reordered_and_spaces(self):
        self.ok('payment , 3 , USD , x\n', {'USD': Decimal('3.00')}, header=' kind,amount ,currency, id\n')
        self.ok(' a , RUB , payment , 1 \n\nb,RUB,payment,2\r\n', {'RUB': Decimal('3.00')})

    def test_big_amount(self):
        big = '1' * 80 + '.005'
        self.ok('a,RUB,payment,%s\n' % big, {'RUB': Decimal('1' * 80 + '.01')})

    def test_bad_csv(self):
        self.bad(H + 'a,"RUB"x,payment,1\n')


if __name__ == '__main__':
    unittest.main()
