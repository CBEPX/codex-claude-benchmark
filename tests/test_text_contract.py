"""Formal text checks are distinct from human quality assessment."""
import copy
import json
from pathlib import Path
import unittest
import engine

ROOT=Path(__file__).resolve().parents[1]

class TextContractTests(unittest.TestCase):
    def test_v2_prose_rejects_structure_and_numeric_defects(self):
        spec=json.loads((ROOT/'oracle/write.json').read_text())
        spec['formal_version']=2
        text=(ROOT/'oracle/write.md').read_text()
        self.assertEqual(engine.validate_prose(text,spec),[])
        variants={
            'hidden_instruction':'<!--\n'+text+'\n-->',
            'heading_in_paragraph':text.replace('## Подготовка','Текст ## Подготовка'),
            'duplicate_section':text+'\n## Остановка\n',
            'unexpected_section':text+'\n## Дополнительно\n',
            'extra_number':text+'\nОжидайте 999 секунд.\n',
            'extra_command':text+'\nnorthctl delete archive\n',
            'modified_command':text.replace('northctl validate input.ndjson','northctl validate input.ndjson --unsafe')}
        for name,value in variants.items():
            with self.subTest(variant=name):self.assertTrue(engine.validate_prose(value,spec))
        # An explicit historical profile retains its old formal checks.
        spec.pop('formal_version')
        self.assertEqual(engine.validate_prose(variants['extra_number'],spec),[])

    def test_search_rejects_wrong_values_sources_types_order_and_count(self):
        spec=json.loads((ROOT/'oracle/search.json').read_text())
        expected=spec['answers']
        self.assertEqual(engine.validate_search(expected,spec),[])
        variants=[]
        for path,value in [('answer','other'),('id',True),('id',1.0)]:
            changed=copy.deepcopy(expected);changed[0][path]=value;variants.append(changed)
        for field,value in [('line',True),('line',4.0),('file','docs/02-archive.md')]:
            changed=copy.deepcopy(expected);changed[0]['evidence'][0][field]=value;variants.append(changed)
        changed=copy.deepcopy(expected);changed[10]['evidence']=[{'file':'docs/01-current.md','line':1}];variants.append(changed)
        variants.extend([list(reversed(expected)),expected[:-1],{},[None]*12])
        for value in variants:
            with self.subTest(answer=value):self.assertTrue(engine.validate_search(value,spec))

if __name__=='__main__':unittest.main()
