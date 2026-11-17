"""不依賴 PDF 或雲端服務的資料契約。"""

import re

FIELDS = ('student_id', 'name', 'class', 'seat')


class RosterError(ValueError):
    """可直接呈現給使用者的資料錯誤。"""


def normalize_student(student_id, name, class_code, seat, *, promote=False):
    if not isinstance(student_id, str) or not re.fullmatch(r'[0-9]+', student_id.strip()):
        raise RosterError('學號必須是 ASCII 數字字串。')
    if not isinstance(name, str) or not name.strip() or any(c in name for c in '\r\n\x00'):
        raise RosterError('姓名不得空白或含換行、空字元。')
    if not isinstance(class_code, str) or not re.fullmatch(r'[1-3][0-9]{2}', class_code.strip()):
        raise RosterError('班級必須是 1xx、2xx 或 3xx 的三碼字串。')
    if isinstance(seat, bool) or not isinstance(seat, (int, str)) or not re.fullmatch(r'[0-9]+', str(seat)) or int(seat) <= 0:
        raise RosterError('座號必須是正整數。')
    class_code = class_code.strip()
    if promote:
        if class_code.startswith('2'):
            class_code = '3' + class_code[1:]
        elif not class_code.startswith('3'):
            raise RosterError('高三來源只接受 2xx 或 3xx 班級。')
    name = re.sub(r'[OoＯｏ○◯]', '〇', name.strip())
    return dict(zip(FIELDS, (student_id.strip(), name, class_code, int(seat))))


def validate_roster(records):
    if not isinstance(records, list):
        raise RosterError('名單必須是 JSON 陣列。')
    normalized, ids, seats = [], set(), set()
    for position, row in enumerate(records, 1):
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise RosterError(f'第 {position} 筆必須且只能包含 {", ".join(FIELDS)}。')
        if type(row['seat']) is not int:
            raise RosterError(f'第 {position} 筆的 seat 必須是整數。')
        item = normalize_student(row['student_id'], row['name'], row['class'], row['seat'])
        if item['student_id'] in ids:
            raise RosterError(f'重複學號：{item["student_id"]}。')
        seat_key = (item['class'], item['seat'])
        if seat_key in seats:
            raise RosterError(f'座號衝突：{seat_key[0]} 班 {seat_key[1]} 號。')
        ids.add(item['student_id'])
        seats.add(seat_key)
        normalized.append(item)
    return sorted(normalized, key=lambda row: (row['class'], row['seat'], row['student_id']))


def lookup(records, identity):
    value = identity.strip() if isinstance(identity, str) else ''
    email = re.fullmatch(r's([0-9]+)@student\.clhs\.tyc\.edu\.tw', value)
    if email:
        value = email.group(1)
    elif not re.fullmatch(r'[0-9]+', value):
        raise RosterError('查詢格式錯誤：請輸入完整學號或 s學號@student.clhs.tyc.edu.tw。')
    for row in validate_roster(records):
        if row['student_id'] == value:
            return row
    raise RosterError(f'查無學號：{value}。')
