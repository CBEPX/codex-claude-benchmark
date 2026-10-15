from pathlib import Path
import tempfile
import unittest
import privacy_check


class PrivacyTests(unittest.TestCase):
    def test_check_rejects_account_data_without_echoing_its_value(self):
        self.assertTrue(callable(getattr(privacy_check,'issues',None)), 'issues missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'datasets/example';p.mkdir(parents=True)
            (p/'events.public.jsonl').write_text('{"type":"init","creator_account_id":"PRIVATE_VALUE"}\n')
            found=privacy_check.issues(root)
            self.assertTrue(found)
            self.assertNotIn('PRIVATE_VALUE',str(found))

    def test_archived_run_artifacts_are_not_ignored_by_git(self):
        import subprocess
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run(['git','check-ignore','--no-index','datasets/2026-10-15-clean/runs/example/work/result.md'],cwd=root,capture_output=True,text=True)
        self.assertEqual(p.returncode,1,p.stdout)


if __name__=='__main__':unittest.main()
