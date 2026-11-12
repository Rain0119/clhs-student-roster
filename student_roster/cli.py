"""本機預覽、查詢與明確確認匯出的命令列。"""

import argparse
import json
import re
import sys
from collections import Counter
from importlib.resources import files
from pathlib import Path

from . import __version__
from .models import RosterError, lookup, validate_roster
from .storage import check_destination, export_roster, load_roster, write_json


def _export_options(parser):
    parser.add_argument('--output', type=Path, help='匯出 .json 或 .csv；未指定時不寫名單檔')
    parser.add_argument('--yes', action='store_true', help='明確確認預覽後匯出；非互動執行時必須指定')
    parser.add_argument('--overwrite', action='store_true', help='明確允許覆寫既有輸出檔（仍禁止覆寫輸入）')


def build_parser():
    parser = argparse.ArgumentParser(description='學號查詢與名單轉換工具（本機執行）')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    query = commands.add_parser('lookup', help='依完整學號或學校信箱查詢')
    query.add_argument('identity')
    query.add_argument('--data', type=Path, help='自訂 JSON／CSV 名單；預設使用內建資料')
    listing = commands.add_parser('list', help='列出或匯出名單，可依班級篩選')
    listing.add_argument('--data', type=Path)
    listing.add_argument('--class', dest='class_code', help='三碼班級，例如 209')
    _export_options(listing)
    convert = commands.add_parser('convert', help='明確指定格式，轉換一份或多份 PDF')
    convert.add_argument('--source', nargs=2, action='append', required=True, metavar=('PROFILE', 'PDF'), help='grade1／grade2／grade3 與 PDF 路徑；可重複指定')
    convert.add_argument('--report', type=Path, help='獨立 JSON 驗證報告；可記錄轉換錯誤')
    convert.add_argument('--name-overrides', type=Path, help='明確提供學號對應姓名的 JSON 修正檔；不自動猜測')
    _export_options(convert)
    return parser


def _json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _check_paths(inputs, outputs, *, overwrite=False):
    resolved_inputs = {Path(p).resolve() for p in inputs}
    seen = set()
    for path in outputs:
        if path is None:
            continue
        resolved = path.resolve()
        if resolved in resolved_inputs:
            raise RosterError(f'禁止覆寫輸入或內建資料檔：{path}')
        if resolved in seen:
            raise RosterError('名單與報告不得使用相同輸出路徑。')
        seen.add(resolved)
        check_destination(path, overwrite=overwrite)


def _confirm(args):
    if args.yes:
        return True
    if not sys.stdin.isatty():
        print('僅預覽，未寫入名單。確認匯出請加入 --yes。')
        return False
    return input('確認將以上名單匯出？輸入 yes 確認：').strip().lower() == 'yes'


def _preview(rows):
    counts = dict(sorted(Counter(row['class'] for row in rows).items()))
    print(f'有效資料：{len(rows)} 筆')
    print('各班筆數：' + json.dumps(counts, ensure_ascii=False))
    print('預覽前 8 筆（正式輸出包含全部資料）：')
    _json(rows[:8])


def _run_list(args):
    rows = load_roster(args.data)
    if args.class_code:
        if not re.fullmatch(r'[1-3][0-9]{2}', args.class_code):
            raise RosterError('班級必須是 1xx、2xx 或 3xx 的三碼字串。')
        rows = [row for row in rows if row['class'] == args.class_code]
    if args.output is None:
        _json(rows)
        return
    builtin = files('student_roster').joinpath('data/students.json')
    inputs = [args.data] if args.data else [str(builtin)]
    _check_paths(inputs, [args.output], overwrite=args.overwrite)
    _preview(rows)
    if _confirm(args):
        export_roster(rows, args.output, overwrite=args.overwrite)
        print(f'已匯出：{args.output}')


def _run_convert(args):
    from .pdf import PROFILES, convert_pdf

    if args.output and args.output.suffix.lower() not in ('.json', '.csv'):
        raise RosterError('輸出檔案只接受 .json 或 .csv。')
    if args.report and args.report.suffix.lower() != '.json':
        raise RosterError('報告檔案必須使用 .json 副檔名。')
    for profile, _ in args.source:
        if profile not in PROFILES:
            raise RosterError(f'未知來源格式：{profile}；請使用 grade1、grade2 或 grade3。')
    inputs = [path for _, path in args.source]
    name_overrides = None
    if args.name_overrides:
        inputs.append(args.name_overrides)
        try:
            name_overrides = json.loads(args.name_overrides.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RosterError(f'無法載入姓名修正檔：{exc}') from exc
        if not isinstance(name_overrides, dict):
            raise RosterError('姓名修正檔必須是學號對應姓名的 JSON 物件。')
    _check_paths(inputs, [args.output, args.report], overwrite=args.overwrite)
    results, errors = [], []
    for profile, path in args.source:
        try:
            result = convert_pdf(path, profile, name_overrides=name_overrides)
            results.append(result)
            errors.extend(result.issues)
            print(f'{result.source} [{profile}]：{len(result.pages)} 頁，{len(result.students)} 筆，{len(result.issues)} 個問題')
            for page in result.pages:
                print(f'  第 {page["page"]} 頁：{page["students"]} 筆，略過 {page["ignored_lines"]} 行表頭／說明，{page["issues"]} 個問題')
        except RosterError as exc:
            errors.append(str(exc))
    rows = [row for result in results for row in result.students]
    if name_overrides:
        applied = {entry['student_id'] for result in results for entry in result.name_corrections}
        unused = set(name_overrides) - applied
        if unused:
            errors.append('姓名修正檔有未套用的學號，請核對來源或修正檔：' + ', '.join(sorted(unused)))
    try:
        rows = validate_roster(rows)
    except RosterError as exc:
        errors.append(f'合併來源驗證失敗：{exc}')
    report = {'schema_version': 1, 'sources': [result.report() for result in results], 'total': len(rows), 'issues': errors}
    if args.report:
        write_json(report, args.report, overwrite=args.overwrite)
        print(f'已寫入驗證報告：{args.report}')
    if errors:
        raise RosterError('驗證失敗，禁止匯出名單：\n' + '\n'.join(errors))
    _preview(rows)
    if args.output and _confirm(args):
        export_roster(rows, args.output, overwrite=args.overwrite)
        print(f'已匯出：{args.output}')


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(argv)
    try:
        if args.command == 'lookup':
            _json(lookup(load_roster(args.data), args.identity))
        elif args.command == 'list':
            _run_list(args)
        else:
            _run_convert(args)
        return 0
    except (RosterError, OSError, UnicodeError) as exc:
        print(f'錯誤：{exc}', file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('已取消操作。', file=sys.stderr)
        return 130
