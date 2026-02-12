# Knowledge Pipeline - 使用手冊

> 自動化 YouTube 轉錄稿分析與 Open Notebook 上傳工具

---

## 📖 目錄

- [快速開始](#快速開始)
- [CLI 命令參考](#cli-命令參考)
- [工作流程](#工作流程)
- [常見問題](#常見問題)

---

## 快速開始

### 1. 環境準備

```bash
# 進入專案目錄
cd /home/openclaw/Projects/knowledge-pipeline

# 啟動虛擬環境
source venv/bin/activate
```

### 2. 基本指令

```bash
# 查看所有可用命令
python run.py --help

# 測試模式（推薦先用這個）
python run.py run --channel "Bankless" --dry-run

# 正式執行
python run.py run --channel "Bankless"
```

---

## CLI 命令參考

### 主命令結構

```bash
python run.py [全域選項] <子命令> [子命令選項]
```

### 全域選項

| 選項 | 說明 | 範例 |
|-----|------|------|
| `-c, --config` | 指定配置文件 | `--config config/config.yaml` |
| `-v, --verbose` | 詳細輸出模式 | `-v` |

### 子命令

#### `run` - 執行完整流程

發現 → 分析 → 上傳（一次完成）

```bash
# 基本用法
python run.py run

# 測試模式（不上傳）
python run.py run --dry-run

# 只處理特定頻道
python run.py run --channel "Ross Coulthart"

# 使用特定 prompt 模板
python run.py run --template crypto_tech

# 組合使用
python run.py run --channel "Bankless" --dry-run -v
```

**選項：**

| 選項 | 說明 | 預設值 |
|-----|------|--------|
| `--dry-run` | 測試模式，不上傳 | 無 |
| `--channel` | 只處理指定頻道 | 全部頻道 |
| `-t, --template` | Prompt 模板名稱 | `default` |

---

#### `discover` - 只執行發現階段

掃描轉錄檔案，不分析不上傳

```bash
# 基本用法
python run.py discover

# 只掃描特定頻道
python run.py discover --channel "Ashton Forbes"

# 設定最小字數限制
python run.py discover --min-words 500
```

**選項：**

| 選項 | 說明 | 預設值 |
|-----|------|--------|
| `--min-words` | 最小字數限制 | 100 |
| `--channel` | 只掃描指定頻道 | 全部 |

---

#### `analyze` - 只執行分析階段

對 pending 檔案進行 AI 分析

```bash
# 基本用法
python run.py analyze

# 使用特定模板
python run.py analyze --template ufo_research
```

**選項：**

| 選項 | 說明 | 預設值 |
|-----|------|--------|
| `-t, --template` | Prompt 模板名稱 | `default` |

---

#### `upload` - 只執行上傳階段

上傳已分析的檔案到 Open Notebook

```bash
# 基本用法
python run.py upload

# 測試模式
python run.py upload --dry-run
```

**選項：**

| 選項 | 說明 | 預設值 |
|-----|------|--------|
| `--dry-run` | 測試模式，不上傳 | 無 |

---

## 工作流程

### 1. 開發/測試流程（推薦）

適合初次使用或想檢查 AI 分析品質時：

```bash
# Step 1: 測試模式執行（產生 pending 檔案供檢查）
python run.py run --channel "Ross Coulthart" --dry-run

# Step 2: 檢查產生的檔案
ls intermediate/pending/Ross\ Coulthart/2026-02/

# Step 3: 查看內容
cat intermediate/pending/Ross\ Coulthart/2026-02/xxx_analyzed.md

# Step 4: 滿意後，正式上傳
python run.py run --channel "Ross Coulthart"
```

### 2. 全自動流程

適合日常自動化運作：

```bash
# 處理全部頻道
python run.py run

# 或處理特定主題的所有頻道
python run.py run --channel "Bankless"
python run.py run --channel "Benjamin Cowen"
```

### 3. 分階段執行

適合需要人工介入或排程的情境：

```bash
# 階段 1: 發現
python run.py discover --channel "Bankless"

# 階段 2: 分析（可在此檢查結果）
python run.py analyze

# 階段 3: 上傳
python run.py upload
```

---

## 常見問題

### Q1: 頻道名稱怎麼打？

**必須使用 frontmatter 中的頻道名稱**（有空格）：

| ❌ 錯誤 | ✅ 正確 |
|--------|--------|
| `Ross_Coulthart` | `"Ross Coulthart"` |
| `Bankless` | `"Bankless"`（這個剛好沒空格） |
| `Benjamin_Cowen` | `"Benjamin Cowen"` |

**查看可用頻道：**
```bash
ls /home/openclaw/.openclaw/workspace/youtube_transcriber/output/
```

### Q2: 有哪些 prompt 模板可用？

```bash
ls prompts/analysis/
```

目前可用的模板：
- `default.md` - 通用模板
- `crypto_tech.md` - 加密貨幣/技術類
- `ufo_research.md` - UFO 研究類
- `spiritual.md` - 靈性成長類

### Q3: 檔案會放在哪裡？

```
intermediate/
├── pending/{頻道}/{年月}/     # 分析完成，等待上傳
└── approved/{頻道}/{年月}/    # 上傳成功
```

### Q4: 如何調整 timeout？

編輯 `config/config.yaml`：

```yaml
llm:
  timeout: 120        # 單位：秒，預設 120
  max_retries: 3      # 失敗重試次數
```

### Q5: 如何只處理最新的影片？

目前系統會自動跳過已處理的檔案（依 status 欄位）。若要強制重新處理，需先刪除 `intermediate/pending/` 中的對應檔案。

### Q6: 如何查看執行日誌？

```bash
# 即時查看
ls logs/

# 查看最新日誌
tail -f logs/pipeline-$(date +%Y-%m-%d).log
```

### Q7: 為什麼有些檔案被跳過？

常見原因：
1. **已處理過** - status 為 uploaded/pending
2. **字數不足** - 少於 `min_word_count` 設定
3. **頻道限制** - 使用了 `--channel` 篩選
4. **解析失敗** - frontmatter 格式錯誤

執行時加上 `-v` 可查看詳細原因。

---

## 完整頻道列表

| 頻道名稱 | 主題分類 |
|---------|---------|
| Ross Coulthart | UFO Phenomena |
| Ashton Forbes | UFO Phenomena |
| Richard Dolan Intelligent Disclosure | UFO Phenomena |
| The Good Trouble Show | UFO Phenomena |
| Sol Foundation | UFO Phenomena |
| Benjamin Cowen | Crypto |
| Coin Bureau | Crypto |
| Bankless | Crypto |
| Just Dario | Macro Finance |
| Trade Talk | Macro Finance |
| Conquer Trading Investing | Macro Finance |
| Real Vision | Macro Finance |
| Your Monk Haku | Spiritual Growth |
| Paul Selig | Spiritual Growth |
| Lee Harris Energy | Spiritual Growth |
| Eckhart Tolle | Spiritual Growth |
| Christina Lopes | Spiritual Growth |
| Future Forecasting Group | Remote Viewing |
| Future Forecasters | Remote Viewing |
| Farsight | Remote Viewing |
| Screaming Into The Night | Remote Viewing |
| Asian Dad Energy | Tech Career |
| Jeff Su | Tech Career |
| The Primeagen | Tech Career |

---

## 系統需求

- Python 3.10+
- Google Gemini CLI（已安裝）
- Open Notebook（本地運行於 localhost:5055）

---

## 相關文件

- `AGENTS.md` - 開發者指南
- `docs/PRD.md` - 產品需求文件
- `docs/architecture.md` - 系統架構說明
- `config/config.yaml` - 系統設定
- `config/topics.yaml` - 主題分類設定

---

**最後更新**: 2026-02-12
