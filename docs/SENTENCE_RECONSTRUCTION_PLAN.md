# 句子重建功能實做計畫

> **日期**: 2026-02-12  
> **目標**: 將 Whisper 輸出的斷行短句合併為完整句子，提升下游 Knowledge Pipeline 的段落定位成功率  
> **預計影響**: 2 個檔案修改 + 1 個新增測試檔

---

## 1. 問題摘要

目前 whisper.cpp backend 使用 `-otxt` 輸出純文字，產出的 markdown 每行只有 3-8 個詞的斷句。下游 Knowledge Pipeline 使用 LLM 回傳的「完整句子」做段落定位，因為格式不匹配導致 **33-50% 的段落標題插入失敗**。

---

## 2. 修改方案

### 2.1 改動概覽

```
修改前:
whisper.cpp (-otxt) → 純文字 → 1 個 segment (start=0) → SaveStage 原封不動輸出

修改後:
whisper.cpp (-osrt) → SRT 字幕 → 多個 segments (各有時間戳) → SaveStage 合併句子後輸出
```

### 2.2 修改檔案清單

| # | 檔案 | 動作 | 說明 |
|---|------|------|------|
| 1 | `src/transcriber/backends/whisper_cpp.py` | 修改 | 改用 `-osrt`，解析 SRT 為多個 segments |
| 2 | `src/transcriber/pipeline/stages.py` | 修改 | 在 `SaveStage` 新增句子合併邏輯 |
| 3 | `tests/unit/test_stages.py` | 修改 | 新增句子合併的單元測試 |

---

## 3. 各檔案修改細節

### 3.1 whisper_cpp.py — 改用 SRT 輸出並解析

#### 修改重點

1. 將 `-otxt` 參數改為 `-osrt`
2. 新增 `_parse_srt()` 方法解析 SRT 格式
3. 回傳有每個 segment 時間戳的 `TranscriptionResult`

#### SRT 格式說明

```
1
00:00:00,000 --> 00:00:08,960
 It's my distinct honor to once again administer the oath to our second panel of the first

2
00:00:08,960 --> 00:00:12,120
 day of the citizen's hearing.
```

每個 entry 的結構：
- 第 1 行：序號
- 第 2 行：`HH:MM:SS,mmm --> HH:MM:SS,mmm`（起止時間）
- 第 3 行起：文字內容
- 空行分隔

#### 解析邏輯 (pseudocode)

```python
def _parse_srt(self, srt_text: str) -> list[TranscriptionSegment]:
    """解析 SRT 格式為 segments 列表."""
    segments = []
    blocks = srt_text.strip().split("\n\n")
    
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        # lines[0] = 序號
        # lines[1] = 時間軸 "HH:MM:SS,mmm --> HH:MM:SS,mmm"
        start, end = self._parse_timestamp_line(lines[1])
        text = " ".join(lines[2:]).strip()
        segments.append(TranscriptionSegment(start=start, end=end, text=text))
    
    return segments
```

### 3.2 stages.py — SaveStage 新增句子合併

#### 修改重點

在 `SaveStage` 新增 `_reconstruct_sentences()` 方法，並在 `_generate_markdown()` 中使用。

#### 合併邏輯

```
遍歷所有 segments:
  1. 將文字追加到 buffer
  2. 檢查 buffer 末尾是否有句末標點 (.!?。！？)
  3. 如果有 → 輸出 "[MM:SS] buffer 內容" 並清空 buffer
  4. 如果沒有 → 繼續累積
  5. 最後若 buffer 還有剩餘內容 → 也輸出
```

#### 修改前後對比

```markdown
# 修改前 (斷句)
[00:00] It's my distinct honor to once again administer
[00:04] the oath to our second panel of the first
[00:08] day of the citizen's hearing.

# 修改後 (完整句子)
[00:00] It's my distinct honor to once again administer the oath to our second panel of the first day of the citizen's hearing.
```

---

## 4. 注意事項

### 4.1 向後相容性

| 項目 | 是否受影響 |
|------|-----------|
| Frontmatter 格式 | ❌ 不變 |
| 檔案路徑/命名 | ❌ 不變 |
| 正文內容排版 | ✅ 會改變（斷行短句 → 完整句子） |
| 下游解析 | ✅ 正面影響（解決匹配失敗問題） |

### 4.2 Edge Cases

| 情況 | 處理方式 |
|------|---------|
| 縮寫詞 (Mr. Dr. U.S.) | 可能造成提前斷句，但影響不大，不做特殊處理 |
| 標題中的單引號 | 已在前一個 commit 中處理 |
| 超長句子（沒有標點） | 設定上限（例如累積 10 個 segment 後強制輸出） |
| SRT 解析失敗 | fallback 回純文字模式，確保不會因格式問題而中斷 |
| openai / faster-whisper backend | 不受影響，它們已有正確的 segments |

### 4.3 其他 backend 的行為

> [!IMPORTANT]
> 句子合併邏輯放在 `SaveStage`，所有 backend 都會經過。但 openai 和 faster-whisper backend 本身已經回傳多個有時間戳的 segments，所以它們也會受益於句子合併。這是正面影響。

---

## 5. 驗證計畫

### 5.1 單元測試

在 `tests/unit/test_stages.py` 新增以下測試：

```bash
# 執行測試指令
cd ~/.openclaw/workspace/youtube_transcriber
python -m pytest tests/unit/test_stages.py -v
```

新增的測試案例：

| 測試名稱 | 目的 |
|----------|------|
| `test_reconstruct_sentences_basic` | 基本合併：3 個短句 → 1 個完整句子 |
| `test_reconstruct_sentences_multiple` | 多句合併：6 個短句 → 2 個完整句子 |
| `test_reconstruct_sentences_chinese` | 中文標點 `。！？` 判斷 |
| `test_reconstruct_sentences_no_punctuation` | 無標點的超長累積 → 強制輸出 |
| `test_reconstruct_sentences_preserves_timestamp` | 合併後使用第一個 segment 的時間戳 |
| `test_generate_markdown_uses_reconstruction` | 整合測試：`_generate_markdown()` 產出完整句子格式 |

### 5.2 SRT 解析測試

在 `tests/unit/test_backends.py` 新增：

```bash
python -m pytest tests/unit/test_backends.py -v
```

| 測試名稱 | 目的 |
|----------|------|
| `test_parse_srt_basic` | 基本 SRT 解析 |
| `test_parse_srt_multiline_text` | 多行文字的 SRT entry |
| `test_parse_srt_empty` | 空 SRT 輸入的 fallback |

### 5.3 手動驗證

> [!NOTE]
> 由於 whisper.cpp 在另一台 Mac mini 上執行，完整的端對端測試需要你在那台機器上跑一次實際轉錄。但以下步驟可以在本機先確認邏輯正確：

1. **用現有 SRT 樣本驗證**：使用 `docs/UFOs - History & Background Part 2.wav.srt` 作為測試輸入
2. **你在 Mac mini 上確認**：改用 `-osrt` 後，whisper.cpp 是否正常產出 `.srt` 檔案

---

## 6. 實做順序

1. ✏️ 修改 `whisper_cpp.py`：改用 `-osrt` + 新增 SRT 解析
2. ✏️ 修改 `stages.py`：新增 `_reconstruct_sentences()` 方法
3. ✏️ 新增測試案例
4. 🧪 執行全部測試
5. 📝 確認輸出格式符合下游需求
