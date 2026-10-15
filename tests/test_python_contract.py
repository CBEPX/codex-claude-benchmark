"""Qualify CSV acceptance with the reference and semantic defects."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PythonContractTests(unittest.TestCase):
    def test_reference_passes_and_semantic_mutants_fail(self):
        reference=(ROOT/'oracle/aggregate.py').read_text()
        variants={'reference':reference,
            'fixed_column_order':reference.replace('fields = reader.fieldnames', "fields = reader.fieldnames\n        if fields != ['id', 'currency', 'kind', 'amount']: raise ValueError('order')"),
            'ignores_currency_conflict':reference.replace('record = (currency, kind, amount)', 'record = (kind, amount)'),
            'ignores_amount_conflict':reference.replace('record = (currency, kind, amount)', 'record = (currency, kind)'),
            'compares_unrounded_duplicate':reference.replace('record = (currency, kind, amount)', 'record = (currency, kind, Decimal(raw))'),
            'accepts_unicode_digits':reference.replace('[0-9]',r'\d')}
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            shutil.copy2(ROOT/'oracle/test_acceptance.py',work/'test_acceptance.py')
            for name,source in variants.items():
                with self.subTest(variant=name):
                    if name!='reference':self.assertNotEqual(source,reference)
                    (work/'aggregate.py').write_text(source)
                    shutil.rmtree(work/'__pycache__',ignore_errors=True)
                    p=subprocess.run([sys.executable,'-I','-B','-m','unittest','discover','-v'],cwd=work,capture_output=True,text=True,timeout=15)
                    self.assertIn('Ran 8 tests',p.stderr)
                    self.assertNotIn('SyntaxError',p.stderr)
                    self.assertEqual(p.returncode==0,name=='reference',p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
