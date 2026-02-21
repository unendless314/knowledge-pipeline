# Discovery Pending Check 優化方案

> **文件類型**: 技術規劃文件  
> **建立日期**: 2026-02-20  
> **關聯問題**: 避免 LLM 分析階段因程式中斷而導致的重工問題  
> **實作難度**: ⭐⭐ 低  
> **預估工時**: 1-2 小時

---

## 1. 問題背景

### 1.1 現有行為

目前 Pipeline 的執行流程：

```
Discovery Phase
    ↓ 讀取所有無 status 的檔案
Analysis Phase
    ↓ 分析完成後寫入 intermediate/pending/
Upload Phase
    ↓ 上傳後標記 status，檔案移至 approved/
```

### 1.2 問題情境

當 Analysis Phase 因網路斷線、API 錯誤或人為中斷時：

1. `intermediate/pending/` 目錄中已有部分分析完成的檔案
2. 但上游檔案的 `status` 欄位仍為空
3. 下次執行時，Discovery 會**再次發現這些檔案**
4. 導致已分析的檔案被**重新分析**，浪費 Gemini API 配額

---

## 2. 解決方案

### 2.1 方案概述

**方案 B：Discovery 檢查 pending（推薦）**

讓 DiscoveryService 在判斷檔案是否應該處理時，額外檢查對應的 pending 檔案是否已經存在。若存在則跳過，避免重工。

### 2.2 優點

- ✅ **不污染上游**：不修改 youtube_transcriber 的輸出檔案
- ✅ **符合單一職責**：Analyzer 只分析，Discovery 負責發現與過濾
- ✅ **健壯性高**：即使上游檔案被刪除/重建，intermediate 狀態仍有效

---

## 3. 實作規劃

### 3.1 修改檔案清單

| 檔案 | 修改類型 | 說明 |
|------|---------|------|
| `src/discovery.py` | 修改 | 新增 intermediate 路徑檢查邏輯 |
| `src/main.py` | 修改 | 初始化時傳入 intermediate 路徑 |

### 3.2 詳細修改內容

#### 修改 1: `src/discovery.py`

**位置**: `DiscoveryService.__init__()`

新增 `intermediate_dir` 參數：

```python
def __init__(
    self,
    scanner: FileScanner | None = None,
    parser: FrontmatterParser | None = None,
    extractor: TranscriptMetadataExtractor | None = None,
    status_checker: StatusChecker | None = None,
    file_filter: FileFilter | None = None,
    temp_dir: Path | None = None,
    intermediate_dir: Path | None = None,  # ← 新增
):
    # ... 現有程式碼 ...
    self.intermediate_dir = intermediate_dir  # ← 新增
```

---

**位置**: `FileFilter.should_process()`

新增 pending 檔案存在性檢查：

```python
def should_process(
    self,
    metadata: TranscriptMetadata,
    frontmatter: dict,
    filepath: Path,
    intermediate_dir: Path | None = None,  # ← 新增參數
) -> tuple[bool, str | None]:
    """
    判斷檔案是否應該處理
    
    新增邏輯：
    - 檢查對應的 intermediate/pending/ 檔案是否已存在
    - 若存在，視為已處理，避免重工
    """
    # 1. 檢查原有 status
    if self.status_checker.is_processed(frontmatter):
        status = self.status_checker.get_status(frontmatter)
        return False, f"已處理 (status={status.value})"
    
    # 2. 新增：檢查 pending 檔案是否存在 ←
    if intermediate_dir and self._is_pending_file_exists(
        metadata, intermediate_dir
    ):
        return False, "已分析 (pending 檔案已存在)"
    
    # 3. 檢查字數
    if metadata.word_count < self.min_word_count:
        return False, f"字數不足 ({metadata.word_count} < {self.min_word_count})"
    
    return True, None

def _is_pending_file_exists(
    self,
    metadata: TranscriptMetadata,
    intermediate_dir: Path
) -> bool:
    """
    檢查對應的 pending 檔案是否已存在
    
    檔案命名格式：
    intermediate/pending/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
    """
    year_month = metadata.published_at.strftime("%Y-%m")
    
    # 產生 slug（需與 analyzer.py 的邏輯一致）
    slug = self._slugify(metadata.title, max_length=50)
    
    # 構建預期的 pending 檔案路徑
    pending_file = (
        intermediate_dir
        / "pending"
        / metadata.channel
        / year_month
        / f"{metadata.published_at.strftime('%Y%m%d')}_{metadata.video_id}_{slug}_analyzed.md"
    )
    
    return pending_file.exists()

def _slugify(self, text: str, max_length: int = 50) -> str:
    """將標題轉換為 slug（與 analyzer.py 的 _slugify 方法一致）"""
    import re
    slug = re.sub(r"[^\w\s-]", "", text)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:max_length].strip("-")
```

---

**位置**: `DiscoveryService.discover()`

修改呼叫 `should_process()` 的地方，傳入 `intermediate_dir`：

```python
# 檢查是否應該處理
should_process, reason = self.file_filter.should_process(
    metadata, frontmatter, file_path,
    self.intermediate_dir  # ← 新增傳入
)
```

---

#### 修改 2: `src/main.py`

**位置**: `KnowledgePipeline.__init__()`

初始化 DiscoveryService 時傳入 `intermediate_dir`：

```python
# 初始化各個服務
# 修改前：
# self.discovery = DiscoveryService()

# 修改後：
self.discovery = DiscoveryService(
    intermediate_dir=Path(self.config.intermediate)  # ← 新增
)
```

---

