# 靈性成長內容分析提示詞

請分析以下靈性/身心靈相關影片轉錄稿，並嚴格按照指定格式輸出 JSON。

## 影片資訊
- 頻道: {channel}
- 標題: {title}
- 檔案: {file_path}

## 分析任務

請閱讀轉錄稿後，提取以下結構化資訊：

### 1. semantic_summary (字串，必填)
- **說明**: 內容摘要，100-200 字中文摘要
- **重點**: 概括教導的核心訊息、實踐方法和主要洞見
- **範例**: "講者引導聽眾覺察當下的力量，透過呼吸練習和正念觀察，釋放對過去未來的執著，回到當下臨在..."

### 2. key_topics (字串陣列，必填)
- **說明**: 關鍵主題標籤，3-5 個
- **格式**: 每個標籤 30 字元以內，簡潔明確
- **範例**: ["當下覺察", "正念練習", "能量療癒", "意識轉化", "靈性覺醒"]

### 3. content_type (列舉字串，必填)
- **說明**: 內容類型分類
- **可選值** (嚴格選一):
  - `technical_analysis` - 技術分析（能量運作機制分析）
  - `opinion_discussion` - 觀點討論（靈性觀點、哲學探討）
  - `news` - 新聞報導（靈性社群動態）
  - `educational` - 教育教學（教導、引導練習）
  - `interview` - 訪談對話（導師對談、通靈傳訊）

### 4. content_density (列舉字串，必填)
- **說明**: 資訊密度評估
- **可選值** (嚴格選一):
  - `high` - 高密度（深度教導、多層次概念、實作指引）
  - `medium` - 中等（平衡論述、有實質洞見）
  - `low` - 低密度（閒聊、缺乏深度內容）

### 5. temporal_relevance (列舉字串，必填)
- **說明**: 內容時效性
- **可選值** (嚴格選一):
  - `evergreen` - 長期有效（永恆真理、基礎練習）
  - `time_sensitive` - 時效性內容（當前能量更新、時事靈性觀點）
  - `news` - 新聞（特定活動、即時傳訊）

### 6. key_entities (字串陣列，必填)
- **說明**: 關鍵實體（導師、靈性概念、練習方法、書籍參考）
- **格式**: 使用 [[雙括號]] 包圍，便於建立知識連結
- **範例**: ["[[Eckhart Tolle]]", "[[當下的力量]]", "[[脈輪]]", "[[高我]]", "[[冥想]]"]
- **提示**: 包含導師名稱、靈性概念、練習技巧、書籍、能量中心名稱

### 7. segments (物件陣列，必填)
- **說明**: 影片結構分段，識別 3-7 個主要段落
- **每個 segment 欄位**:
  - `section_type` (列舉字串): 段落類型
    - `intro` - 開場/引入主題
    - `key_point` - 核心教導/洞見
    - `detail` - 細節說明/練習指引
    - `conclusion` - 總結/祝福
  - `title` (字串): 段落標題，20 字以內，簡潔描述該段主題
  - `start_quote` (字串): 段落起始錨點文字，10-20 字，用於定位

## 輸出格式 (嚴格 JSON)

請輸出符合以下格式的 JSON，**不要**加入任何其他文字說明：

```json
{
  "semantic_summary": "100-200 字中文摘要...",
  "key_topics": ["主題1", "主題2", "主題3"],
  "content_type": "educational",
  "content_density": "high",
  "temporal_relevance": "evergreen",
  "key_entities": ["[[實體1]]", "[[實體2]]"],
  "segments": [
    {
      "section_type": "intro",
      "title": "主題引入",
      "start_quote": "今天我們來談談..."
    },
    {
      "section_type": "key_point",
      "title": "核心教導",
      "start_quote": "關鍵在於..."
    },
    {
      "section_type": "detail",
      "title": "練習指引",
      "start_quote": "你可以這樣練習..."
    },
    {
      "section_type": "conclusion",
      "title": "總結祝福",
      "start_quote": "願你..."
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
