from decimal import Decimal
import unittest
from aggregate import aggregate
class Visible(unittest.TestCase):
 def test_decimal(self):
  self.assertEqual(aggregate('id,currency,kind,amount\na,RUB,payment,0.10\nb,RUB,payment,0.20\n'), {'RUB':Decimal('0.30')})
 def test_refund(self):
  self.assertEqual(aggregate('id,currency,kind,amount\na,USD,payment,10\nb,USD,refund,3\n'), {'USD':Decimal('7.00')})
