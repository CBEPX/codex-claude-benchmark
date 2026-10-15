from decimal import Decimal
import unittest
from aggregate import aggregate
H='id,currency,kind,amount\n'
class Acceptance(unittest.TestCase):
 def test_empty(self):
  self.assertEqual(aggregate(''),{})
  self.assertEqual(aggregate(H),{})
 def test_round_each_half_up(self):
  self.assertEqual(aggregate(H+'a,EUR,payment,1.005\nb,EUR,payment,1.005\nc,EUR,refund,0.005\n'),{'EUR':Decimal('2.01')})
 def test_duplicate(self):
  self.assertEqual(aggregate(H+'a,RUB,payment,2\na,RUB,payment,2.000\n'),{'RUB':Decimal('2.00')})
 def test_conflicting_duplicate(self):
  with self.assertRaises(ValueError):aggregate(H+'a,RUB,payment,2\na,RUB,refund,2\n')
 def test_invalid_rows(self):
  for row in ['a,RUB,payment,-1','a,RUB,payment,NaN','a,RUB,payment,Infinity','a,RUB,payment,1e3','a,RUB,payment,1.','a,RUB,payment,+1','a,GBP,payment,2','a,RUB,other,2',',RUB,payment,2','a,RUB,payment','a,RUB,payment,2,extra']:
   with self.subTest(row=row):
    with self.assertRaises(ValueError):aggregate(H+row+'\n')
 def test_headers(self):
  for value in ['id,currency,amount\n','id,currency,kind,amount,extra\n','id,id,kind,amount\n']:
   with self.assertRaises(ValueError):aggregate(value)
 def test_whitespace(self):
  self.assertEqual(aggregate(H+' a , RUB , payment , 1.235 \nb,RUB,refund,0.24\n'),{'RUB':Decimal('1.00')})
 def test_types_and_currencies(self):
  got=aggregate(H+'a,USD,payment,0\nb,EUR,refund,1\n')
  self.assertEqual(got,{'USD':Decimal('0.00'),'EUR':Decimal('-1.00')})
  self.assertTrue(all(isinstance(v,Decimal) for v in got.values()))
