# UFO/UAP 研究內容分析提示詞

請分析以下 UFO/UAP 相關影片轉錄稿，並嚴格按照指定格式輸出 JSON。

## 影片資訊
- 頻道: {channel}
- 標題: {title}
- 檔案: {file_path}

## 分析任務

請閱讀轉錄稿後，提取以下結構化資訊：

### 1. semantic_summary (字串，必填)
- **說明**: 內容摘要，100-200 字中文摘要
- **重點**: 概括影片的主要論點、證據和核心主張
- **範例**: "講者論證 MH370 熱影像與核融合推進的關聯，引用目擊者證詞和政府文件，探討先進推進技術的可能性..."

### 2. key_topics (字串陣列，必填)
- **說明**: 關鍵主題標籤，3-5 個
- **格式**: 每個標籤 30 字元以內，簡潔明確
- **範例**: ["UFO 目擊", "政府揭露", "先進推進", "目擊者證詞", "官方文件"]

### 3. content_type (列舉字串，必填)
- **說明**: 內容類型分類
- **可選值** (嚴格選一):
  - `technical_analysis` - 技術分析（推進技術、物理分析）
  - `opinion_discussion` - 觀點討論（理論推測、觀點交鋒）
  - `news` - 新聞報導（最新事件、聽證會報導）
  - `educational` - 教育教學（歷史回顧、概念解釋）
  - `interview` - 訪談對話（目擊者訪談、專家對談）

### 4. content_density (列舉字串，必填)
- **說明**: 資訊密度評估
- **可選值** (嚴格選一):
  - `high` - 高密度（大量目擊證據、文件引用、技術細節）
  - `medium` - 中等（平衡論述、有證據支撐）
  - `low` - 低密度（猜測為主、缺乏實證）

### 5. temporal_relevance (列舉字串，必填)
- **說明**: 內容時效性
- **可選值** (嚴格選一):
  - `evergreen` - 長期有效（歷史案例、基礎概念）
  - `time_sensitive` - 時效性內容（當前調查進展、新聞）
  - `news` - 新聞（最新聽證會、官方公告）

### 6. key_entities (字串陣列，必填)
- **說明**: 關鍵實體（人物、組織、事件、技術名稱）
- **格式**: 使用 [[雙括號]] 包圍，便於建立知識連結
- **範例**: ["[[Irving Langmuir]]", "[[Los Alamos]]", "[[AARO]]", "[[Grusch]]", "[[Tic Tac UFO]]"]
- **提示**: 包含調查人員、政府機構、目擊者、特定事件名稱、技術術語

### 7. segments (物件陣列，必填)
- **說明**: 影片結構分段，識別 3-7 個主要段落
- **每個 segment 欄位**:
  - `section_type` (列舉字串): 段落類型
    - `intro` - 開場/背景介紹
    - `key_point` - 核心論點/證據
    - `detail` - 細節說明/案例
    - `conclusion` - 總結/呼籲
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
      "title": "背景介紹",
      "start_quote": "今天我們要探討的是..."
    },
    {
      "section_type": "key_point",
      "title": "核心證據",
      "start_quote": "關鍵證據顯示..."
    },
    {
      "section_type": "detail",
      "title": "案例細節",
      "start_quote": "具體來說..."
    },
    {
      "section_type": "conclusion",
      "title": "結論與呼籲",
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
