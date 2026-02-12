# Knowledge Pipeline - Agent Guide

> **版本**: 1.1  
> **日期**: 2026-02-12  
> **狀態**: 實作完成（Phase 3 - 整合階段）

---

## 1. 專案概述

Knowledge Pipeline 是連接 **YouTube Transcriber**（上游）與 **Open Notebook**（下游）的獨立處理層。系統自動化以下流程：

1. **發現 (Discovery)**: 掃描 YouTube Transcriber 輸出目錄，識別新增轉錄稿
2. **語意分析 (Semantic Analysis)**: 使用 LLM（目前使用 Google Gemini CLI）提取結構化 metadata
3. **匯入 (Upload)**: 透過 Open Notebook API 建立 Sources 與 Topics
4. **分類 (Classification)**: 依預定義主題路由至對應 Notebook

### 核心價值

將原始轉錄稿轉化為**可搜尋、可分類、可追蹤**的知識庫，支援跨頻道主題搜尋與時效性篩選。

---

## 2. 技術架構

### 2.1 技術棧

- **語言**: Python 3.10+
- **主要依賴**: 
  - `pyyaml>=6.0` - YAML frontmatter 處理
  - `requests>=2.28.0` - Open Notebook API 呼叫
- **外部工具**: Google Gemini CLI (`gemini` 指令)
- **虛擬環境**: `venv/` 目錄

### 2.2 系統架構圖

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Knowledge Pipeline                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐     │
│  │   File          │ ───▶ │   Semantic      │ ───▶ │   Open Notebook │     │
│  │   Discovery     │      │   Analysis      │      │   Uploader      │     │
│  └────────┬────────┘      └────────┬────────┘      └────────┬────────┘     │
│           │                        │                        │              │
│           ▼                        ▼                        ▼              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        State Management                              │   │
│  │  - Frontmatter status tracking  - Idempotency check                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        LLM Provider Layer (抽象層)                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │GeminiCLI    │ │OpenAI API   │ │Gemini API   │ │Local LLM    │   │   │
│  │  │Provider     │ │Provider     │ │Provider     │ │Provider     │   │   │
│  │  │(目前實作)    │ │(預留)       │ │(預留)       │ │(預留)       │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 資料流向

```
YouTube Transcriber Output
│
▼
┌─────────────────┐
│ File Discovery  │  Parse frontmatter → Check status
│                 │  Filter: word_count >= 100
└────────┬────────┘
         │  List[TranscriptFile]
▼
┌─────────────────┐
│ Semantic        │  TranscriptFile -> TranscriptInput
│ Analysis        │  Call LLM via LLMClient -> LLMProvider
│ (Analyzer)      │  Extract: summary, topics, entities, segments
└────────┬────────┘
         │  AnalyzedMarkdown
▼
┌─────────────────┐
│ Open Notebook   │  POST /api/sources/json
│ Uploader        │  PUT /api/sources/{id} (topics)
└────────┬────────┘
         │  Update frontmatter: status=uploaded, source_id=xxx
▼
┌─────────────────┐
│ State Update    │  Move file: pending/ → approved/
└─────────────────┘
```

---

## 3. 目錄結構

```
knowledge-pipeline/
├── src/                          # 原始碼
│   ├── __init__.py
│   ├── main.py                   # CLI 入口與流程整合
│   ├── config.py                 # 配置管理 (ConfigLoader, ConfigValidator)
│   ├── models.py                 # 資料模型 (TranscriptFile, AnalysisResult)
│   ├── discovery.py              # 檔案發現 (DiscoveryService)
│   ├── analyzer.py               # 語意分析 (AnalyzerService)
│   ├── uploader.py               # API 上傳 (OpenNotebookClient)
│   ├── state.py                  # 狀態管理 (StateManager)
│   └── llm/                      # LLM Provider 抽象層
│       ├── __init__.py
│       ├── client.py             # LLMClient 工廠
│       ├── models.py             # TranscriptInput, AnalysisResult, Segment
│       ├── exceptions.py         # LLMError, LLMCallError 等
│       ├── gemini_cli.py         # Gemini CLI Provider
│       └── prompts.py            # PromptLoader, OutputParser
│
├── config/                       # 配置檔案
│   ├── config.yaml               # 主要配置（需手動建立）
│   ├── config.yaml.example       # 配置範例
│   ├── topics.yaml               # 主題對應（需手動建立）
│   └── topics.yaml.example       # 主題配置範例
│
├── prompts/                      # LLM Prompt 模板
│   └── analysis/
│       ├── default.md            # 通用分析模板
│       ├── crypto_tech.md        # 加密貨幣/技術類
│       ├── ufo_research.md       # UFO 研究類
│       ├── spiritual.md          # 靈性成長類
│       └── remote_viewing.md     # 遙視預測類
│
├── intermediate/                 # 中間態檔案
│   ├── pending/                  # 待審查
│   ├── approved/                 # 已核准（上傳成功）
│   └── rejected/                 # 已拒絕
│
├── logs/                         # 執行日誌
├── temp/                         # 臨時檔案（Gemini CLI 使用）
│
├── docs/                         # 文件
│   ├── PRD.md                    # 產品需求文件
│   ├── architecture.md           # 系統架構文件
│   ├── modules.md                # 開發順序與檢核表
│   └── interfaces/               # 介面定義（契約）
│       ├── models.py
│       ├── config.py
│       ├── discovery.py
│       ├── analyzer.py
│       ├── uploader.py
│       ├── state.py
│       ├── llm.py
│       └── tests/                # 驗收測試
│
├── run.py                        # 入口腳本
├── requirements.txt              # Python 依賴
├── IMPLEMENTATION_REPORT.md      # 實作完成報告
└── README.md                     # 使用者手冊
```

