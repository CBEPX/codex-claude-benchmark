from decimal import Decimal, getcontext
import unittest
from aggregate import aggregate
H='id,currency,kind,amount\n'
class Acceptance(unittest.TestCase):
 def test_empty(self):
  self.assertEqual(aggregate(''),{})
  self.assertEqual(aggregate(H),{})
  self.assertEqual(aggregate(H+'\n\r\n'),{})
  self.assertEqual(aggregate(H+'\na,RUB,payment,1\n\nb,RUB,refund,1\n'),{'RUB':Decimal('0.00')})
 def test_round_each_half_up(self):
  context_before=str(getcontext())
  self.assertEqual(aggregate(H+'a,EUR,payment,1.005\nb,EUR,payment,1.005\nc,EUR,refund,0.005\n'),{'EUR':Decimal('2.01')})
  self.assertEqual(aggregate(H+'a,USD,payment,123456789012345678901234567890.125\nb,USD,payment,0.005\nc,USD,refund,123456789012345678901234567890.12\n'),{'USD':Decimal('0.02')})
  self.assertEqual(str(getcontext()),context_before)
 def test_duplicate(self):
  self.assertEqual(aggregate(H+'a,RUB,payment,2\na,RUB,payment,2.000\n'),{'RUB':Decimal('2.00')})
  self.assertEqual(aggregate(H+'a,RUB,payment,2.001\na,RUB,payment,2.004\n'),{'RUB':Decimal('2.00')})
 def test_conflicting_duplicate(self):
  with self.assertRaises(ValueError):aggregate(H+'a,RUB,payment,2\na,RUB,refund,2\n')
  for row in ['a,USD,payment,2','a,RUB,payment,2.01']:
   with self.subTest(row=row):
    with self.assertRaises(ValueError):aggregate(H+'a,RUB,payment,2\n'+row+'\n')
 def test_invalid_rows(self):
  for row in ['a,RUB,payment,','a,RUB,payment,.5','a,RUB,payment,1_0','a,RUB,payment,١','a,RUB,payment,1 0','a,RUB,payment,-1','a,RUB,payment,NaN','a,RUB,payment,Infinity','a,RUB,payment,1e3','a,RUB,payment,1.','a,RUB,payment,+1','a,GBP,payment,2','a,RUB,other,2',',RUB,payment,2','a,RUB,payment','a,RUB,payment,2,extra']:
   with self.subTest(row=row):
    with self.assertRaises(ValueError):aggregate(H+row+'\n')
  for value in [H+'"unterminated', H+'"a"x,RUB,payment,1\n', '"unterminated']:
   with self.subTest(value=value):
    with self.assertRaises(ValueError):aggregate(value)
 def test_headers(self):
  for value in ['id,currency,amount\n','id,currency,kind,amount,extra\n','id,id,kind,amount\n']:
   with self.assertRaises(ValueError):aggregate(value)
  self.assertEqual(aggregate('amount,kind,id,currency\n1.235,payment,a,USD\n'),{'USD':Decimal('1.24')})
  self.assertEqual(aggregate(H+'"a,b",USD,payment,1\n"a,b",USD,payment,1.00\n'),{'USD':Decimal('1.00')})
 def test_whitespace(self):
  self.assertEqual(aggregate(H+' a , RUB , payment , 1.235 \nb,RUB,refund,0.24\n'),{'RUB':Decimal('1.00')})
 def test_types_and_currencies(self):
  got=aggregate(H+'a,USD,payment,0\nb,EUR,refund,1\n')
  self.assertEqual(got,{'USD':Decimal('0.00'),'EUR':Decimal('-1.00')})
  self.assertTrue(all(isinstance(v,Decimal) for v in got.values()))
