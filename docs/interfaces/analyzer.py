"""
Knowledge Pipeline - Analyzer 模組介面定義

此模組負責使用 LLM 對轉錄內容進行語意分析，
提取結構化 metadata 並產出增強版 Markdown 檔案。

重要：Analyzer 不再直接與特定 LLM 實作耦合，
而是透過 src.llm.LLMClient 使用抽象的 LLMProvider。

依賴關係:
    analyzer.py
        └── src.llm (LLMClient, LLMProvider)
            ├── GeminiCLIProvider (目前實作)
            ├── OpenAIProvider (預留)
            └── ...

參考實作: src/analyzer/analyzer.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .llm import LLMClientInterface, TranscriptInput, AnalysisResult
from .models import TranscriptFile, AnalyzedTranscript, ProcessingMetadata


# ============================================================================
# 核心 Analyzer 介面
# ============================================================================

class AnalyzerService(Protocol):
    """
    分析服務介面
    
    整合 prompt 載入、LLM 呼叫、結果解析、Markdown 建構的高階 API。
    
    使用範例:
        from src.analyzer import AnalyzerService
        from src.llm import LLMClient
        
        llm_client = LLMClient.from_config(config.llm)
        analyzer = AnalyzerService(llm_client=llm_client)
        
        result = analyzer.analyze(transcript_file, prompt_template="crypto_tech")
    """
    
    def __init__(self, llm_client: LLMClientInterface) -> None:
        """
        初始化 Analyzer
        
        Args:
            llm_client: LLM 客戶端實例（含具體 Provider）
        """
        ...
    
    def analyze(
        self,
        transcript: TranscriptFile,
        prompt_template: str = "default",
        output_dir: Path | None = None
    ) -> AnalyzedTranscript | None:
        """
        分析單個轉錄檔案
        
        完整流程：
        1. 將 TranscriptFile 轉換為 TranscriptInput
        2. 載入 prompt template 並格式化
        3. 確定輸出路徑（若未指定則使用 intermediate/pending/）
        4. 呼叫 LLMClient 執行分析
        5. （可選）執行結構化分段（inject_headers）
        6. 構建增強版 Markdown
        7. 儲存到指定目錄
        8. 回傳 AnalyzedTranscript
        
        Args:
            transcript: 待分析的轉錄檔案
            prompt_template: 使用的 prompt template 名稱（如 "crypto_tech"）
            output_dir: 輸出目錄，預設使用 config 中的 intermediate/pending
        
        Returns:
            AnalyzedTranscript 或 None（分析失敗時）
        
        Raises:
            LLMCallError: LLM 呼叫失敗
            LLMTimeoutError: 呼叫超時
        """
        ...
    
    def analyze_batch(
        self,
        transcripts: list[TranscriptFile],
        prompt_template: str = "default",
        output_dir: Path | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        delay_between_calls: float = 1.0
    ) -> list[AnalyzedTranscript]:
        """
        批次分析多個轉錄檔案
        
        ⚠️ 注意：因 LLM 通常有 rate limiting（如 Gemini 免費版 1000 calls/day），
        建議批次處理時加入適當延遲（預設每個檔案間隔 1 秒）。
        
        Args:
            transcripts: 待分析的轉錄檔案列表
            prompt_template: 使用的 prompt template 名稱
            output_dir: 輸出目錄
            progress_callback: 進度回呼函數 (current, total, status) -> None
            delay_between_calls: 每次呼叫間隔秒數（避免 rate limit）
        
        Returns:
            分析成功的 AnalyzedTranscript 列表
        """
        ...
    
    def build_analyzed_markdown(
        self,
        transcript: TranscriptFile,
        analysis_result: AnalysisResult,
        processing_meta: ProcessingMetadata
    ) -> str:
        """
        構建增強版 Markdown 內容
        
        輸出格式：
        ```yaml
        ---
        # === 原始資訊 ===
        channel: "Bankless"
        video_id: "xxx"
        title: "..."
        ...

        # === 語意分析結果 ===
        semantic_summary: "..."
        key_topics:
          - "ERC-8004"
          - "AI Agents"
        ...

        # === 處理中繼資料 ===
        analyzed_by: "gemini_cli/gemini-2.5-pro"
        analyzed_at: "2026-02-11T10:00:00"
        pipeline_version: "1.0.0"
        ---

        [結構化後的轉錄內容（含 injected headers）]
        ```
        
        Args:
            transcript: 原始轉錄檔案
            analysis_result: LLM 分析結果
            processing_meta: 處理中繼資料
        
        Returns:
            完整的 Markdown 內容字串
        """
        ...


# ============================================================================
# 結構化分段處理器介面
# ============================================================================

class StructuredSegmentation(Protocol):
    """
    結構化分段處理器介面
    
    執行「LLM 定位 + Python 執刀」的結構化分段策略：
    1. LLM 分析產生 segments（含 start_quote 錨點）
    2. Python 在原始內容中搜尋 start_quote
    3. 在匹配位置插入 Markdown 標題
    
    此處理在 LLM 分析後、Markdown 建構前執行。
    """
    
    def inject_headers(
        self,
        content: str,
        segments: list[dict]
    ) -> str:
        """
        在內容中插入 Markdown 標題
        
        Args:
            content: 原始轉錄內容
            segments: 分段資訊列表（從 analysis_result.segments 取得）
                每個 segment 格式：
                {
                    "section_type": "key_point",
                    "title": "ERC-8004 簡介",
                    "start_quote": "So what exactly is ERC-8004?"
                }
        
        Returns:
            插入標題後的內容
        
        實作注意：
        - 使用 fuzzy match 或 exact match 搜尋 start_quote
        - 在匹配位置上方插入 `## [Key Point] {title}`
        - 若找不到錨點，可選擇跳過或記錄警告
        """
        ...
    
    def find_quote_position(self, content: str, quote: str, fuzzy: bool = True) -> int | None:
        """
        在內容中搜尋錨點位置
        
        Args:
            content: 原始內容
            quote: 錨點文字
            fuzzy: 是否使用模糊匹配
        
        Returns:
            字元位置索引，或 None（未找到）
        """
        ...


# ============================================================================
# 輔助類別
# ============================================================================

@dataclass
class AnalysisConfig:
    """
    Analyzer 配置
    
    Attributes:
        llm_client: LLM 客戶端（必須）
        default_template: 預設 prompt template
        enable_segmentation: 是否啟用結構化分段
        output_dir: 預設輸出目錄
    """
    llm_client: LLMClientInterface
    default_template: str = "default"
    enable_segmentation: bool = True
    output_dir: Path | None = None


# ============================================================================
# 例外定義
# ============================================================================

class AnalyzerError(Exception):
    """Analyzer 模組錯誤基類"""
    pass


class AnalysisFailedError(AnalyzerError):
    """分析失敗（LLM 回傳無效結果）"""
    
    def __init__(self, message: str, transcript_path: Path | None = None):
        super().__init__(message)
        self.transcript_path = transcript_path


class SegmentationError(AnalyzerError):
    """結構化分段失敗"""
    pass


# ============================================================================
# 實作指導
# ============================================================================

"""
實作指南與最佳實踐

