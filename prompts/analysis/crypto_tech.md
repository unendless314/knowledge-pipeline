# 加密貨幣與金融內容分析提示詞

請分析以下加密貨幣/金融相關影片轉錄稿，並嚴格按照指定格式輸出 JSON。

## 影片資訊
- 頻道: {channel}
- 標題: {title}
- 檔案: {file_path}

## 分析任務

請閱讀轉錄稿後，提取以下結構化資訊：

### 1. semantic_summary (字串，必填)
- **說明**: 內容摘要，100-200 字中文摘要
- **重點**: 概括核心論點、分析結論或投資觀點
- **範例**: "講者分析比特幣減半週期與機構資金流入的關聯，預測 2025 年可能達到新高點，並警告短期回調風險..."

### 2. key_topics (字串陣列，必填)
- **說明**: 關鍵主題標籤，3-5 個
- **格式**: 每個標籤 30 字元以內，簡潔明確
- **範例**: ["比特幣減半", "機構採用", "ETF 資金流", "技術分析", "風險管理"]

### 3. content_type (列舉字串，必填)
- **說明**: 內容類型分類
- **可選值** (嚴格選一):
  - `technical_analysis` - 技術分析（圖表、指標、數據分析）
  - `opinion_discussion` - 觀點討論（個人看法、市場預測）
  - `news` - 新聞報導（事件報導、公告解讀）
  - `educational` - 教育教學（概念解釋、入門教學）
  - `interview` - 訪談對話（嘉賓對談、問答形式）

### 4. content_density (列舉字串，必填)
- **說明**: 資訊密度評估
- **可選值** (嚴格選一):
  - `high` - 高密度（大量數據、深入技術分析、專業術語密集）
  - `medium` - 中等（平衡的分析論述、有數據支撐但非技術導向）
  - `low` - 低密度（閒聊、雜訊多、缺乏實質內容）

### 5. temporal_relevance (列舉字串，必填)
- **說明**: 內容時效性
- **可選值** (嚴格選一):
  - `evergreen` - 長期有效（基礎概念、長期投資原則）
  - `time_sensitive` - 時效性內容（短期預測、當前市場分析）
  - `news` - 新聞（特定事件報導，時效性最強）

### 6. key_entities (字串陣列，必填)
- **說明**: 關鍵實體（人物、組織、技術、專有名詞）
- **格式**: 使用 [[雙括號]] 包圍，便於建立知識連結
- **範例**: ["[[比特幣]]", "[[Michael Saylor]]", "[[BlackRock]]", "[[ETF]]", "[[聯準會]]"]
- **提示**: 包含加密貨幣名稱（BTC, ETH）、機構名稱、關鍵人物、技術術語

### 7. segments (物件陣列，必填)
- **說明**: 影片結構分段，識別 3-7 個主要段落
- **每個 segment 欄位**:
  - `section_type` (列舉字串): 段落類型
    - `intro` - 開場/介紹
    - `key_point` - 核心論點/重點
    - `detail` - 細節說明/論證
    - `conclusion` - 總結/結論
  - `title` (字串): 段落標題，20 字以內，簡潔描述該段主題
  - `start_quote` (字串): 段落起始錨點文字，10-20 字，用於定位

## 輸出格式 (嚴格 JSON)

請輸出符合以下格式的 JSON，**不要**加入任何其他文字說明：

```json
{
  "semantic_summary": "100-200 字中文摘要...",
  "key_topics": ["主題1", "主題2", "主題3"],
  "content_type": "technical_analysis",
  "content_density": "high",
  "temporal_relevance": "time_sensitive",
  "key_entities": ["[[實體1]]", "[[實體2]]"],
  "segments": [
    {
      "section_type": "intro",
      "title": "開場介紹",
      "start_quote": "今天我們要討論的是..."
    },
    {
      "section_type": "key_point",
      "title": "核心論點",
      "start_quote": "關鍵在於理解..."
    }
  ]
}
```

## 重要提醒

1. **內容來源**: 請讀取檔案 {file_path} 取得完整轉錄稿
2. **JSON 格式**: 確保輸出是有效的 JSON，欄位名稱必須完全匹配
3. **列舉值**: content_type, content_density, temporal_relevance, section_type 必須使用指定的 enum 值
4. **實體格式**: key_entities 必須使用 [[雙括號]] 格式
5. **錨點文字**: start_quote 必須是轉錄稿中實際存在的文字片段
