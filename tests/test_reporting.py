from pathlib import Path
import unittest
import reporting

ROOT=Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    def test_clean_totals_include_all_attempts_and_do_not_hide_go_failures(self):
        self.assertTrue(callable(getattr(reporting,'summarize',None)), 'summarize missing')
        import json
        rows=[json.loads(x) for x in (ROOT/'datasets/2026-10-15-clean/results.jsonl').read_text().splitlines()]
        result=reporting.summarize(rows)
        self.assertEqual(result['codex']['passes'],15)
        self.assertEqual(result['claude']['passes'],12)
        self.assertAlmostEqual(result['codex']['total_seconds'],956.6570197100227,places=6)
        self.assertAlmostEqual(result['claude']['total_seconds'],677.3952603760117,places=6)

    def test_timeout_and_test_failure_overlap_but_preparation_is_excluded(self):
        self.assertTrue(callable(getattr(reporting,'categories',None)), 'categories missing')
        row={'status':'timeout','passed':False,'errors':['external acceptance tests: error']}
        self.assertEqual(reporting.categories(row),['timeout','tests'])
        self.assertEqual(reporting.categories(dict(row,status='invalid_protocol')),['excluded'])


if __name__=='__main__':unittest.main()