## 1. AnalyzerService 實作範本

```python
@dataclass
class AnalyzerService:
    '''
    分析服務實作
    
    使用範例:
        from src.llm import LLMClient
        
        llm_client = LLMClient.from_config(config.llm)
        analyzer = AnalyzerService(llm_client=llm_client)
        
        result = analyzer.analyze(
            transcript_file,
            prompt_template="crypto_tech",
            output_dir=Path("intermediate/pending")
        )
    '''
    
    llm_client: LLMClientInterface
    enable_segmentation: bool = True
    
    def analyze(
        self,
        transcript: TranscriptFile,
        prompt_template: str = "default",
        output_dir: Path | None = None
    ) -> AnalyzedTranscript | None:
        '''
        分析單個轉錄檔案
        
        完整流程:
        1. TranscriptFile -> TranscriptInput 轉換
        2. 確定輸出路徑
        3. 呼叫 LLMClient 進行分析
        4. （可選）執行結構化分段
        5. 構建增強版 Markdown
        6. 儲存到指定目錄
        7. 回傳 AnalyzedTranscript
        '''
        try:
            # Step 1: 轉換為 LLM 輸入格式
            input_data = self._to_transcript_input(transcript)
            
            # Step 2: 確定輸出路徑
            if output_dir is None:
                output_dir = self._get_default_output_dir(transcript)
            output_path = self._build_output_path(output_dir, transcript)
            
            # Step 3: 執行 LLM 分析（核心步驟）
            # 注意：這裡交給 LLMClient 處理 temp/ 檔案和清理
            analysis_result = self.llm_client.analyze(
                input_data=input_data,
                prompt_template=prompt_template,
                output_path=output_path.parent / f"{output_path.stem}_llm_log.md"
            )
            
            # Step 4: （可選）結構化分段
            content = transcript.content
            if self.enable_segmentation and analysis_result.segments:
                content = self._inject_headers(content, analysis_result.segments)
            
            # Step 5: 構建處理中繼資料
            processing_meta = ProcessingMetadata(
                analyzed_by=f"{analysis_result.provider}/{analysis_result.model}",
                analyzed_at=datetime.now(),
                pipeline_version="1.0.0",
                source_path=str(transcript.path)
            )
            
            # Step 6: 構建最終 Markdown
            markdown_content = self._build_analyzed_markdown(
                original=transcript.metadata,
                analysis=analysis_result,
                processing=processing_meta,
                content=content
            )
            
            # Step 7: 寫入檔案
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            
            # Step 8: 回傳結果
            return AnalyzedTranscript(
                original=transcript.metadata,
                analysis=analysis_result,
                processing=processing_meta,
                status=PipelineStatus.PENDING,
                source_id=None
            )
            
        except (LLMCallError, LLMTimeoutError, LLMRateLimitError) as e:
            # 轉換 LLM 例外為 Analyzer 例外
            raise AnalysisFailedError(
                f"LLM analysis failed: {e}",
                transcript_path=transcript.path
            ) from e
    
    def _to_transcript_input(self, transcript: TranscriptFile) -> TranscriptInput:
        '''將 TranscriptFile 轉換為 TranscriptInput'''
        return TranscriptInput(
            channel=transcript.metadata.channel,
            title=transcript.metadata.title,
            content=transcript.content,
            published_at=transcript.metadata.published_at.isoformat(),
            word_count=transcript.metadata.word_count,
            file_path=transcript.path,
            video_id=transcript.metadata.video_id,
            duration=transcript.metadata.duration
        )
    
    def _build_output_path(self, output_dir: Path, transcript: TranscriptFile) -> Path:
        '''
        建構輸出檔案路徑
        
        格式: intermediate/pending/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
        '''
        # 從 published_at 提取年月
        year_month = transcript.metadata.published_at.strftime("%Y-%m")
        
        # 產生 slug（標題的簡化版本）
        slug = self._slugify(transcript.metadata.title, max_length=50)
        
        # 檔名格式
        filename = (
            f"{transcript.metadata.published_at.strftime('%Y%m%d')}"
            f"_{transcript.metadata.video_id}"
            f"_{slug}"
            f"_analyzed.md"
        )
        
        return output_dir / transcript.metadata.channel / year_month / filename
    
    def _slugify(self, text: str, max_length: int = 50) -> str:
        '''將標題轉換為 slug'''
        # 移除非 alphanumeric 字元，保留 hyphen
        import re
        slug = re.sub(r'[^\w\s-]', '', text)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:max_length].strip('-')
```

