# YouTube Transcriber 整合需求報告

> **發件人**: Knowledge Pipeline 專案  
> **收件人**: YouTube Transcriber 維護工程師  
> **日期**: 2026-02-12  
> **優先級**: Medium  
> **類型**: 功能改進請求

---

## 1. 背景說明

### 1.1 系統關係

```
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  YouTube            │ ───▶ │  Knowledge          │ ───▶ │  Open Notebook      │
│  Transcriber        │      │  Pipeline           │      │  (知識庫)           │
│  (上游系統)          │      │  (下游系統)          │      │                     │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
        │                             │
        │ 輸出格式:                   │ 處理流程:
        │ - Markdown + YAML           │ 1. 發現新轉錄檔案
        │ - 時間戳記 + 短句           │ 2. LLM 語意分析
        │ - 頻道/影片 metadata        │ 3. 插入段落標題
        │                             │ 4. 上傳至知識庫
```

### 1.2 Knowledge Pipeline 的核心功能

Knowledge Pipeline 是連接 YouTube Transcriber 與 Open Notebook 的處理層，主要功能包括：

1. **檔案發現**: 掃描 `output/{channel}/{YYYY-MM}/` 目錄識別新轉錄稿
2. **語意分析**: 使用 LLM (Gemini CLI) 提取結構化 metadata
3. **結構化分段**: 在轉錄內容中插入 Markdown 標題，標記關鍵段落
4. **知識庫上傳**: 透過 API 建立 Sources 並關聯 Topics

---

## 2. 問題描述

### 2.1 核心問題：段落標題插入失敗

在「結構化分段」階段，我們嘗試在轉錄內容中插入 Markdown 標題，以提升 RAG (Retrieval-Augmented Generation) 的檢索品質。然而，**超過 50% 的段落標題無法正確插入**。

### 2.2 根本原因分析

問題根源在於 **Whisper 輸出格式與 LLM 分析結果的格式不匹配**。

#### Whisper 的輸出特性

YouTube Transcriber 目前輸出的格式：

```markdown
[02:04] Let's go
[02:05] and get an update
[02:06] on stock tokens.
[02:07] So can you just
[02:08] remind me
```

統計數據（以 Bankless 頻道 46 分鐘影片為例）：
- 總行數: 2,648 行
- 句末標點行數: 326 行 (~12%)
- 平均每行詞數: 3-8 個詞
- **88% 的行沒有句末標點，語句被截斷**

#### LLM 的回傳格式

LLM 分析後回傳的段落資訊：

```yaml
segments:
  - section_type: key_point
    title: 代幣化股票的現況與未來
    start_quote: "Let's go and get an update on stock tokens."
  
  - section_type: detail
    title: Robinhood 錢包的角色
    start_quote: "Let's introduce the next puzzle piece here, the Robinhood wallet."
```

**注意**: LLM 回傳的是「完整句子」，而非「斷行短句」。

#### 匹配失敗的原因

```
Whisper 輸出:                 LLM 期望匹配:                    結果:
┌─────────────────────┐      ┌────────────────────────────┐   ┌──────────┐
│ Let's go            │      │ Let's go and get an update │   │ ❌ 失敗   │
│ and get an update   │      │ on stock tokens.           │   │          │
│ on stock tokens.    │      └────────────────────────────┘   └──────────┘
└─────────────────────┘                    ↓
                                    精確匹配: -1 (不存在)
                                    模糊匹配: 相似度 < 0.8 (換行符干擾)
```

### 2.3 實際影響

以 `20260211_KcpMRlmrkEw_Robinhood-Chain-Takes-on-NYSENasdaq` 為例：

| Segment # | 標題 | 預期插入位置 | 實際結果 |
|-----------|------|-------------|---------|
| 1 | Robinhood Chain 介紹與願景 | ✅ 成功 | 標題正確插入 |
| 2 | Testnet 發布與開放生態系 | ✅ 成功 | 標題正確插入 |
| 3 | 代幣化股票的現況與未來 | ❌ **失敗** | 未找到匹配位置 |
| 4 | Robinhood 錢包的角色與定位 | ✅ 成功 | 標題正確插入 |
| 5 | 監管環境與 Clarity Act 的影響 | ❌ **失敗** | 未找到匹配位置 |
| 6 | 對 Talos 的策略性投資 | ✅ 成功 | 標題正確插入 |

**段落遺失率: 33%** (2/6)

---

## 3. 需求說明

### 3.1 目標

確保 Knowledge Pipeline 能夠準確地在轉錄內容中定位並插入段落標題。

### 3.2 技術需求

1. **輸出格式標準化**: 將 Whisper 的短句輸出拼接為完整句子
2. **保留時間戳記**: 維持 `[MM:SS]` 格式，用於後續時間定位
3. **向後相容**: 不改變檔案路徑、frontmatter 格式

### 3.3 理想的輸出格式

```markdown
---
channel: "Bankless"
video_id: "KcpMRlmrkEw"
title: "Robinhood Chain Takes on NYSE/Nasdaq"
published_at: "2026-02-11"
duration: "46:38"
word_count: 50305
---

# Robinhood Chain Takes on NYSE/Nasdaq

[02:04] Let's go and get an update on stock tokens. So can you just remind me and listeners who has access to stock tokens.
[02:10] So can you just remind me and listeners who has access to stock tokens and where those are available?
```

