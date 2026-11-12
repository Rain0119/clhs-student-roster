import unittest

from student_roster.models import RosterError, lookup, normalize_student, validate_roster


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.row = {'student_id': '001234', 'name': '王o明', 'class': '209', 'seat': 1}

    def test_four_fields_and_leading_zero(self):
        self.assertEqual(normalize_student('001234', ' 王o明 ', '209', '01'), self.row)

    def test_grade3_promotion_is_explicit(self):
        self.assertEqual(normalize_student('001234', '王o明', '209', 1, promote=True)['class'], '309')
        self.assertEqual(normalize_student('001234', '王o明', '309', 1, promote=True)['class'], '309')
        with self.assertRaises(RosterError):
            normalize_student('001234', '王o明', '109', 1, promote=True)

    def test_invalid_values(self):
        for sid, name, cls, seat in [('１２３', '王O明', '209', 1), ('123', '', '209', 1),
                                      ('123', '王O明', '20', 1), ('123', '王O明', '409', 1),
                                      ('123', '王O明', '209', 0), ('123', '王O明', '209', True),
                                      ('123', '王O明', '209', 1.5)]:
            with self.subTest(values=(sid, name, cls, seat)), self.assertRaises(RosterError):
                normalize_student(sid, name, cls, seat)

    def test_duplicate_ids_are_rejected(self):
        other = {**self.row, 'class': '309'}
        with self.assertRaisesRegex(RosterError, '重複學號'):
            validate_roster([self.row, other])

    def test_seat_conflicts_are_rejected(self):
        with self.assertRaisesRegex(RosterError, '座號衝突'):
            validate_roster([self.row, {**self.row, 'student_id': '001235'}])

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(RosterError):
            validate_roster([{**self.row, 'group': 'A'}])

    def test_sort_order_and_name_preservation(self):
        other = {'student_id': '002345', 'name': '李O𠮷', 'class': '109', 'seat': 12}
        self.assertEqual(validate_roster([self.row, other]), [other, self.row])

    def test_lookup_id_and_verified_format_email(self):
        for identity in ['001234', ' s001234@student.clhs.tyc.edu.tw ']:
            self.assertEqual(lookup([self.row], identity), self.row)

    def test_invalid_identity_and_missing_id_are_distinct(self):
        for identity in ['s001234@gmail.com', 's001234@student.clhs.tyc.edu.tw.evil', '', '１２３']:
            with self.assertRaisesRegex(RosterError, '格式'):
                lookup([self.row], identity)
        with self.assertRaisesRegex(RosterError, '查無'):
            lookup([self.row], '999999')


if __name__ == '__main__':
    unittest.main()
