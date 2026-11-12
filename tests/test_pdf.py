import tempfile
import unittest
from pathlib import Path

from student_roster.models import RosterError
from student_roster.pdf import convert_pdf, parse_pages
from pdf_fixture import text_pdf


class PDFTests(unittest.TestCase):
    def test_grade1_column_order(self):
        result = parse_pages(['報到序號 班級 座號 學號 姓名\n001 109 01 001234 王O明'], 'grade1', source='a.pdf')
        result.require_valid()
        self.assertEqual(result.students, [{'student_id': '001234', 'name': '王O明', 'class': '109', 'seat': 1}])

    def test_optional_extra_columns_and_repeated_header(self):
        result = parse_pages(['學號 姓名 班級 座號 班群 數學\n410001 王o寧 209 01 B 數A',
                              '學號 姓名 班級 座號 班群 數學\n410002 李o安 209 2 B'], 'grade2', source='b.pdf')
        result.require_valid()
        self.assertEqual(len(result.students), 2)
        self.assertEqual([p['students'] for p in result.pages], [1, 1])
        self.assertEqual(result.students[0]['name'], '王o寧')

    def test_grade3_only_promotes_its_profile(self):
        for profile, expected in [('grade2', '209'), ('grade3', '309')]:
            result = parse_pages(['310001 王O明 209 01 A'], profile, source='same-name.pdf')
            result.require_valid()
            self.assertEqual(result.students[0]['class'], expected)

    def test_bad_rows_report_source_page_and_line(self):
        result = parse_pages(['學號 姓名 班級 座號 班群\n410001 王o明 209\n這不是已知說明'], 'grade2', source='bad.pdf')
        self.assertEqual(len(result.issues), 2)
        self.assertIn('bad.pdf', result.issues[0])
        self.assertIn('第 1 頁', result.issues[0])
        self.assertIn('第 2 行', result.issues[0])
        with self.assertRaises(RosterError):
            result.require_valid()

    def test_missing_name_is_not_silently_skipped(self):
        result = parse_pages(['310481 215 41 C'], 'grade3', source='missing.pdf')
        self.assertTrue(result.issues)
        self.assertEqual(result.students, [])

    def test_explicit_name_correction_recovers_image_name_with_audit(self):
        result = parse_pages(['310481 215 41 C'], 'grade3', source='image-name.pdf', name_overrides={'310481': '魏OO'})
        result.require_valid()
        self.assertEqual(result.students, [{'student_id': '310481', 'name': '魏OO', 'class': '315', 'seat': 41}])
        self.assertEqual(result.report()['name_corrections'][0]['student_id'], '310481')
        self.assertEqual(result.report()['name_corrections'][0]['page'], 1)

    def test_invalid_name_correction_is_not_used(self):
        with self.assertRaises(RosterError):
            parse_pages(['310481 215 41 C'], 'grade3', source='x.pdf', name_overrides={'310481': ''})

    def test_two_students_in_one_extracted_line_are_not_swallowed(self):
        result = parse_pages(['410001 王o明 209 1 410002 李o安 209 2 B'], 'grade2', source='joined.pdf')
        with self.assertRaises(RosterError):
            result.require_valid()

    def test_image_only_page_in_otherwise_text_pdf_blocks_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mixed.pdf'
            path.write_bytes(text_pdf(['410001 WangO 209 1 B'], image_page=True))
            result = convert_pdf(path, 'grade2')
            self.assertEqual(len(result.pages), 2)
            with self.assertRaisesRegex(RosterError, '第 2 頁'):
                result.require_valid()

    def test_no_text_and_no_students_fail(self):
        for pages in [[''], ['學號 姓名 班級 座號'], []]:
            with self.subTest(pages=pages):
                result = parse_pages(pages, 'grade2', source='empty.pdf')
                with self.assertRaises(RosterError):
                    result.require_valid()

    def test_blank_page_with_valid_other_page_is_allowed_and_reported(self):
        result = parse_pages(['', '410001 王o明 209 1 B'], 'grade2', source='blank.pdf')
        result.require_valid()
        self.assertEqual(result.pages[0]['students'], 0)

    def test_duplicate_rows_are_traced(self):
        result = parse_pages(['410001 王o明 209 1 B', '410001 王o明 209 1 B'], 'grade2', source='dup.pdf')
        self.assertTrue(any('第 2 頁' in issue and '重複學號' in issue for issue in result.issues))

    def test_wrong_profile_and_invalid_class_fail(self):
        for text, profile in [('001 109 1 001234 王O明', 'grade2'), ('310001 王O明 109 1 C', 'grade3')]:
            self.assertTrue(parse_pages([text], profile, source='bad.pdf').issues)
        with self.assertRaises(RosterError):
            parse_pages(['text'], 'auto', source='x.pdf')

    def test_corrupt_or_missing_pdf_is_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.pdf'
            path.write_bytes(b'not a pdf')
            for candidate in [path, path.with_name('missing.pdf')]:
                with self.subTest(path=candidate), self.assertRaises(RosterError):
                    convert_pdf(candidate, 'grade2')


if __name__ == '__main__':
    unittest.main()