## 2. build_analyzed_markdown 實作範本

```python
def _build_analyzed_markdown(
    self,
    original: TranscriptMetadata,
    analysis: AnalysisResult,
    processing: ProcessingMetadata,
    content: str
) -> str:
    '''
    構建增強版 Markdown
    
    輸出格式：
    ```yaml
    ---
    # === 原始資訊 ===
    channel: "Bankless"
    video_id: "h7zj0SDWmkw"
    title: "AI on Ethereum..."
    published_at: "2026-02-05"
    duration: "1:37:18"
    word_count: 97688

    # === 語意分析結果 ===
    semantic_summary: "深入解析 ERC-8004..."
    key_topics:
      - "ERC-8004"
      - "AI Agents"
    suggested_topic: "Crypto_Finance"
    content_type: "technical_analysis"
    content_density: "high"
    temporal_relevance: "time_sensitive"
    segments: [...]
    key_entities:
      - "[[ERC-8004]]"
      - "[[x402]]"

    # === 處理中繼資料 ===
    analyzed_by: "gemini_cli/gemini-2.5-pro"
    analyzed_at: "2026-02-11T10:00:00+08:00"
    pipeline_version: "1.0.0"
    source_path: "Bankless/2026-02/..."
    ---

    [轉錄內容（可能含 injected headers）]
    ```
    '''
    import yaml
    
    # 組合 frontmatter
    frontmatter = {
        # 原始資訊
        "channel": original.channel,
        "video_id": original.video_id,
        "title": original.title,
        "published_at": original.published_at.isoformat(),
        "duration": original.duration,
        "word_count": original.word_count,
        
        # 語意分析結果
        "semantic_summary": analysis.semantic_summary,
        "key_topics": analysis.key_topics,
        "suggested_topic": analysis.suggested_topic,
        "content_type": analysis.content_type,
        "content_density": analysis.content_density,
        "temporal_relevance": analysis.temporal_relevance,
        "dialogue_format": analysis.dialogue_format,
        "segments": analysis.segments,
        "key_entities": analysis.key_entities,
        
        # 處理中繼資料
        "analyzed_by": processing.analyzed_by,
        "analyzed_at": processing.analyzed_at.isoformat(),
        "pipeline_version": processing.pipeline_version,
        "source_path": processing.source_path,
        
        # Pipeline 狀態
        "status": "pending",
        "source_id": None,
    }
    
    # 序列化 YAML
    yaml_content = yaml.dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,  # 保持欄位順序
        default_flow_style=False
    )
    
    # 組合最終 Markdown
    return f"""---
{yaml_content}---

{content}
"""
```

