# 遙視預測內容分析提示詞

請分析以下遙視/預測相關影片轉錄稿，並嚴格按照指定格式輸出 JSON。

## 影片資訊
- 頻道: {channel}
- 標題: {title}
- 檔案: {file_path}

## 分析任務

請閱讀轉錄稿後，提取以下結構化資訊：

### 1. semantic_summary (字串，必填)
- **說明**: 內容摘要，100-200 字中文摘要
- **重點**: 概述遙視目標、預測時間範圍和關鍵發現
- **範例**: "團隊對 2025 年重大事件進行遙視，觀察到與氣候變遷和地緣政治相關的關鍵影像，時間線落在年中至年底..."

### 2. key_topics (字串陣列，必填)
- **說明**: 關鍵主題標籤，3-5 個
- **格式**: 每個標籤 30 字元以內，簡潔明確
- **範例**: ["遙視目標", "時間線預測", "關鍵影像", "集體意識", "預測驗證"]

### 3. content_type (列舉字串，必填)
- **說明**: 內容類型分類
- **可選值** (嚴格選一):
  - `technical_analysis` - 技術分析（遙視方法論、數據分析）
  - `opinion_discussion` - 觀點討論（預測解讀、可能性探討）
  - `news` - 新聞報導（最新遙視結果發布）
  - `educational` - 教育教學（遙視技巧教學、方法說明）
  - `interview` - 訪談對話（遙視員分享、專家討論）

### 4. content_density (列舉字串，必填)
- **說明**: 資訊密度評估
- **可選值** (嚴格選一):
  - `high` - 高密度（詳細遙視數據、多重驗證、具體時間標記）
  - `medium` - 中等（有具體影像描述、時間範圍）
  - `low` - 低密度（模糊描述、缺乏細節）

### 5. temporal_relevance (列舉字串，必填)
- **說明**: 內容時效性
- **可選值** (嚴格選一):
  - `evergreen` - 長期有效（遙視方法論、歷史案例分析）
  - `time_sensitive` - 時效性內容（未來預測、當前進行中事件）
  - `news` - 新聞（最新遙視會議結果）

### 6. key_entities (字串陣列，必填)
- **說明**: 關鍵實體（遙視目標、相關事件、地點、時間標記）
- **格式**: 使用 [[雙括號]] 包圍，便於建立知識連結
- **範例**: ["[[Courtney Brown]]", "[[Farsight Institute]]", "[[時間線]]", "[[目標座標]]", "[[2025 預測]]"]
- **提示**: 包含遙視機構、主持人、特定目標名稱、時間標記、地點

### 7. segments (物件陣列，必填)
- **說明**: 影片結構分段，識別 3-7 個主要段落
- **每個 segment 欄位**:
  - `section_type` (列舉字串): 段落類型
    - `intro` - 開場/目標設定
    - `key_point` - 核心發現/預測
    - `detail` - 細節描述/影像細節
    - `conclusion` - 總結/可能性評估
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
      "title": "目標設定",
      "start_quote": "今天的遙視目標是..."
    },
    {
      "section_type": "key_point",
      "title": "核心發現",
      "start_quote": "我們觀察到的關鍵影像..."
    },
    {
      "section_type": "detail",
      "title": "影像細節",
      "start_quote": "具體來說，我看到..."
    },
    {
      "section_type": "conclusion",
      "title": "可能性評估",
      "start_quote": "綜合所有數據..."
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
