import json
import re
import unittest
from importlib.resources import files

from student_roster.models import normalize_student
from student_roster.pdf import parse_pages


class NameMaskTests(unittest.TestCase):
    def test_mask_variants_are_normalized_without_changing_identity(self):
        for mask in 'OoＯｏ○◯〇':
            self.assertEqual(normalize_student('001234', f'王{mask}𠮷', '209', 1),
                             {'student_id': '001234', 'name': '王〇𠮷', 'class': '209', 'seat': 1})
        self.assertEqual(normalize_student('310481', '魏OO', '215', 41, promote=True)['name'], '魏〇〇')

    def test_pdf_output_uses_canonical_mask(self):
        result = parse_pages(['410001 王o明 209 1 B'], 'grade2', source='synthetic.pdf')
        self.assertEqual(result.require_valid().students[0]['name'], '王〇明')

    def test_raw_builtin_names_use_only_canonical_mask(self):
        rows = json.loads(files('student_roster').joinpath('data/students.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 2029)
        self.assertTrue(all(not re.search('[OoＯｏ○◯]', r['name']) for r in rows))
        self.assertTrue(all('〇' in r['name'] for r in rows))