## 3. StructuredSegmentation 實作範本

```python
class StructuredSegmentation:
    '''結構化分段處理器'''
    
    def inject_headers(
        self,
        content: str,
        segments: list[dict]
    ) -> str:
        '''
        在內容中插入 Markdown 標題
        
        Args:
            content: 原始轉錄內容
            segments: 分段資訊列表
                [
                    {"section_type": "key_point", "title": "ERC-8004 簡介", "start_quote": "So what exactly..."},
                    ...
                ]
        
        Returns:
            插入標題後的內容
        '''
        # 從後往前插入，避免位置偏移問題
        insertions = []
        
        for segment in segments:
            # 搜尋錨點位置
            pos = self.find_quote_position(content, segment["start_quote"])
            if pos is not None:
                # 找到段落起始位置（行首）
                line_start = content.rfind('\\n', 0, pos) + 1
                
                # 準備標題
                header = f"## [{segment['section_type'].upper()}] {segment['title']}\\n\\n"
                insertions.append((line_start, header))
        
        # 按位置排序（從後往前）
        insertions.sort(key=lambda x: x[0], reverse=True)
        
        # 執行插入
        result = content
        for pos, header in insertions:
            result = result[:pos] + header + result[pos:]
        
        return result
    
    def find_quote_position(self, content: str, quote: str, fuzzy: bool = True) -> int | None:
        '''
        在內容中搜尋錨點位置
        
        Args:
            content: 原始內容
            quote: 錨點文字（約 10-20 字）
            fuzzy: 是否使用模糊匹配
        
        Returns:
            字元位置索引，或 None（未找到）
        '''
        # 精確匹配
        pos = content.find(quote)
        if pos != -1:
            return pos
        
        if not fuzzy:
            return None
        
        # 模糊匹配：允許 minor 差異
        # 實作策略：使用 difflib.SequenceMatcher 或正規化後匹配
        import difflib
        
        best_ratio = 0.0
        best_pos = None
        
        # 簡化實作：搜尋 quote 的前 10 個字
        search_prefix = quote[:10]
        start = 0
        
        while True:
            pos = content.find(search_prefix, start)
            if pos == -1:
                break
            
            # 計算相似度
            candidate = content[pos:pos + len(quote) + 20]  # 多取一點
            ratio = difflib.SequenceMatcher(None, quote, candidate).ratio()
            
            if ratio > best_ratio and ratio > 0.8:  # 閾值 0.8
                best_ratio = ratio
                best_pos = pos
            
            start = pos + 1
        
        return best_pos
```

