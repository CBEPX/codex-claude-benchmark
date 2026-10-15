from decimal import Decimal, Inexact, localcontext
import unittest

from aggregate import aggregate


HEADER = 'id,currency,kind,amount\n'


class AggregateTests(unittest.TestCase):
    def test_empty_and_blank_rows(self):
        for text in ('', '\n\r\n', HEADER, '\n' + HEADER + '\n'):
            with self.subTest(text=text):
                self.assertEqual(aggregate(text), {})

    def test_reordered_header_and_trimmed_values(self):
        self.assertEqual(
            aggregate('amount,kind,id,currency\n 1.005 , payment , a , EUR \n'),
            {'EUR': Decimal('1.01')},
        )

    def test_round_each_row_and_preserve_zero(self):
        result = aggregate(HEADER +
                           'a,RUB,payment,0.005\n\n'
                           'b,RUB,payment,0.005\n'
                           'c,USD,refund,0.005\n'
                           'd,EUR,payment,0\n'
                           'e,RUB,refund,0.02\n')
        self.assertEqual(result, {'RUB': Decimal('0.00'),
                                  'USD': Decimal('-0.01'),
                                  'EUR': Decimal('0.00')})
        self.assertTrue(all(isinstance(value, Decimal) for value in result.values()))

    def test_duplicate_compares_quantized_amount(self):
        self.assertEqual(
            aggregate(HEADER + 'a,RUB,payment,1.004\n a , RUB , payment , 1.00 \n'),
            {'RUB': Decimal('1.00')},
        )
        for duplicate in ('a,USD,payment,1', 'a,RUB,refund,1', 'a,RUB,payment,1.005'):
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                aggregate(HEADER + 'a,RUB,payment,1\n' + duplicate)

    def test_invalid_headers(self):
        for header in ('id,currency,kind', 'id,currency,kind,amount,extra',
                       'id,currency,amount,amount', 'id,currency,kind,unknown',
                       'ID,currency,kind,amount'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                aggregate(header + '\n')

    def test_invalid_rows(self):
        for row in (',RUB,payment,1', 'a,GBP,payment,1', 'a,RUB,other,1',
                    'a,RUB,payment', 'a,RUB,payment,1,extra', ',,,',
                    'a,RUB,payment,"1', 'a,RUB,payment,"1"junk'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                aggregate(HEADER + row)

    def test_invalid_amounts(self):
        for amount in ('', '-1', '+1', '1e2', 'NaN', 'Infinity', '.5', '1.',
                       '1,2', '1_000', '١', '1 2'):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                aggregate(HEADER + f'a,RUB,payment,{amount}\n')

    def test_large_exact_values_and_caller_context(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            result = aggregate(HEADER +
                               'a,RUB,payment,99999999999999999999999999999.995\n'
                               'b,RUB,payment,0.01\n'
                               'c,RUB,refund,0.005\n')
            self.assertEqual(context.prec, 2)
        self.assertEqual(result, {'RUB': Decimal('100000000000000000000000000000.00')})