與現有格式對比：
- **行數減少**: ~70% (從 2,648 行降至 ~800 行)
- **可讀性提升**: 語句連貫，易於閱讀
- **RAG 友好**: LLM 能準確匹配段落起始位置

---

## 4. 建議解決方案

### 4.1 方案概述

在 `SaveStage._generate_markdown()` 中加入「句子重建」邏輯，將 Whisper 的短句 segment 拼接為完整句子。

### 4.2 實作細節

#### 判斷邏輯 (Heuristics)

```python
def should_merge_with_next(line: str) -> bool:
    """
    判斷當前行是否應該與下一行合併。
    
    合併條件 (任一即合併):
    1. 行尾沒有句末標點符號 (.!?。！？)
    2. 行長度 < 15 個字元 (可能是過短的片段)
    3. 下一行開頭是小寫字母 (接續前句)
    
    分段條件 (任一即分段):
    1. 行尾有句末標點符號
    2. 時間間隔 > 2 秒 (可選，需保留時間戳)
    """
    stripped = line.strip()
    
    # 有標點符號，視為句子結束
    if re.search(r'[.!?。！？]$', stripped):
        return False
    
    # 行太短，可能還沒說完
    if len(stripped) < 15:
        return True
    
    # 預設合併
    return True
```

#### 核心演算法

```python
def reconstruct_sentences(segments: list[dict]) -> list[str]:
    """
    將 Whisper segments 重建為連貫句子。
    
    Args:
        segments: Whisper 輸出的 segments list
                  每個 segment: {"start": float, "end": float, "text": str}
    
    Returns:
        重建後的文字行列表，每行包含時間戳和完整句子
    """
    lines = []
    buffer_text = ""
    buffer_start = 0
    
    for seg in segments:
        text = seg.get("text", "").strip()
        start = seg.get("start", 0)
        
        if not buffer_text:
            # 開始新的 buffer
            buffer_text = text
            buffer_start = start
        else:
            # 追加到現有 buffer
            buffer_text += " " + text
        
        # 檢查是否句子結束
        if re.search(r'[.!?。！？]$', text) or len(text) < 15:
            # 輸出這一行
            timestamp = format_timestamp(buffer_start)
            lines.append(f"[{timestamp}] {buffer_text}")
            buffer_text = ""
    
    # 處理剩餘內容
    if buffer_text:
        timestamp = format_timestamp(buffer_start)
        lines.append(f"[{timestamp}] {buffer_text}")
    
    return lines
```

#### 整合至 SaveStage

```python
# src/transcriber/pipeline/stages.py
# class SaveStage:

    def _generate_markdown(self, context: ProcessingContext) -> str:
        word_count = len(context.transcript)
        duration_str = self._format_duration(context.duration)
        lines = [
            "---",
            f'channel: "{context.channel_name}"',
            # ... frontmatter ...
            "---",
            "",
            f"# {context.title}",
            "",
        ]
        
        # 使用新的句子重建邏輯
        reconstructed_lines = self._reconstruct_sentences(context.transcript_segments)
        lines.extend(reconstructed_lines)
        
        return "\n".join(lines)
    
    def _reconstruct_sentences(self, segments: list[dict]) -> list[str]:
        """句子重建邏輯 (見上文)"""
        # ... 實作 ...
```

### 4.3 注意事項

#### Edge Cases 處理

1. **列舉項目**: "First, ... Second, ..." 不應合併為一句
   - 可透過大寫開頭判斷是否為新句
   
2. **人名/專有名詞**: "Mr. Smith" 中的點號不是句末
   - 需要常見縮寫詞典 (Mr., Mrs., Dr., etc.)
   
3. **時間戳精度**: 合併後使用第一句的時間戳
   - 維持可搜尋性，不影響 RAG

#### 向後相容性

- 檔案路徑格式不變
- Frontmatter 欄位不變
- 僅改變正文內容的排版方式

---

## 5. 替代方案

若上游修改不可行，我們可以在下游 (Knowledge Pipeline) 進行相同的處理。但這會有以下缺點：

1. **重複運算**: 每次分析都需要重建句子
2. **歷史檔案**: 已有的大量轉錄檔案無法受益
3. **標準化**: 不同下游系統需要各自實作相同邏輯

**強烈建議在上游統一處理**，讓輸出格式標準化。

---

## 6. 附錄

### A. 樣本檔案

- **原始檔案**: `~/.openclaw/workspace/youtube_transcriber/output/Bankless/2026-02/2026-02-11_KcpMRlmrkEw_Robinhood_Chain_Takes_on_NYSE_Nasdaq___Robinhood_C.md`
- **分析後檔案**: `knowledge-pipeline/intermediate/pending/Bankless/2026-02/20260211_KcpMRlmrkEw_Robinhood-Chain-Takes-on-NYSENasdaq-Robinhood-Cryp_analyzed.md`

### B. 相關程式碼位置

- **下游 Analyzer**: `knowledge-pipeline/src/analyzer.py` (StructuredSegmentation 類別)
- **上游 SaveStage**: `youtube_transcriber/src/transcriber/pipeline/stages.py` (第 380-403 行)

### C. 聯絡資訊

如需進一步討論技術細節，請聯絡 Knowledge Pipeline 維護團隊。

---

*本報告由 Knowledge Pipeline 專案生成，用於跨專案協作溝通。*