## 4. 批次處理實作範本

```python
def analyze_batch(
    self,
    transcripts: list[TranscriptFile],
    prompt_template: str = "default",
    output_dir: Path | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    delay_between_calls: float = 1.0
) -> list[AnalyzedTranscript]:
    '''
    批次分析多個轉錄檔案
    
    使用範例:
        def on_progress(current, total, status):
            print(f"{current}/{total}: {status}")
        
        results = analyzer.analyze_batch(
            transcripts,
            prompt_template="crypto_tech",
            progress_callback=on_progress,
            delay_between_calls=2.0  # 避免 rate limit
        )
    '''
    results = []
    total = len(transcripts)
    
    for i, transcript in enumerate(transcripts, 1):
        try:
            if progress_callback:
                progress_callback(i, total, f"Analyzing {transcript.metadata.title[:50]}...")
            
            result = self.analyze(transcript, prompt_template, output_dir)
            if result:
                results.append(result)
                
                # 避免 rate limit
                if i < total and delay_between_calls > 0:
                    import time
                    time.sleep(delay_between_calls)
                    
        except AnalysisFailedError as e:
            logger.error(f"Failed to analyze {transcript.path}: {e}")
            # 繼續處理下一個
            continue
    
    if progress_callback:
        progress_callback(total, total, f"Completed {len(results)}/{total}")
    
    return results
```

## 5. 常見陷阱與避免方式

| 陷阱 | 錯誤示範 | 正確做法 |
|------|----------|----------|
| 直接修改原始檔案 | `transcript.path.write_text(...)` | 寫入新的 `intermediate/pending/` 路徑 |
| 忽略 LLM 例外 | `result = llm_client.analyze(...)` | 用 try/except 包裹並轉換為 AnalysisFailedError |
| frontmatter 格式錯誤 | 手動拼接字串 | 使用 `yaml.dump()` 確保格式正確 |
| 未處理 segments 為 None | `for seg in analysis.segments:` | 先檢查 `if analysis.segments:` |
| slug 過長或含非法字元 | 直接使用 title 作為檔名 | 使用 `_slugify()` 處理 |

"""

# ============================================================================
# 已移除的介面（移動至 src.llm）
# ============================================================================

"""
以下介面已移至 src.llm 模組：

- LLMProvider (Protocol) -> src.llm.LLMProvider
- TranscriptInput (Dataclass) -> src.llm.TranscriptInput  
- AnalysisResult (Dataclass) -> src.llm.AnalysisResult
- PromptLoader (Protocol) -> src.llm.PromptLoader
- OutputParser (Protocol) -> src.llm.OutputParser
- LLMCallError -> src.llm.LLMCallError
- LLMTimeoutError -> src.llm.LLMTimeoutError

請從 src.llm 匯入這些類別。
"""

# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. AnalyzerService
   - 正確初始化（接收 LLMClient）
   - analyze() 完整流程正確執行
   - analyze_batch() 批次處理正確
   - build_analyzed_markdown() 輸出格式符合 PRD

2. 與 LLM 模組整合
   - 正確使用 LLMClient 作為依賴
   - 錯誤正確傳遞（LLMCallError -> AnalysisFailedError）

3. StructuredSegmentation
   - inject_headers() 正確插入標題
   - find_quote_position() 模糊匹配正確

4. 輸出格式
   - Markdown 包含完整 frontmatter
   - frontmatter 分為原始資訊、語意分析、處理中繼資料三區塊
   - 內容部分保留完整轉錄文字

執行驗收測試：
    python docs/interfaces/tests/test_analyzer.py
"""
