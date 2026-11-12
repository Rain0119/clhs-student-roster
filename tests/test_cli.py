import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pdf_fixture import text_pdf


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'students.json'
        self.rows = [{'student_id': '001234', 'name': '王o明', 'class': '209', 'seat': 1},
                     {'student_id': '001235', 'name': '李O安', 'class': '309', 'seat': 2}]
        self.data.write_text(json.dumps(self.rows, ensure_ascii=False), encoding='utf-8')

    def run_cli(self, *args, input_text=''):
        env = {**os.environ, 'PYTHONUTF8': '1'}
        return subprocess.run([sys.executable, '-m', 'student_roster', *map(str, args)],
                              input=input_text, capture_output=True, encoding='utf-8', env=env)

    def test_lookup_outputs_only_four_fields(self):
        result = self.run_cli('lookup', 's001234@student.clhs.tyc.edu.tw', '--data', self.data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.rows[0])

    def test_unknown_id_has_clear_error_without_traceback(self):
        result = self.run_cli('lookup', '999999', '--data', self.data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('查無學號', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_list_filters_class(self):
        result = self.run_cli('list', '--class', '209', '--data', self.data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.rows[:1])

    def test_preview_does_not_write_and_yes_confirms_export(self):
        output = self.root / 'class.json'
        result = self.run_cli('list', '--data', self.data, '--output', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(output.exists())
        result = self.run_cli('list', '--class', '209', '--data', self.data, '--output', output, '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), self.rows[:1])

    def test_export_cannot_overwrite_its_input_even_with_flags(self):
        before = self.data.read_bytes()
        result = self.run_cli('list', '--data', self.data, '--output', self.data, '--yes', '--overwrite')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.data.read_bytes(), before)

    def test_invalid_pdf_never_creates_output(self):
        path = self.root / 'bad.pdf'
        path.write_bytes(b'bad pdf')
        output = self.root / 'students-out.json'
        result = self.run_cli('convert', '--source', 'grade2', path, '--output', output, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn('無法讀取 PDF', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_real_pdf_preview_and_conversion(self):
        source = self.root / 'sample.pdf'
        source.write_bytes(text_pdf(['001234 WangO 209 1 B', '001235 LeeO 209 2 B']))
        output = self.root / 'converted.json'
        preview = self.run_cli('convert', '--source', 'grade2', source, '--output', output)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('2 筆', preview.stdout)
        self.assertFalse(output.exists())
        result = self.run_cli('convert', '--source', 'grade2', source, '--output', output, '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {'student_id': '001234', 'name': 'WangO', 'class': '209', 'seat': 1})

    def test_failed_pdf_reports_problem_and_does_not_write_partial_roster(self):
        source = self.root / 'partial.pdf'
        source.write_bytes(text_pdf(['001234 WangO 209 1 B', '001235 209 2 B']))
        output, report = self.root / 'converted.json', self.root / 'report.json'
        result = self.run_cli('convert', '--source', 'grade2', source, '--output', output, '--report', report, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        summary = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(summary['sources'][0]['total'], 1)
        self.assertTrue(summary['issues'])
        self.assertIn('第 1 頁第 2 行', summary['issues'][0])

    def test_multiple_sources_are_checked_for_duplicate_ids(self):
        first, second = self.root / 'first.pdf', self.root / 'second.pdf'
        first.write_bytes(text_pdf(['001234 WangO 209 1 B']))
        second.write_bytes(text_pdf(['001234 WangO 209 1 B']))
        output = self.root / 'merged.json'
        result = self.run_cli('convert', '--source', 'grade2', first, '--source', 'grade3', second, '--output', output, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('重複學號', result.stderr)
        self.assertFalse(output.exists())

    def test_explicit_name_correction_file_is_reproducible(self):
        source = self.root / 'missing.pdf'
        source.write_bytes(text_pdf(['310481 215 41 C']))
        corrections = self.root / 'corrections.json'
        corrections.write_text(json.dumps({'310481': '魏OO'}, ensure_ascii=False), encoding='utf-8')
        output, report = self.root / 'corrected.json', self.root / 'audit.json'
        result = self.run_cli('convert', '--source', 'grade3', source, '--name-overrides', corrections,
                              '--output', output, '--report', report, '--yes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))[0]['name'], '魏OO')
        self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['sources'][0]['name_corrections'][0]['name'], '魏OO')

    def test_unknown_correction_id_blocks_export(self):
        source = self.root / 'sample.pdf'
        source.write_bytes(text_pdf(['001234 WangO 209 1 B']))
        corrections = self.root / 'corrections.json'
        corrections.write_text('{"999999": "WangO"}', encoding='utf-8')
        output = self.root / 'out.json'
        result = self.run_cli('convert', '--source', 'grade2', source, '--name-overrides', corrections, '--output', output, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('未套用', result.stderr)
        self.assertFalse(output.exists())

    def test_report_output_path_conflict_is_rejected_before_writing(self):
        source = self.root / 'sample.pdf'
        source.write_bytes(text_pdf(['001234 WangO 209 1 B']))
        output = self.root / 'both.json'
        result = self.run_cli('convert', '--source', 'grade2', source, '--output', output, '--report', output, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('相同輸出路徑', result.stderr)
        self.assertFalse(output.exists())

    def test_overwrite_requires_its_own_flag(self):
        output = self.root / 'class.json'
        output.write_text('original', encoding='utf-8')
        result = self.run_cli('list', '--data', self.data, '--output', output, '--yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(encoding='utf-8'), 'original')
        result = self.run_cli('list', '--data', self.data, '--output', output, '--yes', '--overwrite')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_class_is_not_treated_as_empty_list(self):
        result = self.run_cli('list', '--class', '20', '--data', self.data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('班級', result.stderr)


if __name__ == '__main__':
    unittest.main()
