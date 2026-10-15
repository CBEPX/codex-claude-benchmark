from decimal import Decimal
import unittest
from aggregate import aggregate

H = 'id,currency,kind,amount\n'


class Extra(unittest.TestCase):
    def test_empty_and_header_only(self):
        self.assertEqual(aggregate(''), {})
        self.assertEqual(aggregate('\n\n  \n'), {})
        self.assertEqual(aggregate(H), {})
        self.assertEqual(aggregate(H + '\n\n'), {})

    def test_permuted_header_and_whitespace(self):
        r = aggregate(' amount , kind ,id,currency\n 1.5 , payment , a , EUR \n')
        self.assertEqual(r, {'EUR': Decimal('1.50')})
        self.assertEqual(str(r['EUR']), '1.50')

    def test_blank_lines_skipped(self):
        r = aggregate('\n' + H + '\na,RUB,payment,1\n\n\r\nb,RUB,payment,2\n')
        self.assertEqual(r, {'RUB': Decimal('3.00')})

    def test_bad_headers(self):
        for h in ['id,currency,kind\n', 'id,currency,kind,amount,x\n',
                  'id,currency,kind,kind\n', 'id,id,currency,kind,amount\n',
                  'ID,currency,kind,amount\n', 'id,currency,type,amount\n']:
            with self.assertRaises(ValueError, msg=h):
                aggregate(h + 'a,RUB,payment,1\n')

    def test_bad_column_count(self):
        for row in ['a,RUB,payment\n', 'a,RUB,payment,1,\n', 'a\n']:
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + row)

    def test_bad_values(self):
        for row in [',RUB,payment,1', ' ,RUB,payment,1', ',,,', 'a,rub,payment,1',
                    'a,GBP,payment,1', 'a,RUB,Payment,1', 'a,RUB,charge,1']:
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + row + '\n')

    def test_bad_amounts(self):
        for amt in ['', '-1', '+1', '.5', '5.', '1e5', '1E5', 'NaN', 'Infinity',
                    'inf', '1_000', '1,0', '١', '1.2.3', '0x1', '1 0']:
            with self.assertRaises(ValueError, msg=amt):
                aggregate(H + 'a,RUB,payment,"' + amt + '"\n')

    def test_half_up_per_row(self):
        r = aggregate(H + 'a,RUB,payment,0.005\nb,RUB,payment,0.005\n'
                      'c,USD,payment,2.675\nd,EUR,payment,1.015\n')
        self.assertEqual(r, {'RUB': Decimal('0.02'), 'USD': Decimal('2.68'),
                             'EUR': Decimal('1.02')})

    def test_zero_preserved(self):
        r = aggregate(H + 'a,USD,payment,0\nb,EUR,payment,5\nc,EUR,refund,5\n'
                      'd,RUB,refund,0.004\n')
        self.assertEqual(r, {'USD': Decimal('0'), 'EUR': Decimal('0'),
                             'RUB': Decimal('0')})
        for v in r.values():
            self.assertIsInstance(v, Decimal)
            self.assertEqual(str(v), '0.00')

    def test_negative_total(self):
        self.assertEqual(aggregate(H + 'a,USD,refund,3\n'), {'USD': Decimal('-3.00')})

    def test_exact_duplicate_once(self):
        r = aggregate(H + 'a,RUB,payment,1.00\na,RUB,payment,1\n a ,RUB,payment,1.004\n')
        self.assertEqual(r, {'RUB': Decimal('1.00')})

    def test_conflicting_duplicates(self):
        for row in ['a,USD,payment,1', 'a,RUB,refund,1', 'a,RUB,payment,1.01']:
            with self.assertRaises(ValueError, msg=row):
                aggregate(H + 'a,RUB,payment,1\n' + row + '\n')

    def test_large_amounts_exact(self):
        big = '1' * 40
        r = aggregate(H + f'a,RUB,payment,{big}.005\nb,RUB,payment,1\n')
        self.assertEqual(r, {'RUB': Decimal('1' * 39 + '2.01')})
        self.assertEqual(str(r['RUB']), '1' * 39 + '2.01')

    def test_malformed_csv(self):
        with self.assertRaises(ValueError):
            aggregate(H + 'a,RUB,payment,"1\n')
        with self.assertRaises(ValueError):
            aggregate(H + 'a,RUB,"payment"x,1\n')

    def test_returns_decimal(self):
        r = aggregate(H + 'a,RUB,payment,0.1\n')
        self.assertIs(type(r['RUB']), Decimal)


if __name__ == '__main__':
    unittest.main()
