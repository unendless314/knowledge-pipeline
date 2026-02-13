# Knowledge Pipeline - 系統架構文件

> **版本**: 1.0  
> **日期**: 2026-02-11  
> **狀態**: Phase 2 - 契約階段

---

## 1. 系統概述與定位

### 1.1 系統定位

Knowledge Pipeline 是連接 **YouTube Transcriber**（上游）與 **Open Notebook**（下游）的獨立處理層，負責將原始轉錄稿轉化為可搜尋、可分類、可追蹤的知識庫內容。

### 1.2 核心價值

- **語意分析**：使用 LLM 提取結構化 metadata
- **主題分類**：依預定義規則路由至對應 Notebook
- **人工審查**：所有中間態皆可檢視與修正
- **冪等處理**：透過 frontmatter 狀態管理避免重複處理

---

## 2. 系統架構圖

### 2.1 高層架構

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Knowledge Pipeline                              │
│                                   (本系統)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐     │
│  │   File          │ ───▶ │   Semantic      │ ───▶ │   Open Notebook │     │
│  │   Discovery     │      │   Analysis      │      │   Uploader      │     │
│  │                 │      │   (Analyzer)    │      │                 │     │
│  │ - Scan dir      │      │                 │      │ - Create source │     │
│  │ - Filter new    │      │ - LLM analysis  │      │ - Update topics │     │
│  │ - Parse YAML    │      │ - Extract meta  │      │ - Link notebook │     │
│  └────────┬────────┘      └────────┬────────┘      └────────┬────────┘     │
│           │                        │                        │              │
│           ▼                        ▼                        ▼              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        State Management                              │   │
│  │  - Frontmatter status tracking  - Idempotency check                 │   │
│  │  - File lifecycle management    - Error recording                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Configuration                                 │   │
│  │  - Load topics.yaml             - Load prompts/*.md                 │   │
│  │  - Validate settings            - Environment vars                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        LLM Provider Layer (抽象層)                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │GeminiCLI    │ │OpenAI API   │ │Gemini API   │ │Local LLM    │   │   │
│  │  │Provider     │ │Provider     │ │Provider     │ │Provider     │   │   │
│  │  │(目前實作)    │ │(預留)       │ │(預留)       │ │(預留)       │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
         ▲                                                      │
         │                                                      ▼
┌─────────────────┐                                  ┌─────────────────┐
│  YouTube        │                                  │  Open Notebook  │
│  Transcriber    │                                  │  (localhost)    │
│                 │                                  │                 │
│ - 24 channels   │                                  │ - RAG search    │
│ - Daily sync    │                                  │ - Knowledge QA  │
│ - Markdown out  │                                  │ - Vector store  │
└─────────────────┘                                  └─────────────────┘
       上游                                                   下游
```

### 2.2 資料流向

```
YouTube Transcriber Output
│
│  {channel}/{YYYY-MM}/{filename}.md
│  ├── channel, video_id, title
│  ├── published_at, duration, word_count
│  └── [transcript content]
│
▼
┌─────────────────┐
│ File Discovery  │  Parse frontmatter → Check status
│                 │  Filter: word_count >= 100
│                 │  Skip if status in [uploaded, approved, pending]
└────────┬────────┘
         │  List[TranscriptFile]
▼
┌─────────────────┐
│ Semantic        │  TranscriptFile -> TranscriptInput
│ Analysis        │  Call LLM via LLMClient -> LLMProvider
│ (Analyzer)      │  Extract: summary, topics, entities, segments
│                 │  Save to: intermediate/pending/{channel}/
└────────┬────────┘
         │  AnalyzedMarkdown
▼
┌─────────────────┐
│ Manual Review   │  Human inspects intermediate/pending/
│ (Optional)      │  Edit frontmatter if needed
└────────┬────────┘
         │  Approved files
▼
┌─────────────────┐
│ Open Notebook   │  POST /api/sources/json
│ Uploader        │  PUT /api/sources/{id} (topics)
│                 │  POST /notebooks/{id}/sources/{sid}
└────────┬────────┘
         │  Update frontmatter: status=uploaded, source_id=xxx
▼
┌─────────────────┐
│ State Update    │  Move file: pending/ → approved/
│ & Persistence   │  Record completion
└─────────────────┘
```

---

## 3. 核心模組清單與職責

### 3.1 模組總覽

| 模組 | 檔案 | 職責 | 依賴 |
|------|------|------|------|
| **Config** | `config.py` | 配置載入與驗證 | - |
| **Models** | `models.py` | 資料模型定義 | Config |
| **Discovery** | `discovery.py` | 檔案掃描與識別 | Models, Config |
| **LLM** | `llm/` | LLM Provider 抽象層 | Models |
| **Analyzer** | `analyzer.py` | LLM 語意分析 | Models, Config, LLM |
| **Uploader** | `uploader.py` | Open Notebook API 操作 | Models, Config |
| **State** | `state.py` | 狀態管理與持久化 | Models |
| **Main** | `main.py` | 流程編排與 CLI | 所有模組 |

### 3.2 各模組詳細職責

#### 3.2.1 Config (`config.py`)

- 載入 `config/config.yaml` 與 `config/topics.yaml`
- 環境變數覆蓋（`OPEN_NOTEBOOK_PASSWORD` 等）
- 配置驗證與預設值處理
- 提供型別安全的配置物件

#### 3.2.2 Models (`models.py`)

- 定義所有 Dataclass / Pydantic Model
- 包含：
  - `TranscriptFile`: 原始轉錄檔案結構
  - `AnalysisResult`: LLM 分析結果
  - `SourceMetadata`: Open Notebook 上傳用 metadata
  - `PipelineState`: 狀態追蹤

#### 3.2.3 Discovery (`discovery.py`)

- 遞迴掃描 `transcriber_output/` 目錄
- 解析 Markdown frontmatter (YAML)
- 依 `status` 欄位過濾已處理檔案
- 頻道白名單/黑名單過濾
- 最小字數檢查（預設 100 字）

#### 3.2.4 LLM (`llm/`)

**位置**: `src/llm/`  
**職責**: LLM Provider 抽象層，支援多種 LLM 實作

**核心組件**:
- `LLMClient`: 通用客戶端入口（工廠模式）
- `LLMProvider`: Provider 抽象介面（Protocol）
- `GeminiCLIProvider`: Gemini CLI 實作（當前）
- `PromptLoader`: Prompt 載入與格式化
- `OutputParser`: LLM 輸出解析

**處理流程**:
1. `Analyzer` 建立 `TranscriptInput` 並呼叫 `LLMClient`
2. `LLMClient` 委派給具體 `LLMProvider`（如 `GeminiCLIProvider`）
3. `Provider` 處理長文本限制（複製到 temp/）
4. `Provider` 呼叫 LLM API/CLI
5. `Provider` 解析輸出為標準 `AnalysisResult`
6. 回傳給 `Analyzer` 進行後續處理

**Provider 可替換性**:
- MVP: `GeminiCLIProvider`（免費、簡單）
- 未來: `OpenAIProvider`, `GeminiAPIProvider`, `LocalLLMProvider`
- 切換方式: 修改 `config.yaml` 的 `llm.provider`

#### 3.2.5 Analyzer (`analyzer.py`)

- 讀取轉錄檔案內容
- 將 `TranscriptFile` 轉換為 `TranscriptInput`
- 透過 `LLMClient` 進行語意分析（與具體 Provider 解耦）
- 解析 `AnalysisResult` 並建立增強版 frontmatter
- 執行 `inject_headers` 結構化分段
- 儲存分析結果至 `intermediate/pending/`

#### 3.2.5 Uploader (`uploader.py`)

- Open Notebook API 客戶端
- 建立 Source (`POST /api/sources/json`)
- 更新 Topics (`PUT /api/sources/{id}`)
- 關聯 Notebook (`POST /notebooks/{id}/sources/{sid}`)
- 錯誤重試機制（指數退避）

⚠️ **重要實作細節**：
`build_content()` 必須從分析後檔案（`*_analyzed.md`）讀取內容，而非 `processing.source_path`。
`source_path` 指向原始轉錄檔案（可能含 timestamps），分析後檔案才是清理過的內容。

#### 3.2.6 State (`state.py`)

- 讀取/更新 Markdown frontmatter
- 狀態轉換管理（pending → approved → uploaded）
- 冪等性檢查（避免重複上傳）
- 失敗記錄與重試支援
- 檔案搬移（pending/ ↔ approved/）

#### 3.2.7 Main (`main.py`)

- CLI 入口點（argparse）
- 流程編排與協調
- 日誌設定與執行統計
- 支援子命令：
  - `discover`: 僅執行檔案發現
  - `analyze`: 執行發現+分析
  - `upload`: 上傳 approved 檔案
  - `run`: 完整流程（發現→分析）

---

## 4. 模組間依賴關係圖

```
                    ┌─────────────┐
                    │   Config    │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Models    │ │  Discovery  │ │   Analyzer  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           │           ┌───┴───┐           │
           │           │       │           │
           ▼           ▼       ▼           ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │     LLM     │ │     Main    │ │    State    │
    │  ┌─────┐    │ └──────┬──────┘ └─────────────┘
    │  │Gemini│    │        │
    │  │CLI  │    │        │
    │  └─────┘    │        │
    └─────────────┘        │
                           ▼
                    ┌─────────────┐
                    │  Uploader   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │Open Notebook│
                    └─────────────┘
```

### 4.1 依賴說明

- **Config** 為基礎設施，所有模組皆依賴
- **Models** 被 Discovery, LLM, Analyzer, Uploader, State 共用
- **LLM** 為獨立抽象層，定義 Provider Protocol
  - `GeminiCLIProvider` 為當前實作
  - 未來可擴展 `OpenAIProvider`, `LocalLLMProvider`
- **Analyzer** 依賴 LLM（透過 `LLMClient`），與具體 Provider 解耦
- **Main** 編排所有業務模組（Discovery → Analyzer → Uploader）
- **State** 獨立運作，僅依賴 Models
- **Uploader** 呼叫外部 API（Open Notebook）

---

## 5. 外部依賴

### 5.1 LLM Provider

本系統透過 `src.llm` 模組提供 LLM Provider 抽象層，支援多種實作：

#### 5.1.1 Gemini CLI Provider（當前實作）

- **用途**: LLM 語意分析（MVP 預設）
- **指令**: `gemini`（需預先安裝 Google Gemini CLI）
- **文件**: 執行 `gemini --help` 查看完整選項
- **輸入方式**: STDIN prompt（內容透過檔案路徑指定）
- **關鍵選項**:
  - `-p, --prompt`: **必須使用！** 啟動 headless 模式（否則進入互動模式）
  - `-o json`: 輸出 JSON 格式（便於解析）
  - `-m gemini-2.5-pro`: 指定模型
  - `--approval-mode plan`: **使用 plan 模式**（唯讀，最安全）
- **輸出解析**: 提取 JSON 區塊（處理可能的雜訊）
- **長文本處理**: 自動複製到 `temp/` 目錄，使用相對路徑
- **Timeout**: 120 秒（考慮冷啟動時間）
- **Retry**: 3 次（指數退避 3s → 6s → 12s）
- **Rate Limit**: 免費版 1000 calls/day

**命令範例**:
```bash
# 正確：使用 -p 進入 headless 模式，plan 模式確保安全
# 使用兩個 temp 檔案傳遞：prompt_task_xxx.md（指令）和 transcript_xxx.md（內容）
gemini -p "請讀取 prompt_task_Bankless_7842.md 並按照其中指示分析 transcript_Bankless_7842.md，然後輸出 JSON 結果" \
       -o json \
       -m gemini-2.5-pro \
       --approval-mode plan

# 錯誤：缺少 -p，會進入互動模式！
gemini "分析檔案 temp/Bankless_1234.md"

# 錯誤：直接傳遞完整 prompt（有 shell 轉義風險）
gemini -p "{完整的 prompt 內容...包含反引號和引號等}"
```

**輸出解析範例**:
```python
# Gemini 輸出可能包含雜訊，需要提取 JSON 區塊
import json
import re

def extract_json_block(text: str) -> dict:
    # 尋找 ```json ... ``` 代碼塊
    matches = re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if matches:
        return json.loads(matches[-1])
    
    #  fallback: 尋找 { ... } 區塊
    #  ...
```

**Provider 設定** (`config.yaml`):
```yaml
llm:
  provider: "gemini_cli"
  project_dir: "/path/to/knowledge-pipeline"
  timeout: 300
  max_retries: 3
```

#### 5.1.2 OpenAI API Provider（預留）

- **用途**: 未來切換至 OpenAI GPT-4/Claude 等
- **狀態**: 介面已定義，實作待開發

**Provider 設定** (未來):
```yaml
llm:
  provider: "openai_api"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4"
```

#### 5.1.3 Local LLM Provider（預留）

- **用途**: 未來支援本地模型（Llama、Ollama 等）
- **狀態**: 介面已定義，實作待開發

### 5.2 Open Notebook API

- **Base URL**: `http://localhost:5055`
- **認證**: `Authorization: Bearer <password>`
- **核心端點**:
  - `GET /health`
  - `POST /api/sources/json`
  - `PUT /api/sources/{id}`
  - `POST /api/notebooks/{id}/sources/{source_id}`
- **Timeout**: 5 秒
- **Retry**: 3 次（固定間隔 5 秒）

### 5.3 檔案系統

- **輸入**: YouTube Transcriber 輸出目錄（唯讀）
- **輸出**: `intermediate/` 中間態檔案
- **權限**: 需讀寫中間態目錄

---

## 6. 資料結構

### 6.1 核心資料流

```
Raw Markdown File
       │
       ▼
┌─────────────────┐
│ TranscriptFile  │  path, channel, video_id, title,
│  (Parsed)       │  published_at, duration, word_count,
│                 │  content, status?, source_id?
└────────┬────────┘
         │
         ▼ (Discovery.discover())
         │
         ▼ (轉換)
┌─────────────────┐
│ TranscriptInput │  channel, title, content,
│  (LLM Input)    │  published_at, word_count, file_path
└────────┬────────┘
         │
         ▼ (LLMClient.analyze())
         │    ┌─────────────────┐
         ├──▶ │ GeminiCLIProvider│
         │    │  (或其他Provider) │
         │    └────────┬────────┘
         │             │ subprocess.run(["gemini", ...])
         │             │
         ▼             ▼
┌─────────────────┐
│ AnalysisResult  │  semantic_summary, key_topics[],
│  (LLM Output)   │  content_type, temporal_relevance,
│                 │  segments[], key_entities[]
└────────┬────────┘
         │
         ▼ (Analyzer.analyze())
┌─────────────────┐
│ AnalyzedMarkdown│  Merged frontmatter + cleaned content
│  (File Output)  │  Saved to intermediate/pending/
│                 │  ⚠️ timestamps removed, headers injected
└────────┬────────┘
         │
         ▼ (Uploader.upload())
         │  ⚠️ Must read content from AnalyzedMarkdown file,
         │     NOT from original source_path (which has raw timestamps)
┌─────────────────┐
│   ON Source     │  id (source:xxxxx), title, content,
│  (API Response) │  topics[], metadata{}
└─────────────────┘
```

---

## 7. 錯誤處理策略

| 錯誤類型 | 處理方式 | 狀態標記 |
|---------|---------|---------|
| LLM Timeout | 重試 3 次 → 標記 failed | `status: failed` |
| API 4xx | 不重試，標記 failed | `status: failed` |
| API 5xx | 重試 3 次 → 標記 failed | `status: failed` |
| YAML 解析錯誤 | 跳過檔案，記錄警告 | - |
| 磁碟滿了 | 中止執行 | - |

---

## 7.1 常見實作陷阱

| 陷阱 | 錯誤示範 | 正確做法 |
|------|----------|----------|
| 從原始檔案讀取內容上傳 | `build_content()` 使用 `processing.source_path` | 從 `*_analyzed.md` 檔案讀取清理後內容 |
| API ID 格式錯誤 | `PUT /api/sources/{pure_id}` (無前綴) | `PUT /api/sources/source:xxxxx` (完整 ID) |
| Notebooks API 回應格式 | `response.get("notebooks", [])` | 直接處理 list：`response if isinstance(response, list) else []` |
| SourceCreateResponse 欄位 | `created_at`, `content` | `created`, `full_text` (依 API 實際回傳) |

---

## 8. 擴展性設計

### 8.1 LLM Provider 可替換

```python
class LLMProvider(Protocol):
    def analyze(self, content: str, prompt: str) -> AnalysisResult: ...

class GeminiCLIProvider: ...
class OpenAIProvider: ...  # Future
class LocalLLMProvider: ...  # Future
```

### 8.2 Input Adapter 預留

```python
class InputAdapter(Protocol):
    def parse(self, filepath: Path) -> TranscriptFile: ...

class YouTubeTranscriptAdapter: ...  # Current
class PDFAdapter: ...  # Future
class RSSAdapter: ...  # Future
```

---

## 9. 附錄

### 9.1 目錄結構

```
knowledge-pipeline/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry
│   ├── config.py            # Configuration
│   ├── models.py            # Data models
│   ├── discovery.py         # File discovery
│   ├── analyzer.py          # LLM analysis
│   ├── uploader.py          # ON API client
│   └── state.py             # State management
├── config/
│   ├── config.yaml          # Main config
│   └── topics.yaml          # Topic mapping
├── prompts/
│   └── analysis/
│       ├── default.md       # Default prompt
│       ├── crypto_tech.md   # Crypto-specific
│       └── ufo_research.md  # UFO-specific
├── intermediate/
│   ├── pending/             # Awaiting review
│   ├── approved/            # Ready/Uploaded
│   └── rejected/            # Rejected (future)
├── logs/
│   └── pipeline-{date}.log
└── docs/
    ├── PRD.md               # Product requirements
    ├── architecture.md      # This file
    ├── modules.md           # Module dev order
    └── interfaces/          # Interface definitions
        ├── models.py
        ├── config.py
        ├── discovery.py
        ├── analyzer.py
        ├── uploader.py
        ├── state.py
        └── tests/
```

### 9.2 狀態機

```
                    ┌─────────────┐
    ┌───────────────│  Discovered │◀─────────────────┐
    │               │  (Memory)   │                  │
    │               └──────┬──────┘                  │
    │                      │ analyze()               │
    │                      ▼                         │
    │               ┌─────────────┐   edit manually  │
    └──────────────▶│   Pending   │──────────────────┘
       skip if done │  (pending/) │
                    └──────┬──────┘
                           │ upload()
                           ▼
                    ┌─────────────┐
            ┌───────│   Uploaded  │
            │       │ (approved/) │
            │       └─────────────┘
            │
            │  retry manually
            ▼
    ┌─────────────┐
    │    Failed   │
    │  (frontmatter)
    └─────────────┘
```

---

*文件結束*