---

## 4. 開發規範

### 4.1 程式碼風格

- **語言**: 文件與註解使用**繁體中文**，程式碼使用**英文**
- **型別註解**: 強制使用 Python type hints
- **Docstring**: 使用 Google Style docstrings
- **字串引號**: 優先使用雙引號 `"`
- **行長限制**: 100 字元

### 4.2 命名規範

| 類型 | 規範 | 範例 |
|------|------|------|
| 類別 | PascalCase | `AnalyzerService`, `TranscriptFile` |
| 函數/方法 | snake_case | `analyze()`, `load_config()` |
| 常數 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| 模組 | snake_case | `discovery.py`, `uploader.py` |
| 私有方法 | 前綴底線 | `_slugify()`, `_prepare_temp_file()` |

### 4.3 錯誤處理

- 每個模組定義專屬 Exception 類別
- 使用例外鏈 (`raise ... from e`) 保留原始錯誤資訊
- 區分可重試錯誤與不可重試錯誤

```python
# 錯誤類別範例
class AnalyzerError(Exception):
    """Analyzer 模組錯誤基類"""
    pass

class AnalysisFailedError(AnalyzerError):
    """分析失敗"""
    def __init__(self, message: str, transcript_path: Path | None = None):
        super().__init__(message)
        self.transcript_path = transcript_path
```

---

## 5. 建置與執行

### 5.1 環境準備

```bash
# 進入專案目錄
cd /home/openclaw/Projects/knowledge-pipeline

# 啟動虛擬環境
source venv/bin/activate

# 安裝依賴（若尚未安裝）
pip install -r requirements.txt
```

### 5.2 配置設定

```bash
# 複製配置範例
cp config/config.yaml.example config/config.yaml
cp config/topics.yaml.example config/topics.yaml

# 編輯 config.yaml 設定路徑和 API 密碼
# 編輯 topics.yaml 設定主題對應
```

### 5.3 CLI 命令

```bash
# 執行完整流程
python run.py run

# 僅執行發現階段
python run.py discover

# 僅執行分析階段（使用特定模板）
python run.py analyze --template crypto_tech

# 僅執行上傳階段
python run.py upload

# 測試模式（不上傳）
python run.py run --dry-run

# 只處理特定頻道
python run.py run --channel "Bankless"

# 詳細輸出模式
python run.py -v run
```

---

## 6. 測試策略

### 6.1 測試結構

測試檔案位於 `docs/interfaces/tests/`，每個模組對應一個測試檔：

```
docs/interfaces/tests/
├── test_models.py       # Models 模組驗收測試
├── test_config.py       # Config 模組驗收測試
├── test_discovery.py    # Discovery 模組驗收測試
├── test_state.py        # State 模組驗收測試
├── test_llm.py          # LLM 模組驗收測試
├── test_analyzer.py     # Analyzer 模組驗收測試
└── test_uploader.py     # Uploader 模組驗收測試
```

### 6.2 執行測試

```bash
# 單一模組測試
python docs/interfaces/tests/test_models.py

# 使用 pytest
python -m pytest docs/interfaces/tests/test_models.py -v

# 全部測試
python -m pytest docs/interfaces/tests/ -v
```

### 6.3 驗證工具

```bash
# 基礎介面合規性檢查
python check_implementation.py

# 深入技術規範檢查
python detailed_review.py
```

---

## 7. 開發順序

請**嚴格按照以下順序**開發，避免循環依賴：

| 順序 | 模組 | 檔案 | 說明 |
|------|------|------|------|
| 1 | **Models** | `src/models.py` | 核心資料結構定義 |
| 2 | **Config** | `src/config.py` | 配置載入與驗證 |
| 3 | **Discovery** | `src/discovery.py` | 檔案掃描與過濾 |
| 4 | **State** | `src/state.py` | 狀態管理與檔案操作 |
| 5 | **LLM** | `src/llm/` | LLM Provider 抽象層 |
| 6 | **Analyzer** | `src/analyzer.py` | 語意分析流程編排 |
| 7 | **Uploader** | `src/uploader.py` | Open Notebook API 客戶端 |
| 8 | **Main** | `src/main.py` | CLI 入口與流程整合 |

