import csv
import json
import tempfile
import unittest
from pathlib import Path

from student_roster.models import RosterError
from student_roster.storage import export_roster, load_roster


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [{'student_id': '001234', 'name': '王〇明', 'class': '209', 'seat': 1}]

    def test_json_and_csv_roundtrip_with_only_four_fields(self):
        for suffix in ['json', 'csv']:
            with self.subTest(suffix=suffix):
                path = self.root / f'data.{suffix}'
                export_roster(self.rows, path)
                self.assertEqual(load_roster(path), self.rows)
        csv_path = self.root / 'data.csv'
        self.assertTrue(csv_path.read_bytes().startswith(b'\xef\xbb\xbf'))
        with csv_path.open(encoding='utf-8-sig', newline='') as handle:
            self.assertEqual(next(csv.reader(handle)), ['student_id', 'name', 'class', 'seat'])

    def test_existing_file_is_preserved_without_explicit_overwrite(self):
        path = self.root / 'data.json'
        path.write_text('original', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            export_roster(self.rows, path)
        self.assertEqual(path.read_text(encoding='utf-8'), 'original')
        export_roster(self.rows, path, overwrite=True)
        self.assertEqual(load_roster(path), self.rows)

    def test_validation_happens_before_output_is_created(self):
        path = self.root / 'bad.json'
        with self.assertRaises(RosterError):
            export_roster([*self.rows, *self.rows], path)
        self.assertFalse(path.exists())

    def test_unsupported_output_never_overwrites(self):
        path = self.root / 'original.pdf'
        path.write_bytes(b'original')
        with self.assertRaises(RosterError):
            export_roster(self.rows, path, overwrite=True)
        self.assertEqual(path.read_bytes(), b'original')

    def test_corrupt_json_and_extra_fields_are_rejected(self):
        path = self.root / 'bad.json'
        for contents in ['{', json.dumps([{**self.rows[0], 'group': 'A'}])]:
            path.write_text(contents, encoding='utf-8')
            with self.assertRaises(RosterError):
                load_roster(path)

    def test_csv_duplicate_headers_are_rejected(self):
        path = self.root / 'bad.csv'
        path.write_text('student_id,name,class,seat,seat\n123,王O明,209,1,2\n', encoding='utf-8')
        with self.assertRaises(RosterError):
            load_roster(path)


if __name__ == '__main__':
    unittest.main()