### 3.3 流程圖

```
Before Optimization:
┌─────────────────┐
│   Discovery     │─── 掃描所有無 status 的檔案
│                 │     (不認識 pending 目錄)
└────────┬────────┘
         │ 58 個檔案（全部）
         ▼
┌─────────────────┐
│   Analysis      │─── 分析到第 30 個時崩潰
│                 │     （前面 30 個已寫入 pending）
└────────┬────────┘
         │ 程式重啟
         ▼
┌─────────────────┐
│   Discovery     │─── 又發現 58 個檔案 ❌
│                 │     （重工問題）
└─────────────────┘

After Optimization:
┌─────────────────┐
│   Discovery     │─── 掃描所有無 status 的檔案
│                 │     (同時檢查 pending 目錄)
└────────┬────────┘
         │ 58 個檔案
         │
         │ 檢查：30 個在 pending 已存在
         │
         ▼
    28 個新檔案
         │
         ▼
┌─────────────────┐
│   Analysis      │─── 分析到第 15 個時崩潰
│                 │     （前面 15 個已寫入 pending）
└────────┬────────┘
         │ 程式重啟
         ▼
┌─────────────────┐
│   Discovery     │─── 發現 58 個檔案
│                 │     但 45 個（30+15）在 pending 已存在
│                 │     只處理剩餘 13 個 ✅
└─────────────────┘
```

---

## 4. 注意事項

### 4.1 slug 產生邏輯一致性

**重要**：`FileFilter._slugify()` 必須與 `AnalyzerService._slugify()` 的邏輯**完全一致**，否則會導致檔案路徑不匹配。

建議：
- 將 `_slugify()` 提取為共用工具函數（`src/utils.py`）
- 或至少確保兩處的實作完全相同

### 4.2 統計資訊更新

`DiscoveryStatistics` 需要新增一個欄位來記錄因 pending 檔案存在而跳過的數量：

```python
@dataclass
class DiscoveryStatistics:
    # ... 現有欄位 ...
    filtered_by_pending: int = 0  # ← 新增
```

並在 `main.py` 的 `run_discovery()` 中輸出此統計。

### 4.3 向下相容性

若 `intermediate_dir` 為 `None`（預設值），則跳過 pending 檢查，保持現有行為。這確保了：
- 現有單元測試無需修改
- 第三方使用 `DiscoveryService` 時不會被強制要求提供 intermediate 路徑

---

## 5. 測試建議

### 5.1 單元測試

```python
# test_discovery.py 新增測試案例

def test_should_skip_if_pending_file_exists():
    """測試：若 pending 檔案已存在，應該跳過"""
    # 建立模擬的 pending 檔案
    # 呼叫 discover()
    # 驗證該檔案不在結果中

def test_should_process_if_pending_file_not_exists():
    """測試：若 pending 檔案不存在，應該處理"""
    # 驗證新檔案會被發現

def test_slugify_consistency():
    """測試：slug 產生邏輯與 analyzer 一致"""
    # 驗證特殊字元、長度限制等行為一致
```

### 5.2 整合測試

1. 執行分析階段到一半時中斷
2. 重新執行完整流程
3. 驗證只有未分析的檔案被送入 Analysis Phase

---

## 6. 相關程式碼參考

### 6.1 Analyzer 產生檔案路徑的邏輯

位置：`src/analyzer.py:473-504`

```python
def _build_output_path(self, output_dir: Path, transcript: TranscriptFile) -> Path:
    year_month = transcript.metadata.published_at.strftime("%Y-%m")
    slug = self._slugify(transcript.metadata.title, max_length=50)
    filename = (
        f"{transcript.metadata.published_at.strftime('%Y%m%d')}"
        f"_{transcript.metadata.video_id}"
        f"_{slug}"
        f"_analyzed.md"
    )
    return output_dir / transcript.metadata.channel / year_month / filename
```

### 6.2 現有的 FileFilter 邏輯

位置：`src/discovery.py:434-514`

---

## 7. 執行檢查清單

- [ ] 修改 `src/discovery.py`
  - [ ] `DiscoveryService.__init__()` 新增 `intermediate_dir` 參數
  - [ ] `FileFilter.should_process()` 新增 pending 檢查邏輯
  - [ ] 新增 `_is_pending_file_exists()` 輔助方法
  - [ ] 新增 `_slugify()` 方法（或提取為共用函數）
  - [ ] 更新 `discover()` 中的呼叫
  - [ ] 更新 `DiscoveryStatistics` 統計欄位
- [ ] 修改 `src/main.py`
  - [ ] `KnowledgePipeline.__init__()` 傳入 `intermediate_dir`
  - [ ] 更新 `run_discovery()` 統計輸出
- [ ] 新增/更新單元測試
- [ ] 手動測試驗證
  - [ ] 正常流程不受影響
  - [ ] 中斷後重工問題已解決

---

## 8. 附錄

### 檔案命名對照表

| 欄位 | 來源 |
|------|------|
| `published_at` | `metadata.published_at` (date 物件) |
| `video_id` | `metadata.video_id` |
| `channel` | `metadata.channel` |
| `slug` | `title` 經 `_slugify()` 處理 |
| `year_month` | `published_at.strftime("%Y-%m")` |

### 完整路徑格式

```
{intermediate_dir}/pending/{channel}/{YYYY-MM}/{YYYYMMDD}_{video_id}_{slug}_analyzed.md

範例：
./intermediate/pending/Bankless/2026-02/20260215_abc12345xyz_AI-on-Ethereum_analyzed.md
```
