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
        self.assertEqual(aggregate('amount,kind,currency,id'), {})

    def test_column_order_whitespace_blank_lines(self):
        text = ' amount , kind ,currency,id\r\n\r\n 1.5 , payment , EUR , x \r\n\n2,refund,EUR,y\n'
        self.assertExact(aggregate(text), {'EUR': Decimal('-0.50')})

    def test_rounding_per_row_half_up(self):
        text = H + 'a,RUB,payment,0.005\nb,RUB,payment,0.005\nc,USD,payment,2.675\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('0.02'), 'USD': Decimal('2.68')})

    def test_zero_preserved(self):
        self.assertExact(aggregate(H + 'a,USD,payment,0.004\n'), {'USD': Decimal('0.00')})
        self.assertExact(aggregate(H + 'a,USD,payment,5\nb,USD,refund,5\n'), {'USD': Decimal('0.00')})

    def test_large_amount_exact(self):
        big = '1' * 40
        self.assertExact(aggregate(H + f'a,RUB,payment,{big}.125\n'), {'RUB': Decimal(big + '.13')})

    def test_duplicates(self):
        text = H + 'a,RUB,payment,1.001\na,RUB,payment,1.004\n'
        self.assertExact(aggregate(text), {'RUB': Decimal('1.00')})
        for dup in ('a,RUB,payment,1.01', 'a,USD,payment,1', 'a,RUB,refund,1'):
            with self.assertRaises(ValueError):
                aggregate(H + 'a,RUB,payment,1\n' + dup + '\n')

    def test_invalid(self):
        bad = [
            'id,currency,kind\na,RUB,payment\n',
            'id,currency,kind,amount,extra\n',
            'id,currency,kind,kind\n',
            'id,currency,kind,amount,id\n',
            'ID,currency,kind,amount\n',
            H + 'a,RUB,payment\n',
            H + 'a,RUB,payment,1,\n',
            H + ',RUB,payment,1\n',
            H + ' ,RUB,payment,1\n',
            H + 'a,rub,payment,1\n',
            H + 'a,GBP,payment,1\n',
            H + 'a,RUB,Payment,1\n',
            H + 'a,RUB,charge,1\n',
            H + '"a,RUB,payment,1\n',
        ]
        for amount in ('', '-1', '+1', '1e2', 'NaN', 'Infinity', 'inf', '.5', '5.',
                       '1.2.3', '1_000', '١', '1 000', '0x10'):
            bad.append(H + 'a,RUB,payment,"%s"\n' % amount)
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                aggregate(text)


if __name__ == '__main__':
    unittest.main()
