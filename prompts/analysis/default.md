# 通用內容分析提示詞

請分析以下 YouTube 影片轉錄稿，並嚴格按照指定格式輸出 JSON。

## 影片資訊
- 頻道: {channel}
- 標題: {title}
- 檔案: {file_path}

## 分析任務

請閱讀轉錄稿後，提取以下結構化資訊：

### 1. semantic_summary (字串，必填)
- **說明**: 內容摘要，100-200 字中文摘要
- **重點**: 概括核心論點、主要內容和關鍵結論
- **範例**: "講者探討了當前市場趨勢與未來發展方向，強調了幾個關鍵因素..."

### 2. key_topics (字串陣列，必填)
- **說明**: 關鍵主題標籤，3-5 個
- **格式**: 每個標籤 30 字元以內，簡潔明確
- **範例**: ["主題一", "主題二", "主題三", "主題四"]

### 3. content_type (列舉字串，必填)
- **說明**: 內容類型分類
- **可選值** (嚴格選一):
  - `technical_analysis` - 技術分析（數據、方法論分析）
  - `opinion_discussion` - 觀點討論（個人看法、評論）
  - `news` - 新聞報導（事件報導、公告）
  - `educational` - 教育教學（概念解釋、教學）
  - `interview` - 訪談對話（嘉賓對談、問答）

### 4. content_density (列舉字串，必填)
- **說明**: 資訊密度評估
- **可選值** (嚴格選一):
  - `high` - 高密度（大量資訊、深入分析、專業術語密集）
  - `medium` - 中等（平衡論述、有實質內容）
  - `low` - 低密度（閒聊、雜訊多、缺乏實質內容）

### 5. temporal_relevance (列舉字串，必填)
- **說明**: 內容時效性
- **可選值** (嚴格選一):
  - `evergreen` - 長期有效（基礎概念、長期原則）
  - `time_sensitive` - 時效性內容（短期分析、當前趨勢）
  - `news` - 新聞（特定事件，時效性最強）

### 6. key_entities (字串陣列，必填)
- **說明**: 關鍵實體（人物、組織、概念、專有名詞）
- **格式**: 使用 [[雙括號]] 包圍，便於建立知識連結
- **範例**: ["[[實體一名稱]]", "[[實體二名稱]]", "[[組織名稱]]"]
- **提示**: 包含重要人物、機構、核心概念、專業術語

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
  "content_type": "opinion_discussion",
  "content_density": "medium",
  "temporal_relevance": "evergreen",
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
    },
    {
      "section_type": "conclusion",
      "title": "總結",
      "start_quote": "總而言之..."
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
