# Knowledge Pipeline - Agent Guide

> **版本**: 1.0  
> **日期**: 2026-02-11  
> **狀態**: Phase 2 - 契約階段（介面已定義，實作進行中）

---

## 專案概述

Knowledge Pipeline 是連接 **YouTube Transcriber**（上游）與 **Open Notebook**（下游）的獨立處理層。系統自動化以下流程：

1. **發現 (Discovery)**: 掃描 YouTube Transcriber 輸出目錄，識別新增轉錄稿
2. **語意分析 (Semantic Analysis)**: 使用 LLM（MVP 使用 Google Gemini CLI）提取結構化 metadata
3. **匯入 (Upload)**: 透過 Open Notebook API 建立 Sources 與 Topics
4. **分類 (Classification)**: 依預定義主題路由至對應 Notebook

### 核心價值

將原始轉錄稿轉化為**可搜尋、可分類、可追蹤**的知識庫，支援跨頻道主題搜尋與時效性篩選。

---

## 技術架構

### 技術棧

- **語言**: Python 3.10+
- **主要依賴**: 
  - `pyyaml` - YAML frontmatter 處理
  - `requests` - Open Notebook API 呼叫
  - `ruamel.yaml` - 保留格式的 YAML 讀寫（建議）
- **外部工具**: Google Gemini CLI (`gemini` 指令)
- **測試框架**: `unittest` / `pytest`

### 系統架構圖

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

---

## 目錄結構

```
knowledge-pipeline/
├── src/                          # 原始碼（尚未實作）
│   ├── __init__.py
│   ├── main.py                   # CLI 入口
│   ├── config.py                 # 配置管理
│   ├── models.py                 # 資料模型
│   ├── discovery.py              # 檔案發現
│   ├── analyzer.py               # 語意分析
│   ├── uploader.py               # API 上傳
│   ├── state.py                  # 狀態管理
│   └── llm/                      # LLM Provider 抽象層
│       ├── __init__.py
│       ├── client.py
│       ├── provider.py
│       └── gemini_cli.py
│
├── config/                       # 配置檔案
│   ├── config.yaml               # 主要配置
│   └── topics.yaml               # 主題對應
│
├── prompts/                      # LLM Prompt 模板
│   └── analysis/
│       ├── default.md
│       ├── crypto_tech.md
│       └── ufo_research.md
│
├── intermediate/                 # 中間態檔案
│   ├── pending/                  # 待審查
│   ├── approved/                 # 已核准
│   └── rejected/                 # 已拒絕
│
├── logs/                         # 執行日誌
│   └── pipeline-{YYYY-MM-DD}.log
│
└── docs/                         # 文件
    ├── PRD.md                    # 產品需求文件
    ├── architecture.md           # 系統架構文件
    ├── modules.md                # 開發順序與檢核表
    └── interfaces/               # 介面定義（契約）
        ├── models.py
        ├── config.py
        ├── discovery.py
        ├── analyzer.py
        ├── uploader.py
        ├── state.py
        ├── llm.py
        └── tests/                # 驗收測試
```

---

## 開發規範

### 程式碼風格

- **語言**: 文件與註解使用繁體中文，程式碼使用英文
- **型別註解**: 強制使用 Python type hints
- **Docstring**: 使用 Google Style docstrings
- **字串引號**: 優先使用雙引號 `"`
- **行長限制**: 100 字元

### 命名規範

| 類型 | 規範 | 範例 |
|------|------|------|
| 類別 | PascalCase | `AnalyzerService`, `TranscriptFile` |
| 函數/方法 | snake_case | `analyze()`, `load_config()` |
| 常數 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| 模組 | snake_case | `discovery.py`, `uploader.py` |
| 私有方法 | 前綴底線 | `_slugify()`, `_prepare_temp_file()` |

### 錯誤處理

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

## 測試策略

### 測試結構

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

### 執行測試

```bash
# 單一模組測試
python docs/interfaces/tests/test_models.py

# 使用 pytest
python -m pytest docs/interfaces/tests/test_models.py -v

# 全部測試
python -m pytest docs/interfaces/tests/ -v
```

### 驗收標準

每個測試檔案包含具體驗收項目，實作完成後需通過所有測試：

1. **test_models.py**: TranscriptMetadata、AnalysisResult、AnalyzedTranscript、Enum 定義
2. **test_config.py**: ConfigLoader、ConfigValidator、TopicResolver、PromptLoader
3. **test_discovery.py**: FileScanner、FrontmatterParser、StatusChecker、DiscoveryService
4. **test_state.py**: FrontmatterReader/Writer、IdempotencyChecker、FileMover、StateManager
5. **test_llm.py**: TranscriptInput、AnalysisResult、LLMProvider、LLMClient、PromptLoader
6. **test_analyzer.py**: AnalyzerService、StructuredSegmentation、輸出格式驗證
7. **test_uploader.py**: OpenNotebookClient、SourceBuilder、UploaderService、錯誤處理

