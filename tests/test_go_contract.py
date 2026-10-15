"""Qualify the Go acceptance suite with a reference and intentional defects."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class GoContractTests(unittest.TestCase):
    def test_generated_fixtures_match_checked_in_files(self):
        import fixtures
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixtures.build(root)
            for path in root.rglob('*'):
                if path.is_file():
                    self.assertEqual(path.read_bytes(),(ROOT/path.relative_to(root)).read_bytes(),str(path.relative_to(root)))

    def test_reference_passes_and_semantic_mutants_fail(self):
        reference=(ROOT/'oracle/records.go').read_text()
        variants={'reference':reference,
                  'normalizes_id':reference.replace('if !seen[rec.ID]', 'rec.ID = strings.TrimSpace(rec.ID)\n  if !seen[rec.ID]'),
                  'counts_characters_not_bytes':reference.replace('if len(b)>maxBytes', 'if len([]rune(string(b)))>maxBytes'),
                  'rejects_exact_limit':reference.replace('if len(b)>maxBytes', 'if len(b)>=maxBytes'),
                  'reads_before_rejecting_limit':reference.replace('if maxBytes <= 0 {', 'if maxBytes <= 0 { r.Read(make([]byte, 1));'),
                  'undersized_crlf_buffer':reference.replace('capacity = maxBytes+2', 'capacity = maxBytes+1'),
                  'accepts_zero_limit':reference.replace('if maxBytes <= 0', 'if maxBytes < 0')}
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            shutil.copy2(ROOT/'fixtures/go/go.mod',work/'go.mod')
            shutil.copy2(ROOT/'oracle/acceptance_test.go',work/'acceptance_test.go')
            for name,source in variants.items():
                with self.subTest(variant=name):
                    if name!='reference':self.assertNotEqual(source,reference)
                    (work/'records.go').write_text(source)
                    p=subprocess.run(['go','test','-count=1','./...'],cwd=work,capture_output=True,text=True,timeout=45,env={**os.environ,'GOTOOLCHAIN':'local'})
                    self.assertNotIn('[build failed]',p.stdout+p.stderr)
                    self.assertEqual(p.returncode==0,name=='reference',p.stdout+p.stderr)

if __name__=='__main__':unittest.main()
