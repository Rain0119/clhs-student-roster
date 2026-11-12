import json
import unittest
from importlib.resources import files

from student_roster import lookup
from student_roster.storage import load_roster


class BuiltinTests(unittest.TestCase):
    def test_complete_dataset_has_only_four_fields(self):
        rows = load_roster()
        self.assertEqual(len(rows), 2029)
        self.assertTrue(all(set(row) == {'student_id', 'name', 'class', 'seat'} for row in rows))
        self.assertEqual(len({row['student_id'] for row in rows}), 2029)

    def test_builtin_csv_and_json_match_exactly(self):
        data = files('student_roster').joinpath('data/students.csv')
        self.assertEqual(load_roster(str(data)), load_roster())

    def test_target_class_contains_37_students(self):
        rows = [row for row in load_roster() if row['class'] == '209']
        self.assertEqual(len(rows), 37)
        self.assertEqual(rows[0], {'student_id': '410282', 'name': '尤o榕', 'class': '209', 'seat': 1})

    def test_user_confirmed_name_and_grade3_promotion(self):
        self.assertEqual(lookup(load_roster(), '310481'),
                         {'student_id': '310481', 'name': '魏OO', 'class': '315', 'seat': 41})

    def test_source_report_has_all_pages_and_no_errors(self):
        report = json.loads(files('student_roster').joinpath('data/sources.json').read_text(encoding='utf-8'))
        self.assertEqual(report['total'], 2029)
        self.assertEqual(report['issues'], [])
        self.assertEqual([s['total'] for s in report['sources']], [678, 689, 662])
        self.assertEqual([len(s['pages']) for s in report['sources']], [15, 16, 15])
        self.assertEqual(report['sources'][2]['name_corrections'][0]['name'], '魏OO')
        for source in report['sources']:
            self.assertEqual(sum(p['students'] for p in source['pages']), source['total'])
            self.assertEqual(len(source['sha256']), 64)


if __name__ == '__main__':
    unittest.main()
