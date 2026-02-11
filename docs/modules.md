# Knowledge Pipeline - 開發檢核表與順序

> **版本**: 1.1 (Revised)  
> **日期**: 2026-02-11  
> **說明**: 本文件為開發執行的 Roadmap，詳細技術規格請參閱 `architecture.md` 與 `interfaces/`。

---

## 1. 優先順序總覽

| 順序 | 模組 | 優先級 | 預估工時 | 前置依賴 | 說明 |
|------|------|--------|----------|----------|------|
| 1 | **Models** | 🔴 高 | 2h | - | 核心資料結構定義 |
| 2 | **Config** | 🔴 高 | 2h | Models | 配置載入與驗證 |
| 3 | **Discovery** | 🔴 高 | 4h | Models, Config | 檔案掃描與過濾 |
| 4 | **State** | 🟡 中 | 3h | Models | 狀態管理與檔案操作 |
| 5 | **LLM** | 🟡 中 | 5h | Models | LLM Provider 抽象層 (Gemini CLI) |
| 6 | **Analyzer** | 🟡 中 | 4h | Models, Config, State, LLM | 語意分析流程編排 |
| 7 | **Uploader** | 🟡 中 | 4h | Models, Config | Open Notebook API 客戶端 |
| 8 | **Main (CLI)** | 🟢 低 | 3h | All above | CLI 入口與流程整合 |

---

## 2. 詳細開發任務

### Phase 1: 基礎建設

#### Step 1: Models (`src/models.py`)
- **目標**: 定義系統使用的所有 Dataclass 與 Enum。
- **參考介面**: `docs/interfaces/models.py`
- **驗收標準**:
  - [ ] 所有 Enum (PipelineStatus, ContentType 等) 定義正確。
  - [ ] TranscriptFile 與 AnalysisResult 資料結構完整。
  - [ ] 通過 `docs/interfaces/tests/test_models.py` 測試。

#### Step 2: Config (`src/config.py`)
- **目標**: 實作配置載入與環境變數覆蓋邏輯。
- **參考介面**: `docs/interfaces/config.py`
- **驗收標準**:
  - [ ] 能正確載入 `config/config.yaml` 與 `config/topics.yaml`。
  - [ ] 支援 `OPEN_NOTEBOOK_PASSWORD` 環境變數覆蓋。
  - [ ] 通過 `docs/interfaces/tests/test_config.py` 測試。

#### Step 3: Discovery (`src/discovery.py`)
- **目標**: 掃描目錄並過濾待處理檔案。
- **參考介面**: `docs/interfaces/discovery.py`
- **驗收標準**:
  - [ ] 正確解析 Markdown Frontmatter。
  - [ ] **關鍵**: `failed` 狀態預設跳過（`should_retry` 預設回傳 False）。
  - [ ] **關鍵**: 實作 `cleanup_temp_files`，能清理過期的 `temp/` 檔案。
  - [ ] 通過 `docs/interfaces/tests/test_discovery.py` 測試。

---

### Phase 2: 核心邏輯

#### Step 4: State (`src/state.py`)
- **目標**: 管理檔案狀態與冪等性。
- **參考介面**: `docs/interfaces/state.py`
- **驗收標準**:
  - [ ] 更新 Frontmatter 時，盡量保留原始格式（建議使用 `ruamel.yaml`）。
  - [ ] 冪等性檢查正確：`uploaded` 且有 `source_id` 視為已完成。
  - [ ] `failed` 狀態預設不重試。
  - [ ] 通過 `docs/interfaces/tests/test_state.py` 測試。

#### Step 5: LLM (`src/llm/`)
- **目標**: 實作 Gemini CLI Provider 與抽象層。
- **參考介面**: `docs/interfaces/llm.py`
- **技術細節**: 詳見 `architecture.md` 章節 5.1.1
- **驗收標準**:
  - [ ] **關鍵**: 強制使用 `-p` flag 啟動 headless 模式。
  - [ ] **關鍵**: 長文本寫入 `temp/`，並使用相對路徑傳遞給 Gemini。
  - [ ] 使用 `try...finally` 確保 temp 檔案被清理。
  - [ ] 通過 `docs/interfaces/tests/test_llm.py` 測試。

#### Step 6: Analyzer (`src/analyzer.py`)
- **目標**: 編排 LLM 分析流程，產出增強版 Markdown。
- **參考介面**: `docs/interfaces/analyzer.py`
- **驗收標準**:
  - [ ] 正確載入 Prompt Template 並格式化。
  - [ ] 將 LLM 輸出 (JSON) 轉換為 `AnalysisResult` 物件。
  - [ ] 產出的 Markdown 包含完整 Frontmatter。
  - [ ] 通過 `docs/interfaces/tests/test_analyzer.py` 測試。

#### Step 7: Uploader (`src/uploader.py`)
- **目標**: 上傳內容至 Open Notebook。
- **參考介面**: `docs/interfaces/uploader.py`
- **驗收標準**:
  - [ ] **流程順序**: Create (embed=False) -> Update Topics -> Trigger Embedding。
  - [ ] 正確使用 `POST /api/sources/json` 端點。
  - [ ] 支援 `trigger_embedding` 手動觸發向量化。
  - [ ] 通過 `docs/interfaces/tests/test_uploader.py` 測試。

---

### Phase 3: 整合

#### Step 8: Main (`src/main.py`)
- **目標**: CLI 入口點與流程串接。
- **驗收標準**:
  - [ ] 支援 `discover`, `analyze`, `upload`, `run` 子命令。
  - [ ] 啟動時自動執行 `cleanup_temp_files`。
  - [ ] 日誌輸出清晰。

---

## 3. 開發注意事項

1. **依賴關係**：請嚴格按照 Step 1 -> Step 8 的順序開發，避免循環依賴。
2. **介面一致性**：實作必須符合 `docs/interfaces/` 定義，若發現實作困難，請先討論修改介面。
3. **錯誤處理**：所有模組都應定義專屬的 Exception 類別（如 `LLMError`, `APIError`）。
4. **測試驅動**：每個 Step 完成後，務必執行對應的驗收測試。

---

*文件結束*
