# 學號查詢與名單轉換工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 交付可下載、本機執行的 PDF 四欄名單轉換與學號查詢工具，附三個年級的內建名單。

**Architecture:** Python 套件分離資料驗證、PDF 擷取、匯出與命令列。內建 JSON 隨套件提供；同一資料契約供私人系統匯入 Neon，公開工具無雲端依賴。

**Tech Stack:** Python 3.10+、pdfplumber 0.11.9、標準庫 argparse／unittest／csv／json、setuptools。

## Global Constraints

- 每筆資料僅含 `student_id`（字串）、`name`（字串）、`class`（字串）、`seat`（正整數）。
- 姓名維持原始遮蔽形式，學號保留前導零。
- 高三指定來源的 2xx 轉成 3xx；不得依檔名自動推定來源。
- 原始 PDF 不變更、不加入 Git；不刪除使用者檔案。
- 先預覽與驗證，再明確確認匯出；已存在輸出須另外明確授權覆寫。
- 有缺欄、非法值、重複學號、同班同座號衝突、不可解析列時禁止匯出。
- 公開與私人系統使用獨立 repository；本次只實作公開工具。

## 檔案分工

- `student_roster/models.py`：四欄驗證、排序、衝突偵測與學號／信箱查詢。
- `student_roster/pdf.py`：三種明確格式的跨頁 PDF 擷取、來源行號與逐頁報告。
- `student_roster/storage.py`：內建資料載入、安全 JSON／CSV 匯出。
- `student_roster/cli.py`、`__main__.py`、`__init__.py`：命令列及公開函式。
- `student_roster/data/students.json`、`students.csv`、`sources.json`：內建四欄名單及獨立來源報告。
- `student_roster/data/name-overrides.json`：使用者明確提供的 `310481` → `魏OO`；透過 `--name-overrides PATH` 才套用並留下報告。
- `tests/test_models.py`、`test_pdf.py`、`test_storage.py`、`test_cli.py`：有意義的資料契約及實際命令列測試。
- `pyproject.toml`、`README.md`、`.gitignore`：安裝、使用及公開邊界。

### Task 1: 資料契約與精確查詢

**Interfaces:** `normalize_student(student_id, name, class_code, seat, *, promote=False) -> dict`；`validate_roster(records) -> list[dict]`；`lookup(records, identity) -> dict`；例外 `RosterError(ValueError)`。

- [x] 先測前導零、姓名大小寫遮蔽、班級修正、非法值與衝突，執行 `python -m unittest discover -s tests -p test_models.py -v`，觀察缺少模組的失敗。
- [x] 實作上述介面；學號限 ASCII 數字、班級限三碼且年級為 1–3、座號正整數。查詢僅接受完整學號或 `s[0-9]+@student.clhs.tyc.edu.tw`。
- [x] 重跑同指令通過；檢查輸出物件鍵嚴格等於四欄。

```python
self.assertEqual(normalize_student('001234', ' 王o明 ', '209', '01', promote=True),
                 {'student_id': '001234', 'name': '王o明', 'class': '309', 'seat': 1})
with self.assertRaises(RosterError):
    validate_roster([row, row])
```

### Task 2: PDF 擷取與來源驗證

**Interfaces:** `parse_pages(pages: list[str], profile: str, *, source: str) -> ConversionResult`；`convert_pdf(path, profile) -> ConversionResult`。結果包含 `students`、`pages`、`issues`、`source`、`profile`；`require_valid()` 有問題即拋錯。

- [x] 寫高一重排欄位、高二可缺額外選科欄、高三轉班、跨頁重複表頭、缺欄、錯格式、未知說明列、無文字與衝突測試，先確認失敗。
- [x] 只忽略明確公告說明與指定欄位表頭；任何其他非空列都解析或報錯。逐頁記錄筆數與忽略列數，逐筆記錄來源頁／行以追查衝突。
- [x] 使用 pdfplumber 讀取全部頁面；損壞、加密、無文字不建立正式名單。
- [x] `python -m unittest discover -s tests -p test_pdf.py -v` 通過後，實跑三份原始 PDF；比較筆數、跨頁樣本與 209 班。

```python
result = parse_pages(['學號 姓名 班級 座號 班群 數學\n410001 王o寧 209 01 B'], 'grade2', source='sample.pdf')
self.assertEqual(result.students[0]['class'], '209')
self.assertEqual(result.students[0]['seat'], 1)
```

### Task 3: 安全匯出與命令列

**Interfaces:** `load_roster(path=None) -> list[dict]`；`export_roster(records, output, *, overwrite=False)`；`main(argv=None) -> int`。支援 `lookup`、`list`、`convert`。

- [x] 先測 JSON／CSV 四欄往返、BOM、拒絕覆寫、CLI 查詢、篩班、預覽不寫檔、有錯不寫檔、取消匯出與非互動明確確認。
- [x] `lookup ID [--data PATH]`；`list [--class CLASS] [--data PATH] [--output PATH]`；`convert --source grade1 PATH [--source grade2 PATH] [--source grade3 PATH] [--output PATH] [--report PATH]`。
- [x] `--yes` 是預覽後匯出的明確確認；既有輸出另需 `--overwrite`。若未帶 `--yes` 且可互動，提示確認；非互動不寫正式檔。未指定 `--output` 時僅預覽。JSON／CSV 依副檔名選擇。
- [x] 目的檔先以排他建立保護新檔；覆寫僅在明確旗標存在時允許。不自動刪檔。所有輸入 PDF、資料檔與輸出／報告路徑禁止互相覆寫。
- [x] `python -m unittest discover -s tests -v` 通過；執行真實 PDF 轉換、查詢及座號列表命令。

```python
with self.assertRaises(FileExistsError):
    export_roster([row], existing_path)
self.assertEqual(json.loads(json_path.read_text(encoding='utf-8')), [row])
```

### Task 4: 內建資料、文件與交付

- [x] 三份原始 PDF 全部解析並驗證，產生合併 `students.json`、同內容 CSV，以及只含來源摘要的 `sources.json`；報告記錄來源 SHA-256、逐頁筆數、班級筆數與來源修正規則。
- [x] README 提供 Windows PowerShell 與通用命令、來源格式、四欄契約、個別／合併轉換、209 班匯出、覆寫規則及限制；說明查詢不等於身分驗證。
- [x] 套件安裝配置內含內建 JSON。加入 GitHub Actions 在 Python 3.10／3.12 上跑完整測試並建立套件；不發布雲端資源。
- [x] 用隔離安裝目錄確認 CLI 可在 repository 外載入內建名單，並檢查 wheel 內容只有公開專案資料。
- [x] 全測試、`git diff --check`、實際 CLI、三份 PDF 對照均完成後提交本機 Git；回報已完成範圍，GitHub 發布與私人系統不在本次交付內。

## 計畫自我檢查

設計中的來源格式、四欄契約、查詢、衝突與錯誤、預覽確認、安全匯出、私人系統介面及離線重建均分配到上述任務。真實 PDF 的完整驗證與套件外部執行分開驗證，不以單元測試替代。依目前對話直接在本機執行此計畫，不另開對話或要求重複批准。
