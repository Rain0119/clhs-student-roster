# 學號查詢與名單轉換工具

下載或 Fork 後，在本機將同格式的編班公告 PDF 轉成學生名單，並以學號查詢姓名、班級、座號。不需要 Google、Neon 或 Vercel 帳號。

本專案與私人「班級投票與表單系統」是兩個獨立 repository。私人系統匯入這裡產生的 JSON；本工具不處理登入、投票或實際填答資料。

## 安裝與查詢

需要 Python 3.10 以上。下載專案後，在專案資料夾開啟終端機：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\student-roster.exe lookup 410001
```

macOS／Linux 的虛擬環境路徑為 `.venv/bin/python` 與 `.venv/bin/student-roster`。以下範例使用已安裝到環境中的 `student-roster` 指令；也可使用 `python -m student_roster` 執行。

```powershell
student-roster lookup 410001
student-roster lookup s410001@student.clhs.tyc.edu.tw
student-roster list --class 209
student-roster lookup 410001 --data "自己的名單.json"
```

查詢只接受完整學號或 `s學號@student.clhs.tyc.edu.tw`。格式錯誤與查無學號會回傳不同錯誤，結束碼為 1。輸入信箱只是一種查詢方式，**不等於已驗證帳號或使用者身分**。

## 四欄資料格式

以下使用虛構範例：

```json
[
  {
    "student_id": "001234",
    "name": "王〇明",
    "class": "209",
    "seat": 1
  }
]
```

- `student_id`：ASCII 數字字串，保留前導零。
- `name`：保留可辨識姓名，不推測完整姓名；遮蔽字元 `O`、`o`、`Ｏ`、`ｏ`、`○`、`◯` 統一為 `〇`（U+3007）。此規則同樣適用於 PDF 轉換、自訂 JSON／CSV 載入及匯出。
- `class`：三碼字串，例如 `209`。
- `seat`：正整數，來源的 `01` 正規化成 `1`。

JSON 為 UTF-8 陣列，CSV 為 UTF-8 BOM，表頭固定為 `student_id,name,class,seat`。兩者都依班級、座號、學號排序；不含報到序號、班群、數學分組或信箱。

可用 Python 模組整合其他本機程式：

```python
from student_roster import lookup
from student_roster.storage import load_roster

student = lookup(load_roster(), "410001")
```

## PDF 轉換與預覽

PDF 必須可擷取文字，並明確指定來源格式；不依檔名自動推定年級。

| 格式 | 來源欄位順序 | 班級規則 |
| --- | --- | --- |
| `grade1` | 報到序號、班級、座號、學號、姓名 | 保留班級，捨棄報到序號 |
| `grade2` | 學號、姓名、班級、座號，後接班群／數學等欄位 | 保留班級，只輸出四欄 |
| `grade3` | 學號、姓名、班級、座號，後接選擇班群等欄位 | 2xx 改為 3xx；已為 3xx 保留 |

先預覽，不指定 `--output` 就不會寫入名單：

```powershell
student-roster convert --source grade2 "自己的高二公告.pdf"
```

預覽會列出逐頁筆數、忽略的表頭／說明列數、問題數、各班筆數與前 8 筆資料。正式輸出包含全部有效資料，不只前 8 筆。

確認後匯出：

```powershell
student-roster convert --source grade2 "自己的高二公告.pdf" --output "自己的名單.json" --yes
student-roster convert --source grade2 "自己的高二公告.pdf" --output "自己的名單.csv" --yes
```

一次合併多份來源並輸出獨立驗證報告：

```powershell
student-roster convert --source grade1 "高一.pdf" --source grade2 "高二.pdf" --source grade3 "高三.pdf" --output "全部名單.json" --report "轉換報告.json" --yes
```

`--report` 是明確指定寫入驗證報告，無論名單驗證成功或失敗都會記錄可取得的結果；報告不是正式名單，可能包含錯誤原始列，請先檢查再分享。

若有缺欄、重複學號、同班同座號衝突、未識別的列或不可擷取文字，會指出來源、頁碼與行號，**禁止匯出整份名單**，不靜默丟棄問題資料。掃描影像、加密／損壞 PDF 與任意其他學校格式不在第一版支援範圍內。

## 匯出單一班級

```powershell
student-roster list --class 209 --output "209.json" --yes
student-roster list --class 209 --output "209.csv" --yes
```

私人投票系統可讀取 `209.json`，再匯入自己的 Neon；不需要本工具的線上服務。

## 確認與覆寫規則

- 沒有 `--output`：只列出或預覽資料，不寫名單。
- 指定 `--output` 但沒有 `--yes`：互動終端會詢問；非互動執行只預覽，不寫名單。
- 輸出已存在：預設失敗，保留原檔。需要重新產生時，明確加入 `--overwrite`，或換個檔名。
- `--yes` 只表示同意匯出；**不代表同意覆寫**。
- 輸入檔與輸出檔不得相同，報告與名單也不得使用同一路徑。
- 輸出資料夾需先存在；工具不刪除任何使用者檔案。

```powershell
student-roster list --class 209 --output "209.json" --yes --overwrite
```

## 內建名單與替換

| 來源 | 筆數 |
| --- | ---: |
| 高一 | 678 |
| 高二 | 689 |
| 高三 | 662 |
| 合計 | 2,029 |

高二 209 班共 37 人。

內建四欄資料位於 `student_roster/data/students.json` 與 `students.csv`。`sources.json` 獨立記錄來源檔名、SHA-256、來源格式、逐頁筆數與班級筆數，學生物件本身不含額外中繼資料。

來源為使用者提供的 `115高一編班公告.pdf`、`115高二編班公告.pdf`、`115高三編班公告.pdf`；高三來源的 2xx 依明確指示轉為 3xx。原始 PDF 留在本機，Git 忽略 `*.pdf`，不隨專案發布。

高三來源第 12 頁的學號 `310481` 姓名為不可擷取的內容，使用者已明確指定為 **魏〇〇**。這筆人工確認值保存在獨立的 `student_roster/data/name-overrides.json`，重建時必須明確傳入；工具不會自動對別人的 PDF 套用此修正。來源報告會記錄修正學號、姓名、來源頁與行號。

在本專案目前的資料夾配置中，完整重建指令為：

```powershell
python -m student_roster convert --source grade1 "../編班公告/115高一編班公告.pdf" --source grade2 "../編班公告/115高二編班公告.pdf" --source grade3 "../編班公告/115高三編班公告.pdf" --name-overrides student_roster/data/name-overrides.json --output student_roster/data/students.json --report student_roster/data/sources.json --yes --overwrite
python -m student_roster list --output student_roster/data/students.csv --yes --overwrite
```

若自己的來源也有需人工確認的姓名，可提供相同格式的 JSON 修正檔，例如 `{"001234": "王〇明"}`，以 `--name-overrides` 明確指定。不存在於此次來源的修正學號會報錯，避免用錯檔案。修正不能用來忽略其他缺欄、合併列、衝突或掃描頁問題。

替換方式：先轉換自己的 PDF 並檢查報告，再用輸出的 JSON／CSV 取代內建同名檔案；或每次以 `--data` 指向自己的名單。修改套件內建資料後，需重新執行 `python -m pip install .`，讓安裝版本取得更新。

## 開發與驗證

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

測試使用標準庫 `unittest` 與程式產生的虛構 PDF，不需要原始學生 PDF。GitHub Actions 設定在 Windows／Linux 的 Python 3.10、3.12 執行測試與封裝；雲端執行結果以該 repository 的 Actions 紀錄為準。
