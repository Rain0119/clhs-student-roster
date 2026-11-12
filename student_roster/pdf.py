"""明確指定來源格式的 PDF 轉換與可追查報告。"""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .models import RosterError, normalize_student, validate_roster

PROFILES = ('grade1', 'grade2', 'grade3')
HEADERS = {
    '報到序號 班級 座號 學號 姓名',
    '學號 姓名 班級 座號',
    '學號 姓名 班級 座號 班群',
    '學號 姓名 班級 座號 班群 數學',
    '學號 姓名 班級 座號 選擇班群',
}
GRADE1_ROW = re.compile(r'(?P<serial>[0-9]+)\s+(?P<cls>[0-9]{3})\s+(?P<seat>[0-9]+)\s+(?P<sid>[0-9]+)\s+(?P<name>.+)')
SENIOR_ROW = re.compile(r'(?P<sid>[0-9]+)\s+(?P<name>.+?)\s+(?P<cls>[0-9]{3})\s+(?P<seat>[0-9]+)(?:\s+(?P<extra>.*))?')
MISSING_NAME_ROW = re.compile(r'(?P<sid>[0-9]+)\s+(?P<cls>[0-9]{3})\s+(?P<seat>[0-9]+)(?:\s+(?P<extra>.*))?')
EXTRA_COLUMNS = {
    'grade2': re.compile(r'(?:(?:A|B|C|數理|音)(?: 數[AB])?)?'),
    'grade3': re.compile(r'[ABC]?'),
}


@dataclass
class ConversionResult:
    source: str
    profile: str
    students: list = field(default_factory=list)
    pages: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    name_corrections: list = field(default_factory=list)
    sha256: str = ''

    def require_valid(self):
        if self.issues:
            raise RosterError('\n'.join(self.issues))
        return self

    def report(self):
        return {
            'source': self.source,
            'profile': self.profile,
            'sha256': self.sha256,
            'rule': '2xx → 3xx；3xx 保留' if self.profile == 'grade3' else '保留來源班級',
            'total': len(self.students),
            'classes': dict(sorted(Counter(s['class'] for s in self.students).items())),
            'pages': self.pages,
            'issues': self.issues,
            'name_corrections': self.name_corrections,
        }


def _is_heading(line):
    if line in HEADERS:
        return True
    if re.fullmatch(r'請按Ctrl\+F後輸入學號，即可查詢高[一二三]編班', line):
        return True
    return bool(re.fullmatch(r'按Ctrl\+F 後以報到序號即可查詢班級座號(?:\([0-9]+更新\))?', line))


def parse_pages(pages, profile, *, source, nontext_pages=(), name_overrides=None):
    if profile not in PROFILES:
        raise RosterError(f'來源格式必須明確指定為 {", ".join(PROFILES)}。')
    name_overrides = {} if name_overrides is None else name_overrides
    if not isinstance(name_overrides, dict):
        raise RosterError('姓名修正檔必須是學號對應姓名的 JSON 物件。')
    for sid, name in name_overrides.items():
        normalize_student(sid, name, '101', 1)
    result = ConversionResult(str(source), profile)
    ids, seats = {}, {}
    saw_text = False
    for page_number, text in enumerate(pages, 1):
        summary = {'page': page_number, 'students': 0, 'ignored_lines': 0, 'issues': 0}
        result.pages.append(summary)
        if page_number in nontext_pages:
            result.issues.append(f'{source} 第 {page_number} 頁：頁面包含圖片或圖形，但無可擷取文字；禁止忽略為空白頁。')
            summary['issues'] += 1
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            saw_text = True
            location = f'{source} 第 {page_number} 頁第 {line_number} 行'
            if _is_heading(' '.join(line.split())):
                summary['ignored_lines'] += 1
                continue
            match = (GRADE1_ROW if profile == 'grade1' else SENIOR_ROW).fullmatch(line)
            try:
                missing_name = False
                if not match and profile != 'grade1':
                    fallback = MISSING_NAME_ROW.fullmatch(line)
                    if fallback and fallback['sid'] in name_overrides:
                        match = fallback
                        missing_name = True
                if not match:
                    raise RosterError('無法依指定格式解析，可能缺少必要欄位或格式不符。')
                values = match.groupdict()
                original_name = values.get('name', '')
                if values['sid'] in name_overrides:
                    values['name'] = name_overrides[values['sid']]
                if profile != 'grade1' and not EXTRA_COLUMNS[profile].fullmatch(' '.join((values.get('extra') or '').split())):
                    raise RosterError('額外欄位不符合此來源格式，可能有合併列或欄位錯位。')
                if re.fullmatch(r'[0-9\s]+', values['name']):
                    raise RosterError('姓名欄位疑似缺漏或錯位。')
                student = normalize_student(values['sid'], values['name'], values['cls'], values['seat'], promote=profile == 'grade3')
                sid, seat_key = student['student_id'], (student['class'], student['seat'])
                if sid in ids:
                    raise RosterError(f'重複學號 {sid}；前一筆位於 {ids[sid]}。')
                if seat_key in seats:
                    raise RosterError(f'座號衝突 {seat_key[0]} 班 {seat_key[1]} 號；前一筆位於 {seats[seat_key]}。')
                ids[sid], seats[seat_key] = location, location
                result.students.append(student)
                if student['student_id'] in name_overrides:
                    result.name_corrections.append({
                        'student_id': student['student_id'], 'name': student['name'],
                        'extracted_name': original_name, 'page': page_number, 'line': line_number,
                        'reason': '使用者明確提供；來源姓名無法擷取' if missing_name else '使用者明確指定姓名修正',
                    })
                summary['students'] += 1
            except RosterError as exc:
                result.issues.append(f'{location}：{exc} 原始列：{line}')
                summary['issues'] += 1
    if not saw_text:
        result.issues.append(f'{source}：PDF 無可擷取文字；不支援掃描影像或空白文件。')
    elif not result.students and not result.issues:
        result.issues.append(f'{source}：未找到學生資料。')
    result.students = validate_roster(result.students)
    return result


def convert_pdf(path, profile, *, name_overrides=None):
    import pdfplumber

    path = Path(path)
    try:
        content = path.read_bytes()
        with pdfplumber.open(path) as pdf:
            pages, nontext_pages = [], set()
            for page_number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ''
                if not text.strip() and any(page.objects.values()):
                    nontext_pages.add(page_number)
                pages.append(text)
    except Exception as exc:
        raise RosterError(f'無法讀取 PDF {path.name}：{exc}') from exc
    result = parse_pages(pages, profile, source=path.name, nontext_pages=nontext_pages, name_overrides=name_overrides)
    result.sha256 = hashlib.sha256(content).hexdigest()
    return result
