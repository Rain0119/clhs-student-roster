"""四欄名單載入與需要明確授權的檔案匯出。"""

import csv
import io
import json
from importlib.resources import files
from pathlib import Path

from .models import FIELDS, RosterError, validate_roster


def load_roster(path=None):
    try:
        if path is None:
            records = json.loads(files('student_roster').joinpath('data/students.json').read_text(encoding='utf-8'))
        else:
            path = Path(path)
            if path.suffix.lower() == '.json':
                records = json.loads(path.read_text(encoding='utf-8-sig'))
            elif path.suffix.lower() == '.csv':
                with path.open(encoding='utf-8-sig', newline='') as handle:
                    reader = csv.DictReader(handle)
                    if reader.fieldnames != list(FIELDS):
                        raise RosterError('CSV 表頭必須依序且只含 student_id,name,class,seat。')
                    records = list(reader)
                for row in records:
                    if row.get('seat') is None or not row['seat'].isascii() or not row['seat'].isdigit():
                        raise RosterError('CSV 座號必須是 ASCII 正整數。')
                    row['seat'] = int(row['seat'])
            else:
                raise RosterError('名單檔案只接受 .json 或 .csv。')
        return validate_roster(records)
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise RosterError(f'無法載入名單：{exc}') from exc


def check_destination(path, *, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f'輸出已存在：{path}；請改用新路徑或明確指定 --overwrite。')
    if path.exists() and not path.is_file():
        raise RosterError(f'輸出路徑不是檔案：{path}')
    if not path.parent.is_dir():
        raise RosterError(f'輸出資料夾不存在：{path.parent}')


def write_json(value, path, *, overwrite=False):
    path = Path(path)
    if path.suffix.lower() != '.json':
        raise RosterError('報告檔案必須使用 .json 副檔名。')
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    check_destination(path, overwrite=overwrite)
    with path.open('w' if overwrite else 'x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def export_roster(records, output, *, overwrite=False):
    rows = validate_roster(records)
    path = Path(output)
    if path.suffix.lower() == '.json':
        write_json(rows, path, overwrite=overwrite)
    elif path.suffix.lower() == '.csv':
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        check_destination(path, overwrite=overwrite)
        with path.open('w' if overwrite else 'x', encoding='utf-8-sig', newline='') as handle:
            handle.write(buffer.getvalue())
    else:
        raise RosterError('輸出檔案只接受 .json 或 .csv。')