---

## 開發順序

請**嚴格按照以下順序**開發，避免循環依賴：

| 順序 | 模組 | 說明 |
|------|------|------|
| 1 | **Models** (`src/models.py`) | 核心資料結構定義 |
| 2 | **Config** (`src/config.py`) | 配置載入與驗證 |
| 3 | **Discovery** (`src/discovery.py`) | 檔案掃描與過濾 |
| 4 | **State** (`src/state.py`) | 狀態管理與檔案操作 |
| 5 | **LLM** (`src/llm/`) | LLM Provider 抽象層 |
| 6 | **Analyzer** (`src/analyzer.py`) | 語意分析流程編排 |
| 7 | **Uploader** (`src/uploader.py`) | Open Notebook API 客戶端 |
| 8 | **Main** (`src/main.py`) | CLI 入口與流程整合 |

每個步驟完成後，務必執行對應的驗收測試。

---

## 關鍵實作細節

### 1. Gemini CLI 整合

**重要**: Gemini CLI 有沙盒限制，只能存取執行目錄下的檔案。

```python
# 正確做法：複製到 temp/ 並使用相對路徑
temp_input = project_dir / "temp" / f"{channel}_{hash}.md"
shutil.copy2(transcript.path, temp_input)

try:
    result = subprocess.run(
        ["gemini", "-p", prompt, "-o", "json", "--approval-mode", "plan"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(project_dir)  # 關鍵：在 project_dir 執行
    )
finally:
    temp_input.unlink(missing_ok=True)
```

**必須使用的選項**:
- `-p, --prompt`: 啟動 headless 模式（否則進入互動模式）
- `--approval-mode plan`: 唯讀模式（最安全）
- `-o json`: JSON 輸出格式

### 2. Open Notebook API 流程

正確的 API 呼叫順序：

```python
# Step 1: 建立 Source（embed=False，避免無 Topics 時建立索引）
source = client.create_source(
    type="text",
    title=f"{channel} | {title} | {published_at}",
    content=markdown_content,
    embed=False
)

# Step 2: 更新 Topics（必須在建後執行）
client.update_source_topics(source.id, topics=["topic1", "topic2"])

# Step 3: 關聯至 Notebook
client.link_source_to_notebook(notebook_id, source.id)

# Step 4: 觸發嵌入（在 Topics 更新後）
client.trigger_embedding(source.id)
```

**重要**: 建立 Source 時使用 `POST /api/sources/json`（不是 `/api/sources`）。

### 3. 狀態管理

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

### 4. 中間態檔案結構

```
intermediate/
├── pending/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
└── approved/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
```

---

## 配置說明

### config/config.yaml

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
  timeout: 300
  max_retries: 3

batch:
  max_concurrent: 3
  retry_attempts: 3
  retry_delay: 5

logging:
  level: "INFO"
  format: "console"
```

### config/topics.yaml

```yaml
version: "1.0"

topics:
  UFO_UAP:
    name: "UFO/UAP Research"
    description: "不明飛行物體研究、政府揭露、先進推進技術"
    notebook: "UFO-Disclosure-Archive"
    prompt_template: "ufo_research"
    channels:
      - "Ross_Coulthart"
      - "Ashton_Forbes"

channels:
  "Ross_Coulthart":
    default_topic: "UFO_UAP"
```

---

## 安全考量

1. **API 金鑰管理**: 使用環境變數（`OPEN_NOTEBOOK_PASSWORD`），不硬編碼
2. **Gemini 沙盒**: 使用 `--approval-mode plan` 確保唯讀，防止檔案被修改
3. **臨時檔案**: 使用 `try...finally` 或 context manager 確保清理
4. **錯誤日誌**: 不記錄敏感資訊（API key、密碼）

---

## 參考文件

| 文件 | 說明 |
|------|------|
| `docs/PRD.md` | 產品需求文件（完整規格） |
| `docs/architecture.md` | 系統架構與資料流 |
| `docs/modules.md` | 開發順序與檢核表 |
| `docs/interfaces/*.py` | 各模組介面定義（必須遵循） |
| `docs/interfaces/tests/*.py` | 驗收測試 |

---

## 上游與下游系統

### 上游：YouTube Transcriber

- **位置**: `~/workspace/youtube_transcriber/`
- **輸出格式**: Markdown 含 YAML frontmatter
- **輸出路徑**: `{transcriber_output}/{channel}/{YYYY-MM}/{filename}.md`

### 下游：Open Notebook

- **Base URL**: `http://localhost:5055`
- **認證**: `Authorization: Bearer <password>`
- **API 文件**: `http://localhost:5055/docs`

---

*本文件由 AI Agent 根據專案結構與文件自動生成*
