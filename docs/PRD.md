# Knowledge Pipeline - Product Requirements Document

> **版本**: 1.0 (MVP)  
> **日期**: 2026-02-10  
> **狀態**: 草稿  

---

## 目錄

1. [Overview](#1-overview)
2. [System Context](#2-system-context)
3. [Functional Requirements](#3-functional-requirements)
4. [Data Flow & Pipeline](#4-data-flow--pipeline)
5. [Schema & Classification](#5-schema--classification)
6. [Error Handling & Resilience](#6-error-handling--resilience)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Future Work](#8-future-work)
9. [Appendix](#9-appendix)

---

## 1. Overview

### 1.1 Problem Statement

每日自動同步 24 個 YouTube 頻道產生大量轉錄稿（目前累積 224+ 檔案），人工無法完整閱讀與內容加工，導致：
- 資訊過載無法有效吸收
- 跨影片主題連結困難
- 知識沉澱與再利用效率低落

### 1.2 Solution

建立 Knowledge Pipeline，自動化以下流程：
1. **發現**：每日掃描 YouTube Transcriber 輸出目錄，識別新增檔案
2. **語意分析**：使用 LLM（目前為 Google Gemini）提取結構化 metadata
3. **匯入**：透過 Open Notebook API 建立 Sources 與 Notes
4. **分類**：依預定義主題與子分類路由至對應 Notebook

### 1.3 Core Value

將原始轉錄稿轉化為**可搜尋、可分類、可追蹤**的知識庫，讓 Open Notebook 的 RAG 能力可被用於個人知識管理，支援：
- 跨頻道主題搜尋（例：「所有 UFO 頻道對 Disclosure 的看法」）
- 時效性篩選（例：「近 3 天加密貨幣市場動態」）
- 未來擴展至內容創作（腳本、社群文案）

**MVP 範圍限定**：僅上傳 Sources 至 Open Notebook，不建立 Notes。Sources 包含完整的轉錄內容與 LLM 分析後的 frontmatter 元數據。

### 1.4 Success Criteria

| 指標 | 目標值 |
|------|--------|
| 每日自動同步 | 無人工介入處理新增檔案 |
| API 成功率 | > 95% |
| 人工審查點 | Gemini 分析結果、最終匯入內容皆為可檢視的 Markdown |
| 處理效能 | 批次處理 20 ~ 40 個檔案 < 4 小時 |
| Provider 可替換 | 架構支援切換 LLM 供應商（Gemini CLI / Gemini / OpenAI / Local LLM）|

---

## 2. System Context

### 2.1 上游系統：YouTube Transcriber

**角色**：內容輸入源（唯讀依賴）

**輸出規格**：
- **格式**：Markdown 檔案含 YAML frontmatter
- **位置**：`{transcriber_output}/{channel}/{YYYY-MM}/{filename}.md`
- **欄位**：
  ```yaml
  ---
  channel: "Channel Name"
  video_id: "abc123"
  title: "Video Title"
  published_at: "2026-02-10"
  duration: "18:05"
  word_count: 19898
  ---
  ```
- **內容**：純文字轉錄（逐字稿）

**相依性**：
- 本系統僅讀取 `transcriber_output` 目錄
- 不修改 Transcriber 任何檔案或程式碼
- Transcriber 更新時，本系統需相容新格式

### 2.2 下游系統：Open Notebook

**角色**：知識庫儲存與 RAG 服務

**介面**：
- **Base URL**：`http://localhost:5055`（本地部署）
- **認證**：密碼保護（透過 `OPEN_NOTEBOOK_PASSWORD` 環境變數設定，使用 `Authorization: Bearer <password>` header）
- **核心 API**：
  - `POST /api/sources/json` — 建立來源（JSON payload，注意：**不是** `/api/sources`）
  - `PUT /api/sources/{id}` — 更新來源（用於設定 topics）
  - `POST /api/notebooks` — 建立筆記本
  - `POST /api/notebooks/{id}/sources/{source_id}` — 將 Source 關聯至 Notebook
  - `GET /health` — 健康檢查（**無** `/api` 前綴）

**⚠️ 重要**：Open Notebook 提供兩個建立 Source 的端點：

| 端點 | Content-Type | 用途 |
|------|-------------|------|
| `POST /api/sources` | `multipart/form-data` | 用於**檔案上傳**（有 `file` 欄位）|
| `POST /api/sources/json` | `application/json` | 用於**JSON 字串內容**（本系統使用）|

本系統採用 `type: "text"` 方式直接傳入轉錄內容（含 frontmatter），因此使用 `/api/sources/json`。若嘗試用 `POST /api/sources` 傳 JSON，會回傳錯誤（`"type": "missing"`）。

**定位**：
- 視為「特定功能用途的 API 服務提供商」
- 內部提示詞調整、RAG 參數優化在 ON 端處理
- 本系統負責將結構化內容正確送入 ON

### 2.3 本系統定位

**Knowledge Pipeline** 是連接上下游的獨立處理層：

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  YouTube        │     │   Knowledge         │     │  Open Notebook  │
│  Transcriber    │────▶│   Pipeline          │────▶│  (localhost)    │
│                 │     │   (本系統)           │     │                 │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
       上游                      處理層                    下游
       
       產生 Markdown    ──▶   LLM 語意分析     ──▶   API 上傳
       (channel,        ──▶   結構化分類       ──▶   Sources/Notes
        title, etc.)    ──▶   中間態保存       ──▶   知識庫建立
```

**設計原則**：
1. **Provider 可擴展**：MVP 使用 Gemini CLI 作為 LLM 供應商，架構預留切換至其他 API（OpenAI、Gemini API、Local LLM）的能力，以應對未來可能的服務變更或價格調整
2. **單向資料流**：不建立反向同步機制
3. **零侵入**：不修改上下游系統
4. **中間態可審查**：所有處理結果保存為 Markdown，支援人工審查後批次上傳

### 2.4 邊界定義

| 功能 | 上游 (Transcriber) | 本系統 (Pipeline) | 下游 (Open Notebook) |
|------|-------------------|------------------|---------------------|
| 影片下載 | ✅ | ❌ | ❌ |
| 語音轉文字 | ✅ | ❌ | ❌ |
| 語意分析/標籤 | ❌ | ✅ | ❌ |
| 主題分類 | ❌ | ✅ | ❌ |
| 向量儲存/RAG | ❌ | ❌ | ✅ |
| 知識問答 | ❌ | ❌ | ✅ |

---

## 3. Functional Requirements

### 3.1 File Discovery

**功能**：識別需要處理的新增轉錄稿

**核心邏輯**：
- **唯一識別**：使用 **YouTube Video ID** 作為檔案的唯一 Key（來源於檔名或 frontmatter）。
- **狀態判斷**：直接讀取檔案 Frontmatter 中的 `status` 欄位。禁止使用檔案 Hash（因處理過程會修改檔案內容）。

**需求**：
- 掃描 `transcriber_output` 目錄（遞迴子目錄）
- 識別流程：
  1. 解析檔案 meta 資訊（Video ID, Published Date）。
  2. 檢查 Frontmatter `status`：
     - 若 `status` 為 `uploaded` / `approved` / `pending` → **跳過**（視為已處理）。
     - 若 `status` 為 `failed` → **跳過**（預設不自動重試，避免陷入死迴圈，需人工介入修改狀態或使用特定 flag 強制重試）。
     - 若無 `status` 欄位 → **視為新檔案**（加入待處理清單）。
- 檔案過濾：
  - 最小字數限制（預設 100 字）
  - 頻道白名單/黑名單

**輸出**：待處理檔案路徑清單

### 3.2 Semantic Analysis

**功能**：使用 LLM 提取結構化語意資訊

**核心原則**：
- ⚠️ **禁止直接寫入 Open Notebook**：LLM 輸出必須先保存為 Markdown 檔案
- 提示詞獨立配置，支援動態調整分析策略
- **MVP 使用 Gemini CLI**：直接呼叫 `gemini` 命令行工具
  
  ⚠️ **重要限制**：Gemini Agent 有沙盒限制，只能存取執行目錄下的檔案。
  因此必須先將轉錄稿複製到專案目錄內（如 `temp/`），再讓 Gemini 讀取。
  
  參考實作流程：
  ```python
  # 1. 將轉錄稿複製到沙盒可存取位置
  transcript_path = project_dir / "temp" / f"{transcript.channel}_{hash}.md"
  shutil.copy2(transcript.path, transcript_path)
  
  # 2. 從 prompts/analysis/{category}.md 載入 template
  template = load_prompt_template(template_name)
  
  # 3. 構建完整 prompt（使用相對路徑引用 transcript）
  prompt_content = template.format(
      channel=transcript.metadata.channel,
      title=transcript.metadata.title,
      file_path=transcript_path.name  # 使用相對路徑
  )
  
  # 4. 將 prompt 寫入 temp 檔案（避免 shell 轉義問題）
  prompt_path = project_dir / "temp" / f"prompt_task_{transcript.channel}_{hash}.md"
  prompt_path.write_text(prompt_content)
  
  # 5. 執行 Gemini 分析（使用簡短的 meta prompt）
  meta_prompt = f"請讀取 {prompt_path.name} 並按照其中指示分析 {transcript_path.name}，然後輸出 JSON 結果"
  subprocess.run([
      "gemini",
      "-p", meta_prompt,           # 簡短的 meta prompt
      "-o", "json",                # JSON 輸出
      "--approval-mode", "plan"    # 唯讀模式
  ], cwd=str(project_dir), timeout=300)
  
  # 6. 提取結果並清理臨時檔案
  result = extract_result(output_file)
  transcript_path.unlink()
  prompt_path.unlink()
  ```
  
  為何使用兩個 temp 檔案：
  - **避免 shell 轉義風險**：完整 prompt 可能包含反引號、引號等特殊字元
  - **命令長度限制**：Shell 有 ARG_MAX 限制，無法將長轉錄稿直接塞進參數
  - **職責分離**：prompt（指令）與 transcript（資料）分開，便於除錯
  - **Gemini 沙盒限制**：只能讀取執行目錄下的檔案，需將檔案複製到 temp/
  
  產出結果：
  - 從輸出檔案提取 JSON/YAML 格式的分析結果
  - 將結果合併回原始 frontmatter，產出增強版 Markdown
  
- **預留 Provider 擴展能力**：架構支援未來切換至其他 LLM 供應商（OpenAI API、Gemini API、Local LLM 等）

**結構化分段 (Structured Segmentation)**：
為了優化 RAG Chunking 效果，避免長文本語意斷裂，採用「LLM 定位 + Python 執刀」的策略：
1. **LLM 分析**：生成 `segments` 清單，每個段落包含 `start_quote` (錨點文字，約 10-20 字的段落起始句)。
2. **Python 後處理**：Pipeline 在保存檔案前，執行 `inject_headers` 邏輯：
   - 讀取 `segments` 中的 `start_quote`。
   - 在原始轉錄稿中進行字串搜尋（Fuzzy Match 或 Exact Match）。
   - 在匹配位置上方插入 Markdown 標題（如 `## [Key Point] 磁場格柵原理`）。
3. **優勢**：避開 LLM 輸出 Token 上限限制，確保內容不被截斷且標題定位精準。

**分析項目**（可透過提示詞配置調整）：
| 欄位 | 說明 | 範例 |
|------|------|------|
| `semantic_summary` | 內容摘要（100-200 字） | "講者論證 MH370 熱影像與核融合推進的關聯..." |
| `key_topics` | 關鍵主題（3-5 個） | `["Nuclear Fusion", "MH370", "IEC"]` |
| `content_type` | 內容類型 | `technical_analysis` / `opinion_discussion` / `news` |
| `temporal_relevance` | 時效性 | `evergreen` / `time_sensitive` / `news` |
| `key_entities` | 關鍵實體 | `["[[Irving Langmuir]]", "[[Los Alamos]]"]` |

**輸出格式**：
```yaml
---
# 原始資訊（保留 Transcriber 輸出）
channel: "Ashton Forbes"
title: "..."
published_at: "2026-02-10"
# ...

# 語意分析結果（LLM 生成）
semantic_summary: "..."
key_topics: [...]
content_type: "..."
temporal_relevance: "..."
key_entities: [...]

# 處理中繼資料
analyzed_by: "gemini-2.0-flash"
analyzed_at: "2026-02-10T08:30:00+08:00"
---

[原始轉錄內容]
```

**提示詞配置**：
- **架構**：採用 `prompts/{task_type}/{category}.md` 分層結構，以支援不同領域的客製化分析指令。
- **位置範例**：
  - `prompts/analysis/default.md` (通用預設)
  - `prompts/analysis/crypto_tech.md` (加密貨幣技術專用)
  - `prompts/analysis/spiritual.md` (靈性內容專用)
- **配置邏輯**：於 `topics.yaml` 的 Topic 定義中指定 `prompt_template` (如 `crypto_tech`)。若未指定，則預設使用 `default`。

### 3.3 Classification & Routing

**功能**：依主題分類決定 Open Notebook 中的歸檔位置

**分類配置**：
- 位置：`config/topics.yaml`
- 結構：參照 `youtube_transcriber/channels.yaml`，獨立維護
- 對應：頻道 → 主分類 → Notebook 名稱

**範例配置**：
```yaml
topics:
  UFO_UAP:
    name: "UFO/UAP Research"
    notebooks:
      - "UFO-Disclosure-Archive"
      - "Advanced-Propulsion"
    channels:
      - "Ross_Coulthart"
      - "Ashton_Forbes"
      - "Richard_Dolan_Intelligent_Disclosure"
  
  Crypto_Finance:
    name: "Crypto & Finance"
    notebooks:
      - "Bitcoin-Analysis"
      - "Macro-Economics"
    channels:
      - "Bankless"
      - "Benjamin_Cowen"
      - "Coin_Bureau"
  
  Spiritual_Growth:
    name: "Spiritual Growth"
    notebooks:
      - "Presence-Teachings"
      - "Channeled-Messages"
    channels:
      - "Eckhart_Tolle"
      - "Paul_Selig"

# 子分類策略
taxonomy:
  primary: topic           # 主分類（上述 topics）
  secondary: channel       # 次分類：頻道名稱
  # 可選：tertiary: date_quarter  # 三級：季度
```

### 3.4 Open Notebook Integration

**功能**：將 Markdown 檔案匯入 Open Notebook

**輸入**：經過語意分析的 Markdown 檔案（本地檔案系統）

**流程**（MVP 版本）— **經實測確認**：

1. **前置檢查**：
   - API 連線測試（`GET /health`）
   - Notebook 存在檢查（不存在則建立）

2. **建立 Source**：
   ```bash
   POST /api/sources/json
   {
     "type": "text",
     "title": "{channel} | {title} | {published_at}",
     "content": "---\nchannel: xxx\nvideo_id: xxx\n...\n---\n\n[轉錄內容]"
   }
   ```
   - 回傳 `source_id`（格式：`source:xxxxx`）

3. **更新 Topics**（**必須在建立後執行**）：
   ```bash
   PUT /api/sources/{source_id}
   {
     "topics": ["ERC-8004", "AI Agents", "..."]
   }
   ```
   - ⚠️ 實測發現 `topics` 無法在建立時一起設定

4. **關聯至 Notebook**：
   ```bash
   POST /api/notebooks/{notebook_id}/sources/{source_id}
   ```

5. **觸發嵌入**（必須順序）：
   - ⚠️ 建立 Source 時務必設定 `embed: false`（避免在無 Topics 狀態下建立索引，導致 RAG 搜尋不到）。
   - 確保 Step 3 (更新 Topics) 成功完成。
   - 最後使用 `POST /api/embed` 或依賴 Step 4 的關聯動作（若支援）觸發索引更新。

6. **狀態記錄**：
   - 更新檔案 frontmatter：`status: "uploaded"`、`source_id: "..."`
   - 自動將檔案從 `pending/` 移至 `approved/`

**錯誤處理**：
- API 失敗：將檔案 frontmatter 設為 `status: "failed"`，可手動重試
- 流程中任何步驟失敗，該檔案標記為失敗，不中斷批次處理

**批次上傳程式邏輯**：
```python
for file in pending_files:
    try:
        # Step 1: 建立 Source
        source = create_source_api(file.content, file.title)
        # Step 2: 更新 Topics
        update_source_topics(source.id, file.key_topics)
        # Step 3: 關聯 Notebook
        link_source_to_notebook(source.id, target_notebook_id)
        # Step 4: 記錄成功
        mark_as_uploaded(file, source.id)
    except Exception as e:
        log_failure(file, e)
```

### 3.5 Manual Review Support

**功能**：支援人工審查所有中間狀態

**中間態檔案結構**：
```
intermediate/
├── pending/              # 待審查（LLM 分析完成但未上傳）
│   └── {YYYY-MM-DD}/
│       └── {filename}_analyzed.md
├── approved/             # 已核准（等待上傳或已上傳）
│   └── {YYYY-MM-DD}/
└── rejected/             # 已拒絕（不匯入 ON）
    └── {YYYY-MM-DD}/
```

**審查操作流程**（MVP 版本）：

1. **查看**：人工閱讀 `intermediate/pending/` 目錄下的 Markdown 檔案
   ```bash
   cat intermediate/pending/{channel}/{YYYY-MM}/*.md
   ```

2. **人工修正**（如有需要）：
   - 若 LLM 分析結果不準確，直接編輯 Markdown frontmatter
   - 修改後再次閱讀確認

3. **批次上傳**：確認無誤後，執行上傳程序
   ```bash
   python main.py --upload-approved
   ```
   - 程序自動將當日所有 `pending/` 中的檔案上傳至 Open Notebook
   - 上傳完成後自動將檔案移至 `approved/` 目錄
   - 更新 frontmatter：`status: "uploaded"`、`source_id: "..."`

4. **拒絕處理**（暫時不需要）：
   - MVP 階段若內容有問題，使用者會直接修正而非拒絕
   - `rejected/` 目錄保留供未來擴展

**注意**：人工審查是上傳前的必要步驟，MVP 不支援 `auto_approve` 自動模式

---

## 4. Data Flow & Pipeline

### 4.1 Daily Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Daily Pipeline Execution                       │
└─────────────────────────────────────────────────────────────────────────┘

Trigger: Cron (預設每日 9:00 AM 執行，此時 YouTube Transcriber 應已完成同步)

**註**：Transcriber 執行時間不固定（約需 2 小時處理 24 個頻道），Pipeline 不偵測 Transcriber 狀態。
若 Transcriber 延遲，當日檔案會在次日處理，此為可接受的遺漏風險。

    │
    ▼
┌─────────────────┐
│ 1. File Discovery │  掃描 transcriber_output/ 識別新檔案
│                 │  依 published_at 篩選 (預設: 昨天/前天)
│   Input: Dir    │  輸出: 待處理檔案清單 [{path, channel, published_at}]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Semantic     │  讀取檔案內容
│    Analysis     │  呼叫 LLM Provider (Gemini CLI/Gemini/OpenAI/Local)
│                 │  解析回傳結果，組合 frontmatter
│   Input: File   │  輸出: 增強版 Markdown (含 LLM 分析結果)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. Save to      │  寫入 intermediate/pending/{channel}/{YYYY-MM}/
│    Intermediate │  檔名: {published_at}_{video_id}_{slug(title)}_analyzed.md
│                 │  狀態: pending (等待人工審查)
│   Output: File  │
└────────┬────────┘
         │
         ▼ (人工審查後 - 執行上傳指令)
┌─────────────────┐
│ 4. Upload to    │  1. 讀取 topics.yaml，根據 channel 找到目標 Notebook
│    Open Notebook│  2. POST /api/sources/json 建立 Source
│                 │  3. PUT /api/sources/{id} 更新 topics
│   HTTP API      │  4. POST /notebooks/{id}/sources/{sid} 關聯至 Notebook
│   (批次執行)    │  輸出: source_id
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. State Update │  更新檔案 frontmatter：status, source_id
│                 │  自動將檔案從 pending/ 移至 approved/
│   Persistence   │  （無需額外 log 檔案，狀態保存在 frontmatter）
└─────────────────┘
```

### 4.2 State Management

**狀態定義**：

| 狀態 | 說明 | 儲存位置 |
|------|------|----------|
| `discovered` | 已識別但未處理 | 記憶體（執行期間）|
| `analyzed` | LLM 分析完成，待審查 | `intermediate/pending/` |
| `approved` | 人工核准，待上傳 | `intermediate/approved/` |
| `uploaded` | 已成功上傳至 ON | `intermediate/approved/` + frontmatter 標記 |
| `rejected` | 人工拒絕不上傳 | `intermediate/rejected/` |
| `failed` | 上傳失敗 | frontmatter 標記 `status: failed` |

**狀態管理**：

不使用獨立的 log 檔案，而是將狀態直接寫入檔案 frontmatter：

```yaml
---
# ... 其他 frontmatter ...

# === Pipeline 狀態（程式自動管理）===
status: "uploaded"           # pending / approved / uploaded / failed
source_id: "source:xxxxx"    # ON 回傳的 source ID（上傳後填入）
---
```

**優點**：
- 簡化架構：無需額外維護 log 檔案
- 狀態直覺：開啟 Markdown 即可看到完整資訊
- 彈性處理：即使重複上傳，也只需手動刪除 ON 中的重複 Source

**冪等性檢查**：
- 檢查 frontmatter 的 `status` 和 `source_id`
- 若 `status == "uploaded"` 且有 `source_id`，則跳過處理
- 重複上傳不會造成毀滅性後果，僅佔用額外硬碟空間

### 4.3 Intermediate File Format

**目錄結構**（方案 A：頻道優先）：

```
intermediate/
├── pending/                          # 待審查
│   ├── Bankless/
│   │   └── 2026-02/
│   │       └── 20260205_h7zj0SDWmkw_AI_on_Ethereum_analyzed.md
│   ├── Ashton_Forbes/
│   │   └── 2026-02/
│   │       └── 20260205_q3wZIslfRxg_MH370_Thermal_analyzed.md
│   └── ...
├── approved/                         # 已核准（已/待上傳）
│   └── [相同結構]
└── rejected/                         # 已拒絕
    └── [相同結構]
```

**檔案命名規則**：
```
{published_at}_{video_id}_{slug(title, max=50)}_analyzed.md
```

**檔案內容格式**：

```markdown
---
# === 原始資訊 (來自 YouTube Transcriber) ===
channel: "Bankless"
video_id: "h7zj0SDWmkw"
title: "AI on Ethereum: ERC-8004, x402, OpenClaw and the Botconomy"
published_at: "2026-02-05"
duration: "1:37:18"
word_count: 97688

# === 語意分析 (來自 LLM Provider) ===
semantic_summary: "深入解析 AI 代理在以太坊上的技術標準 ERC-8004 與支付協議 x402，探討 OpenClaw 等框架如何推動自主機器經濟..."
key_topics:
  - "ERC-8004"
  - "AI Agents"
  - "x402 Payment Protocol"
  - "OpenClaw"
  - "Botconomy"
suggested_topic: "Crypto_Finance"
content_type: "technical_analysis"
content_density: "high"
temporal_relevance: "time_sensitive"
segments:
  - section_type: "intro"
    title: "ERC-8004 簡介"
    start_quote: "So what exactly is ERC-8004? It starts with"
  - section_type: "key_point"
    title: "AI Agent 的支付難題"
    start_quote: "The biggest problem for AI agents today is"
key_entities:
  - "[[ERC-8004]]"
  - "[[x402]]"
  - "[[OpenClaw]]"
  - "[[Ethereum]]"

# === 處理中繼資料 ===
analyzed_by: "gemini-2.0-flash"
analyzed_at: "2026-02-10T06:35:00+08:00"
pipeline_version: "1.0.0"
---

[原始轉錄內容，純文字，保留完整]
```

**日期格式**：
- 統一使用 ISO 8601 格式：`YYYY-MM-DD`
- 目錄名稱使用 `YYYY-MM`（年月）

---

## 5. Schema & Classification

### 5.1 Topic Hierarchy

**配置位置**：`config/topics.yaml`

**設計原則**：
- **混合驅動**：結合 AI 的語意判斷與人工設定的靜態規則。
- **手動維護**：由使用者人工管理，不與 `youtube_transcriber/channels.yaml` 自動同步。

**配置範例**：

```yaml
# config/topics.yaml
version: "1.0"

# 1. 主題定義 (給 AI 閱讀描述，決定歸屬)
topics:
  UFO_UAP:
    name: "UFO/UAP Research"
    description: "不明飛行物體研究、政府揭露、先進推進技術"
    notebook: "UFO-Disclosure-Archive"
    prompt_template: "ufo_research"  # 對應 prompts/analysis/ufo_research.md
  
  Crypto_Finance:
    name: "Crypto & Finance"
    description: "加密貨幣分析、宏觀經濟、機構採用"
    notebook: "Bitcoin-Analysis"
    prompt_template: "crypto_tech"   # 對應 prompts/analysis/crypto_tech.md
  
  Spiritual_Growth:
    name: "Spiritual Growth"
    description: "意識覺醒、正念練習、通靈教導"
    notebook: "Presence-Teachings"
    prompt_template: "spiritual"     # 對應 prompts/analysis/spiritual.md

# 2. 頻道預設值 (當 AI 未能分類時的備援規則)
channels:
  "Ross_Coulthart":
    default_topic: "UFO_UAP"
  "Bankless":
    default_topic: "Crypto_Finance"
  "Eckhart_Tolle":
    default_topic: "Spiritual_Growth"
```

**使用方式**：
參見 [3.3 Classification & Routing](#33-classification--routing) 的詳細邏輯。

### 5.2 Metadata Schema

#### 5.2.1 原始欄位（來自 YouTube Transcriber）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `channel` | string | 頻道名稱 | `"Bankless"` |
| `video_id` | string | YouTube Video ID | `"h7zj0SDWmkw"` |
| `title` | string | 影片標題 | `"AI on Ethereum..."` |
| `published_at` | date | 發布日期 (ISO 8601) | `"2026-02-05"` |
| `duration` | string | 影片長度 | `"1:37:18"` |
| `word_count` | integer | 轉錄字數 | `97688` |

#### 5.2.2 LLM 分析欄位（由 Semantic Analysis 產生）

| 欄位 | 類型 | 說明 | 值域/範例 |
|------|------|------|-----------|
| `semantic_summary` | string | 內容摘要 (100-200 字) | 自由文字 |
| `key_topics` | array[string] | 關鍵主題 (3-5 個) → 對應 ON `topics` 欄位 | `["ERC-8004", "AI Agents"]` |
| `suggested_topic` | string | AI 建議的歸檔類別 ID | 對應 `topics.yaml` 中的 Key (如 `Crypto_Finance`) |
| `content_type` | enum | 內容類型 | `technical_analysis`, `opinion_discussion`, `news`, `educational`, `interview` |
| `content_density` | enum | 資訊密度 | `high` (硬知識/數據), `medium` (分析/論述), `low` (閒聊/雜訊) |
| `temporal_relevance` | enum | 時效性 | `evergreen`, `time_sensitive`, `news` |
| `segments` | array[object] | 敘事結構分段 | 含 `section_type`, `title`, `start_quote` (錨點) |
| `key_entities` | array[string] | 關鍵實體 | `["[[Ethereum]]", "[[x402]]"]` |
| `dialogue_format` | enum | 對話形式 | `monologue`, `interview`, `discussion`, `presentation` |

**⚠️ 注意**：Open Notebook 沒有 `source_type` 欄位，`type` 欄位用於指定輸入方式（`text`/`link`/`upload`）。`key_topics` 對應至 ON 的 `topics` 欄位。

#### 5.2.3 處理中繼資料（由 Pipeline 產生）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `analyzed_by` | string | LLM Provider 與模型 | `"gemini-2.0-flash"` |
| `analyzed_at` | datetime | 分析時間 (ISO 8601) | `"2026-02-10T06:35:00+08:00"` |
| `pipeline_version` | string | Pipeline 版本 | `"1.0.0"` |
| `source_path` | string | 原始檔案路徑 | `"Bankless/2026-02/...md"` |

#### 5.2.4 Pipeline 狀態管理（寫入 frontmatter）

不使用獨立 log 檔案，直接將處理狀態寫入 Markdown frontmatter：

| 欄位 | 類型 | 說明 | 值域 |
|------|------|------|------|
| `status` | enum | Pipeline 處理狀態 | `pending` / `approved` / `uploaded` / `failed` |
| `source_id` | string | ON 回傳的 Source ID | `"source:xxxxx"`（上傳後填入）|
| `error` | string | 錯誤訊息（失敗時）| 自由文字 |
| `error_code` | string | 錯誤代碼（失敗時）| 例：`ON_API_TIMEOUT` |
| `failed_at` | datetime | 失敗時間（失敗時）| ISO 8601 格式 |

**狀態說明**：
- `pending`：LLM 分析完成，等待人工審查
- `approved`：人工審查通過，等待上傳
- `uploaded`：已成功上傳至 Open Notebook
- `failed`：上傳或處理失敗，需人工介入

**冪等性檢查**：
- 上傳前檢查 `status == "uploaded"` 且 `source_id` 存在 → 跳過處理
- 即使重複上傳，僅佔用額外硬碟空間，不會造成毀滅性後果

### 5.3 File Naming Convention

**Intermediate 檔案**：
```
{published_at}_{video_id}_{slug(title)}_analyzed.md
```

- `published_at`: `YYYYMMDD` 格式（檔名用，無橫線）
- `video_id`: YouTube Video ID（11 碼）
- `slug(title)`: 標題 slug，只保留 alphanumeric 與 hyphen，max 50 字元
- 範例：`20260205_h7zj0SDWmkw_AI-on-Ethereum-ERC-8004-x402-OpenClaw_analyzed.md`

**Source 標題（Open Notebook 內）**：
```
{channel} | {title} | {published_at}
```
- 範例：`Bankless | AI on Ethereum: ERC-8004, x402, OpenClaw and the Botconomy | 2026-02-05`

### 5.4 Open Notebook Structure

**MVP 範圍**：僅上傳 Sources，不建立 Notes。Sources 包含完整的轉錄內容與 LLM 分析後的 frontmatter 元數據，足以支援 Open Notebook 的 RAG 搜尋功能。

（Notes 功能規劃於 [8.1 Content Generation](#81-content-generation) 未來開發）

**Source 欄位對應**：
| Open Notebook Source | Pipeline Metadata |
|---------------------|-------------------|
| `title` | `{channel} \| {title} \| {published_at}` |
| `content` | 原始轉錄內容（純文字）+ YAML frontmatter |
| `type` | `"text"`（表示直接傳入文字內容）|
| `topics` | `key_topics` 陣列（**需在建後用 PUT 更新**）|
| `metadata` | 完整 frontmatter (JSON 字串) |

**⚠️ 實測發現**：
- Open Notebook **沒有** `source_type` 欄位，`type` 欄位是用來指定輸入方式（`text`/`link`/`upload`），不是內容分類
- `topics` **無法**在 `POST /api/sources/json` 時設定，必須在建立後用 `PUT /api/sources/{id}` 更新
- `topics` **會參與全文搜尋**，所以將 `key_topics` 放進 content 的 frontmatter 和 `topics` 欄位是合理的設計

**MVP 設計**：將 frontmatter 包含在 content 中，同時將關鍵欄位寫入 `metadata` 和 `tags`，兼顧 RAG 檢索能力與結構化管理需求。這樣就同時擁有：
- 🔍 **可搜尋性**：frontmatter 進入向量索引，RAG 時 LLM 能看到頻道名稱、主題標籤等脈絡
- 🏷️ **可標籤化**：`key_topics` 放入 `tags` 欄位，給 ON 的標籤系統使用
- 📊 **可程式化**：完整 frontmatter JSON 寫入 `metadata`，供外部工具讀取

**為何不只放在 metadata？**
如果 frontmatter 只放在 `metadata`，它就不會被向量化，搜尋 `"Bankless"` 或 `"ERC-8004"` 時會匹配不到這些關鍵資訊。雖然 YAML 鍵名可能成為「雜訊」，但實務上：
1. 語意搜尋會理解 context，不會被鍵名誤導
2. frontmatter 通常在一個獨立的 chunk，不干擾主要內文
3. 這是「資料純度」與「檢索能力」之間的必要取捨

**Topics 欄位對應**：
- LLM 分析的 `key_topics` → 存入 `topics` 欄位（透過 PUT 更新）
- `topics` 會參與 ON 的全文搜尋，所以同時放在 frontmatter 和 `topics` 欄位是合理的

---

## 6. Error Handling & Resilience

### 6.1 Error Categories

| 類別 | 例子 | 處理方式 | 是否可重試 |
|------|------|---------|-----------|
| **API 錯誤** | LLM rate limit (429)、ON timeout | 指數退避重試 | ✅ |
| **網路錯誤** | DNS 失敗、連線中斷 | 線性退避重試 | ✅ |
| **資料錯誤** | 缺少必要欄位、YAML 解析失敗 | 記錄失敗，跳過 | ❌ |
| **系統錯誤** | 磁碟滿了、權限不足 | 記錄失敗，中止執行 | ❌ |
| **認證錯誤** | API key 無效、密碼錯誤 | 立即中止，人工介入 | ❌ |

### 6.2 Retry Strategy

**LLM Provider API**（MVP 使用 Gemini Agent）：
- 最大重試次數：3 次
- 退避策略：指數退避（1s → 2s → 4s）
- Timeout：300 秒（參考 enhance_with_gemini.py 設定）
- **Gemini CLI 呼叫**：直接使用 `gemini` 命令：
  ```bash
  gemini -p "請讀取 prompt_task_xxx.md 並按照其中指示分析 transcript_xxx.md，然後輸出 JSON 結果" \
         -o json \
         --approval-mode plan
  ```
- **內容傳遞**：在 prompt 中指定檔案路徑，由 Gemini 讀取（非 STDIN）
- **Rate Limiting**：免費版 1000 calls/day，批次處理需加入延遲
- **未來擴展**：架構預留切換至 OpenAI API、Gemini API、Local LLM 的能力

**Open Notebook API**（上傳）：
- 最大重試次數：3 次
- 退避策略：固定間隔 5 秒
- Timeout：5 秒（上傳應快速完成）

**⚠️ 長時間任務**：
- Podcast 產出等長時間任務（可能 30 分鐘）
- **歸類為 Future Work**（見 [8.1 Content Generation](#81-content-generation)）
- 當前架構不支援非同步輪詢模式

**重試條件**：
- HTTP 5xx：重試
- HTTP 429 (Rate Limit)：重試（配合 Retry-After header）
- HTTP 4xx（除 429）：不重試，記錄失敗
- Timeout：視為可重試

### 6.3 Dead Letter Queue

**失敗處理**：

API 呼叫失敗時，將 frontmatter 更新為 `status: "failed"`，並記錄錯誤資訊：

```yaml
---
# ... 其他 frontmatter ...
status: "failed"
error: "API timeout after 3 retries"
error_code: "ON_API_TIMEOUT"
failed_at: "2026-02-10T06:40:00+08:00"
---
```

**處理流程**：
1. 重試耗盡後，更新 frontmatter 標記為 `status: "failed"`
2. 當日執行繼續處理其他檔案（不中斷）
3. 支援手動重試：修改 frontmatter 為 `status: "approved"` 後重新執行上傳程序
4. 連續失敗超過 10 個檔案，發送警告並中止（防止系統性問題）

**人工介入指標**：
- 單一檔案失敗：修改 frontmatter 後重新上傳
- 大量失敗（>10）：檢查 API 狀態、網路、配置
- 認證錯誤：更新 API key / 密碼

### 6.4 Monitoring

**日誌系統**：
- 位置：`logs/pipeline-{YYYY-MM-DD}.log`
- 格式：`{timestamp} [{level}] {component}: {message}`
- 層級：DEBUG / INFO / WARNING / ERROR

**日誌範例**：
```
2026-02-10 06:30:15 [INFO] discovery: Found 3 new files
2026-02-10 06:30:16 [INFO] analyzer: Processing Bankless/2026-02/20260205_xxx.md
2026-02-10 06:31:02 [INFO] analyzer: Gemini analysis completed (46s)
2026-02-10 06:31:05 [INFO] uploader: Source created: uuid-xxx
2026-02-10 06:31:06 [ERROR] uploader: Failed to upload Ashton_Forbes/... (timeout)
2026-02-10 06:31:06 [INFO] uploader: Retrying (1/3)...
```

**執行統計**（記憶體內，不持久化）：
```python
{
  "started_at": "2026-02-10T06:30:00+08:00",
  "completed_at": "2026-02-10T06:45:00+08:00",
  "discovered": 3,
  "analyzed": 3,
  "uploaded": 2,
  "failed": 1,
  "skipped": 0
}
```

**每日報告**：
- 不內建於 Pipeline 程式
- 透過 OpenClaw Cron Job 觸發報告生成（見 [9.2 References](#92-references)）
- 報告格式參考 YouTube Transcriber 每日報告

---

## 7. Non-Functional Requirements

### 7.1 Performance

**處理容量**：
- 每日預期處理量：20-30 個影片轉錄稿
- 初始回填處理（224 檔案）：手動批次執行，非每日常態

**時間目標**：
| 操作 | 預期時間 | Timeout |
|------|---------|---------|
| File Discovery | < 10 秒 | 30 秒 |
| Semantic Analysis (LLM) | 30-120 秒 | 120 秒 |
| ON API Upload | < 3 秒 | 5 秒 |
| **每日總執行** | **10-60 分鐘** | - |

**資源使用**：
- 記憶體：串流處理，不載入全部檔案（< 500MB RSS）
- 磁碟：Intermediate 檔案保留直到人工審核/清除
- 網路：LLM API 與 ON API 呼叫

### 7.2 Reliability

**冪等性**：
- 同一檔案多次執行不產生重複 Open Notebook Sources（理論上）
- 透過 frontmatter `status` 和 `source_id` 欄位判斷是否已處理
- 即使重複上傳，也僅佔用額外硬碟空間，不會造成毀滅性後果

**狀態持久化**：
- 狀態直接寫入檔案 frontmatter（`status`、`source_id` 欄位）
- 支援從中斷點恢復（跳過已上傳檔案，透過 frontmatter 判斷）

**失敗處理**：
- LLM 分析失敗：更新 frontmatter `status: failed`，**不上傳原始內容**
- 需人工介入後重新處理
- ON API 上傳失敗：可重試，重試耗盡後更新 frontmatter 標記

**優雅降級**：
- 不支援（LLM 為必備，失敗即停止該檔案處理）

### 7.3 Maintainability

**配置驅動**：
- 所有行為參數化（`config/config.yaml`）
- 主題對應獨立（`config/topics.yaml`）
- 提示詞獨立（`prompts/`）

**`config/config.yaml` 範例**：

```yaml
# config/config.yaml
# Knowledge Pipeline 系統設定

version: "1.0"

# 路徑設定
paths:
  transcriber_output: "/path/to/youtube_transcriber/output"  # YouTube Transcriber 輸出目錄
  intermediate: "./intermediate"                              # 中間態檔案存放處

# Open Notebook API 設定
open_notebook:
  base_url: "http://localhost:5055"
  password: ""  # 若有設定 OPEN_NOTEBOOK_PASSWORD，請填入

# LLM Provider 設定（MVP 使用 Gemini CLI）
llm:
  provider: "gemini_cli"  # 未來可擴展: openai, gemini_api, local
  # gemini_cli 無需額外設定，直接使用系統安裝的 `gemini` 指令

# 批次處理設定
batch:
  max_concurrent: 3        # 同時處理檔案數（避免 API 限流）
  retry_attempts: 3        # API 失敗重試次數
  retry_delay: 5           # 重試間隔（秒）

# 日誌設定
logging:
  level: "INFO"           # DEBUG / INFO / WARNING / ERROR
  format: "console"       # console / file（預設 console，方便 Docker 使用）
```

**程式碼結構**：
```
src/
├── __init__.py
├── main.py                 # 入口點
├── config.py               # 配置載入
├── discovery.py            # 檔案發現
├── analyzer.py             # LLM 分析（Provider 抽象）
├── uploader.py             # Open Notebook 上傳
├── state.py                # 狀態管理
└── models.py               # 資料模型
```

**日誌規範**：
- 結構化日誌，方便 grep/filter
- 敏感資訊（API key）不記錄

### 7.4 Observability

**日誌層級**（可配置）：
- `DEBUG`: 詳細執行流程
- `INFO`: 正常操作流程（預設）
- `WARNING`: 可恢復的異常
- `ERROR`: 需要人工介入的錯誤

**關鍵指標**：
| 指標 | 說明 | 告警條件 |
|------|------|---------|
| `files_discovered` | 發現新檔案數 | - |
| `files_analyzed` | 成功分析數 | - |
| `files_uploaded` | 成功上傳數 | - |
| `files_failed` | 失敗數 | > 5 連續失敗 |
| `api_success_rate` | API 成功率 | < 90% |
| `execution_duration` | 執行時間 | > 2 小時 |

**健康檢查**（可選）：
- 獨立健康檢查指令：`python -m src.health`
- 檢查項目：設定有效、API 連線、磁碟空間

---

## 8. Future Work

### 8.1 Content Generation

**目標**：利用知識庫內容自動化產出衍生品

**功能規劃**：

| 功能 | 描述 | 複雜度 | 相依性 |
|------|------|--------|--------|
| **摘要彙整** | 依主題/時間區間自動生成內容摘要 | 低 | ON RAG |
| **社群文案** | 根據單一或多個 Sources 生成 Twitter/Threads 文案 | 中 | ON API |
| **Podcast 腳本** | 生成對話式腳本或主持人摘要 | 高 | 長時間 LLM |
| **一鍵發布** | 文案審核後直接發送至社群平台 | 高 | 平台 API |

**執行模式**：
- 所有產出必須為可審查的中間態（Markdown 檔案）
- 最終發布前需人工確認
- Podcast 等長時間任務（30+ 分鐘）需非同步輪詢架構

### 8.2 Full Automation

**目標**：跳過人工審查階段，實現全自動化

**啟用條件**：
- LLM 分析準確率經驗證 > 95%
- 建立自動化測試機制
- 設定風險控管（失敗時降級為人工審查模式）

**風險**：
- LLM 錯誤分析無法攔截
- 不當內容上傳至知識庫
- 建議僅在特定低風險頻道啟用

### 8.3 Extended Input Formats

**目標**：支援多種內容來源

**候選格式**：
- PDF（研究報告、論文）
- RSS/Atom 訂閱源（部落格、新聞）
- Podcast 音頻（Whisper 轉錄）
- 其他影片平台（Rumble、Odysee 等）

**架構調整**：
- 抽象 `InputAdapter` 介面
- 每種格式獨立 adapter
- 統一輸出為 Pipeline 內部格式

### 8.4 Advanced Features

**跨頻道分析**：
- 主題趨勢追蹤（「Disclosure」討論熱度月度變化）
- 實體關係圖（人物、組織、事件關聯）
- 觀點對比（不同頻道對同一事件的看法差異）

**雙向同步**：
- Open Notebook ↔ Obsidian 筆記同步
- 個人筆記 `my_notes` 欄位回寫至 Markdown
- Graph View 整合

**智慧推薦**：
- 基於觀看歷史的內容推薦
- 待看清單自動生成
- 重點內容主動提醒

### 8.5 Advanced Prompt Templating

**目標**：升級 Prompt Template 系統，支援更強大的模板功能

**MVP 現狀**：
- 使用 Python `str.format()` 進行簡單字串替換
- 支援變數：`{channel}`, `{title}`, `{file_path}`, `{content}`, `{word_count}`

**Future Work**：

| 功能 | 描述 | 複雜度 |
|------|------|--------|
| **Jinja2 模板引擎** | 支援條件邏輯（{% if %}）、迴圈（{% for %}）、過濾器 | 低 |
| **動態內容截斷** | 根據 token 限制自動截斷內容，避免超過 LLM 上限 | 中 |
| **多階段 Prompt** | 支援多輪對話式分析（先摘要再分類再提取 entities） | 高 |
| **Prompt 版本管理** | 追蹤 prompt 變更，支援 A/B 測試不同版本 | 中 |

**使用範例（Jinja2）**：
```markdown
# prompts/analysis/long_video.md
你是一個內容分析師，請分析這部影片：
- 頻道: {{ channel }}
- 標題: {{ title }}
{% if word_count > 50000 %}
⚠️ 這是一部長影片（{{ word_count }} 字），請專注於核心主題，
   忽略次要細節。
{% endif %}
{% for topic in suggested_topics %}
- 可能主題: {{ topic }}
{% endfor %}
```

**相依性**：
- 需安裝 `jinja2` 套件
- 需重構 `PromptLoader` 介面，向後相容現有 `.format()` 風格

---

## 9. Appendix

### 9.1 Glossary

| 術語 | 定義 |
|------|------|
| **Pipeline** | 自動化處理流程，從輸入到輸出的完整工作流 |
| **Source** | Open Notebook 中的原始內容（不可編輯），對應轉錄稿與 LLM 分析結果 |
| **Notebook** | Open Notebook 中的主題資料夾，包含相關 Sources |
| **LLM Provider** | 大語言模型供應商，MVP 使用 Gemini CLI |
| **Intermediate** | 中間態檔案，人工審查前的暫存 Markdown |
| **Frontmatter** | Markdown 檔案頂部的 YAML 元數據區塊 |
| **Topic** | 內容主題分類（如 UFO、Crypto、Spiritual）|
| **Channel** | YouTube 頻道名稱 |
| **Note** | Open Notebook 中的筆記（可編輯）— **MVP 不使用** |
| **Topics** | Open Notebook Source 的標籤欄位，對應 `key_topics`，**需在建後用 PUT 更新** |

### 9.2 References

**上游系統**：
- YouTube Transcriber: `~/workspace/youtube_transcriber/`
- Channels 配置: `youtube_transcriber/channels.yaml`

**下游系統**：
- Open Notebook: `http://localhost:5055`
- API 文件: `http://localhost:5055/docs` (Swagger UI) 或 `http://localhost:5055/openapi.json`

**報告機制**：
- 每日執行報告由 OpenClaw Cron Job 觸發
- 參考範例：YouTube Transcriber 每日報告格式

### 9.3 Changelog

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| v1.0 | 2026-02-10 | MVP 初版：File Discovery → LLM Analysis → ON Upload |

---

*文件結束*