每個步驟完成後，務必執行對應的驗收測試。

---

## 8. 關鍵實作細節

### 8.1 Gemini CLI 整合

**重要**: Gemini CLI 有沙盒限制，只能存取執行目錄下的檔案。

```python
# 正確做法：複製到 temp/ 並使用相對路徑
with self._temp_transcript_file(input_data) as transcript_path:
    # transcript_path 為 temp/{channel}_{hash}.md
    prompt_content = self.prompt_loader.format(
        template_name=prompt_template,
        input_data=input_data,
        file_path=transcript_path.name  # 只給檔名！
    )
    # 使用 context manager 確保清理
```

**必須使用的選項**:
- `-p, --prompt`: 啟動 headless 模式（否則進入互動模式）
- `-m gemini-2.5-pro`: 指定模型

### 8.2 Open Notebook API 流程

正確的 API 呼叫順序：

```python
# Step 1: 建立 Source（embed=False，避免無 Topics 時建立索引）
source = client.create_source(
    type="text",
    title=f"{channel} | {title} | {published_at}",
    content=markdown_content,
    embed=False
)

# Step 2: 更新 Topics（必須在建立後執行）
client.update_source_topics(source.id, topics=["topic1", "topic2"])

# Step 3: 關聯至 Notebook
client.link_source_to_notebook(notebook_id, source.id)

# Step 4: 觸發嵌入（在 Topics 更新後）
client.trigger_embedding(source.id)
```

**重要**: 建立 Source 時使用 `POST /api/sources/json`（不是 `/api/sources`）。

### 8.3 狀態管理

使用 Markdown frontmatter 進行狀態追蹤，無需獨立 log 檔案：

```yaml
---
# ... 其他欄位 ...
status: "pending"              # pending / approved / uploaded / failed
source_id: "source:xxxxx"      # ON 回傳的 ID
error: ""                      # 失敗時的錯誤訊息
error_code: ""
failed_at: ""
---
```

### 8.4 中間態檔案結構

```
intermediate/
├── pending/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
└── approved/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
```

---

## 9. 配置說明

### 9.1 config/config.yaml

```yaml
version: "1.0"

paths:
  transcriber_output: "/path/to/youtube_transcriber/output"
  intermediate: "./intermediate"

open_notebook:
  base_url: "http://localhost:5055"
  password: ""  # 或透過 OPEN_NOTEBOOK_PASSWORD 環境變數

llm:
  provider: "gemini_cli"
  project_dir: "/path/to/knowledge-pipeline"
  timeout: 120
  max_retries: 3

batch:
  max_concurrent: 3
  retry_attempts: 3
  retry_delay: 5

logging:
  level: "INFO"
  format: "console"
```

### 9.2 config/topics.yaml

```yaml
version: "1.0"

topics:
  crypto:
    name: "Crypto"
    description: "加密貨幣分析"
    notebook: "Crypto-Analysis"
    prompt_template: "crypto_tech"
    channels:
      - "Benjamin Cowen"
      - "Coin Bureau"
      - "Bankless"

channels:
  "Benjamin Cowen":
    default_topic: "crypto"
```

---

## 10. 安全考量

1. **API 金鑰管理**: 使用環境變數（`OPEN_NOTEBOOK_PASSWORD`），不硬編碼
2. **Gemini 沙盒**: 使用 `-p` flag 啟動 headless 模式
3. **臨時檔案**: 使用 `try...finally` 或 context manager 確保清理
4. **錯誤日誌**: 不記錄敏感資訊（API key、密碼）

---

## 11. 參考文件

| 文件 | 說明 |
|------|------|
| `docs/PRD.md` | 產品需求文件（完整規格） |
| `docs/architecture.md` | 系統架構與資料流 |
| `docs/modules.md` | 開發順序與檢核表 |
| `docs/interfaces/*.py` | 各模組介面定義（必須遵循） |
| `docs/interfaces/tests/*.py` | 驗收測試 |
| `IMPLEMENTATION_REPORT.md` | 實作完成報告 |
| `README.md` | 使用者手冊 |

---

## 12. 上游與下游系統

### 12.1 上游：YouTube Transcriber

- **位置**: `~/.openclaw/workspace/youtube_transcriber/`
- **輸出格式**: Markdown 含 YAML frontmatter
- **輸出路徑**: `{transcriber_output}/{channel}/{YYYY-MM}/{filename}.md`
- **欄位**: channel, video_id, title, published_at, duration, word_count

### 12.2 下游：Open Notebook

- **Base URL**: `http://localhost:5055`
- **認證**: `Authorization: Bearer <password>`
- **API 文件**: `http://localhost:5055/docs`

---

*本文件由 AI Agent 根據專案實際內容更新*
