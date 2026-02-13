"""
Knowledge Pipeline - Analyzer 模組

使用 LLM 對轉錄內容進行語意分析，提取結構化 metadata 並產出增強版 Markdown 檔案。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

from src.llm import LLMClient, TranscriptInput
from src.llm.exceptions import LLMCallError, LLMRateLimitError, LLMTimeoutError
from src.models import (
    AnalyzedTranscript,
    PipelineStatus,
    ProcessingMetadata,
    TranscriptFile,
    TranscriptMetadata,
)


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
# Analysis Configuration
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
    llm_client: LLMClient
    default_template: str = "default"
    enable_segmentation: bool = True
    output_dir: Path | None = None


# ============================================================================
# Structured Segmentation
# ============================================================================

class StructuredSegmentation:
    """
    結構化分段處理器
    
    執行「LLM 定位 + Python 執刀」的結構化分段策略：
    1. LLM 分析產生 segments（含 start_quote 錨點）
    2. Python 在純文字內容中搜尋 start_quote
    3. 在精確匹配位置插入 Markdown 標題
    """
    
    def inject_headers_to_pure_text(
        self,
        content: str,
        segments: list[dict]
    ) -> str:
        """
        在純文字內容中插入 Markdown 標題
        
        在 start_quote 的精確位置插入標題，並確保標題前後有換行，
        使標題獨立成段，符合 Markdown 語法。
        
        Args:
            content: 純文字轉錄內容（已移除時間戳）
            segments: 分段資訊列表（從 analysis_result.segments 取得）
                每個 segment 格式：
                {
                    "section_type": "key_point",
                    "title": "ERC-8004 簡介",
                    "start_quote": "So what exactly is ERC-8004?"
                }
        
        Returns:
            插入標題後的純文字內容
        """
        if not segments:
            return content
        
        # 從後往前插入，避免位置偏移問題
        insertions = []
        
        for segment in segments:
            # 搜尋錨點位置
            quote = segment.get("start_quote", "")
            pos = self.find_quote_position(content, quote)
            if pos is not None:
                # 在 start_quote 精確位置插入標題
                section_type = segment.get("section_type", "section").upper()
                title = segment.get("title", "")
                
                # 檢查前面是否已經有足夠的換行
                prefix = content[max(0, pos-2):pos]
                if prefix.endswith('\n\n'):
                    # 前面已經有兩個換行，只加標題，後面加兩個換行
                    header = f"## [{section_type}] {title}\n\n"
                elif prefix.endswith('\n'):
                    # 前面只有一個換行，再加一個換行，後面加兩個換行
                    header = f"\n## [{section_type}] {title}\n\n"
                elif pos == 0:
                    # 在內容開頭，後面加兩個換行
                    header = f"## [{section_type}] {title}\n\n"
                else:
                    # 前面沒有換行，加兩個換行，後面也加兩個換行
                    header = f"\n\n## [{section_type}] {title}\n\n"
                insertions.append((pos, header))
        
        # 按位置排序（從後往前）
        insertions.sort(key=lambda x: x[0], reverse=True)
        
        # 執行插入
        result = content
        for pos, header in insertions:
            result = result[:pos] + header + result[pos:]
        
        return result
    
    def inject_headers(
        self,
        content: str,
        segments: list[dict]
    ) -> str:
        """
        （已棄用）在內容中插入 Markdown 標題
        
        此為向後相容方法，實際呼叫 inject_headers_to_pure_text。
        
        Args:
            content: 轉錄內容
            segments: 分段資訊列表
        
        Returns:
            插入標題後的內容
        """
        return self.inject_headers_to_pure_text(content, segments)
    
    def find_quote_position(
        self,
        content: str,
        quote: str,
        fuzzy: bool = True
    ) -> int | None:
        """
        在內容中搜尋錨點位置
        
        Args:
            content: 原始內容
            quote: 錨點文字
            fuzzy: 是否使用模糊匹配
        
        Returns:
            字元位置索引，或 None（未找到）
        """
        if not quote:
            return None
        
        # 精確匹配
        pos = content.find(quote)
        if pos != -1:
            return pos
        
        if not fuzzy:
            return None
        
        # 模糊匹配：允許 minor 差異
        import difflib
        
        best_ratio = 0.0
        best_pos = None
        
        # 簡化實作：搜尋 quote 的前 10 個字
        search_prefix = quote[:min(10, len(quote))]
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


# ============================================================================
# Analyzer Service
# ============================================================================

class AnalyzerService:
    """
    分析服務
    
    整合 prompt 載入、LLM 呼叫、結果解析、Markdown 建構的高階 API。
    
    使用範例:
        from src.llm import LLMClient
        from src.analyzer import AnalyzerService
        
        llm_client = LLMClient.from_config(config.llm)
        analyzer = AnalyzerService(llm_client=llm_client)
        
        result = analyzer.analyze(
            transcript_file,
            prompt_template="crypto_tech",
            output_dir=Path("intermediate/pending")
        )
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        enable_segmentation: bool = True,
        default_template: str = "default"
    ):
        """
        初始化 Analyzer
        
        Args:
            llm_client: LLM 客戶端實例（含具體 Provider）
            enable_segmentation: 是否啟用結構化分段
            default_template: 預設 prompt template
        """
        self.llm_client = llm_client
        self.enable_segmentation = enable_segmentation
        self.default_template = default_template
        self.segmentation = StructuredSegmentation()
    
    def analyze(
        self,
        transcript: TranscriptFile,
        prompt_template: str | None = None,
        output_dir: Path | None = None
    ) -> AnalyzedTranscript | None:
        """
        分析單個轉錄檔案
        
        完整流程：
        1. 提取純文字內容（移除時間戳）
        2. 將 TranscriptFile 轉換為 TranscriptInput（使用純文字）
        3. 確定輸出路徑（若未指定則使用 intermediate/pending/）
        4. 呼叫 LLMClient 執行分析
        5. （可選）執行結構化分段（在純文字中插入標題）
        6. 構建處理中繼資料
        7. 構建增強版 Markdown
        8. 儲存到指定目錄
        9. 回傳 AnalyzedTranscript
        
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
        template = prompt_template or self.default_template
        
        try:
            # Step 1: 提取純文字內容（移除時間戳）
            pure_content = self._extract_pure_text(transcript.content)
            
            # Step 2: 轉換為 LLM 輸入格式（使用純文字）
            input_data = self._to_transcript_input(transcript, pure_content)
            
            # Step 3: 確定輸出路徑
            if output_dir is None:
                output_dir = Path("intermediate/pending")
            output_path = self._build_output_path(output_dir, transcript)
            
            # Step 4: 執行 LLM 分析（核心步驟）
            # 注意：這裡交給 LLMClient 處理 temp/ 檔案和清理
            llm_log_path = output_path.parent / f"{output_path.stem}_llm_log.md"
            analysis_result = self.llm_client.analyze(
                input_data=input_data,
                prompt_template=template,
                output_path=llm_log_path
            )
            
            # Step 5: （可選）結構化分段（在純文字中插入標題）
            content = pure_content
            if self.enable_segmentation and analysis_result.segments:
                content = self._inject_headers(content, analysis_result.segments)
            
            # Step 6: 構建處理中繼資料
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
                f"LLM 分析失敗: {e}",
                transcript_path=transcript.path
            ) from e
    
    def analyze_batch(
        self,
        transcripts: list[TranscriptFile],
        prompt_template: str | None = None,
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
        import time
        
        results = []
        total = len(transcripts)
        template = prompt_template or self.default_template
        
        for i, transcript in enumerate(transcripts, 1):
            try:
                if progress_callback:
                    progress_callback(i, total, f"分析中: {transcript.metadata.title[:50]}...")
                
                result = self.analyze(transcript, template, output_dir)
                if result:
                    results.append(result)
                    
                    # 避免 rate limit
                    if i < total and delay_between_calls > 0:
                        time.sleep(delay_between_calls)
                        
            except AnalysisFailedError as e:
                # 記錄錯誤但繼續處理
                if progress_callback:
                    progress_callback(i, total, f"失敗: {e}")
                continue
        
        if progress_callback:
            progress_callback(total, total, f"完成: {len(results)}/{total}")
        
        return results
    
    def _to_transcript_input(
        self, 
        transcript: TranscriptFile, 
        pure_content: str | None = None
    ) -> TranscriptInput:
        """
        將 TranscriptFile 轉換為 TranscriptInput
        
        使用純文字內容給 LLM 分析，以提升段落邊界精確度。
        
        Args:
            transcript: 轉錄檔案
            pure_content: 純文字內容（已移除時間戳），若為 None 則自動提取
            
        Returns:
            TranscriptInput
        """
        # 若未提供純文字內容，則自動提取
        if pure_content is None:
            pure_content = self._extract_pure_text(transcript.content)
        
        return TranscriptInput(
            channel=transcript.metadata.channel,
            title=transcript.metadata.title,
            content=pure_content,
            published_at=transcript.metadata.published_at.isoformat(),
            word_count=transcript.metadata.word_count,
            file_path=transcript.path,
            video_id=transcript.metadata.video_id,
            duration=transcript.metadata.duration
        )
    
    def _extract_pure_text(self, content: str) -> str:
        """
        移除時間戳，提取純文字內容
        
        將 [MM:SS] 或 [HH:MM:SS] 格式的時間戳從內容中移除，
        讓 LLM 分析純粹的語意內容，避免時間戳干擾段落邊界判斷。
        
        Args:
            content: 原始轉錄內容（含時間戳）
            
        Returns:
            純文字內容（無時間戳）
        """
        lines = content.split('\n')
        pure_lines = []
        
        for line in lines:
            # 移除行首的時間戳 [MM:SS] 或 [HH:MM:SS] 格式
            pure_line = re.sub(r'^\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*', '', line)
            pure_lines.append(pure_line)
        
        return '\n'.join(pure_lines)
    
    def _build_output_path(
        self,
        output_dir: Path,
        transcript: TranscriptFile
    ) -> Path:
        """
        建構輸出檔案路徑
        
        格式: intermediate/pending/{channel}/{YYYY-MM}/{published_at}_{video_id}_{slug}_analyzed.md
        
        Args:
            output_dir: 輸出目錄
            transcript: 轉錄檔案
            
        Returns:
            輸出檔案路徑
        """
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
        """
        將標題轉換為 slug
        
        Args:
            text: 原始文字
            max_length: 最大長度
            
        Returns:
            slug 字串
        """
        # 移除非 alphanumeric 字元，保留 hyphen
        slug = re.sub(r'[^\w\s-]', '', text)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:max_length].strip('-')
    
    def _inject_headers(
        self,
        content: str,
        segments: list
    ) -> str:
        """
        在純文字內容中插入 Markdown 標題
        
        直接在純文字內容中插入標題，無需對齊時間戳，
        確保標題位置與 LLM 建議的 start_quote 完全匹配。
        
        Args:
            content: 純文字內容（已移除時間戳）
            segments: 分段資訊列表
            
        Returns:
            插入標題後的純文字內容
        """
        # 將 Segment 物件轉換為 dict
        segment_dicts = []
        for s in segments:
            if hasattr(s, 'section_type'):
                segment_dicts.append({
                    "section_type": s.section_type,
                    "title": s.title,
                    "start_quote": s.start_quote
                })
            else:
                segment_dicts.append(s)
        
        return self.segmentation.inject_headers_to_pure_text(content, segment_dicts)
    
    def _build_analyzed_markdown(
        self,
        original: TranscriptMetadata,
        analysis,
        processing: ProcessingMetadata,
        content: str
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
            original: 原始轉錄 metadata
            analysis: LLM 分析結果
            processing: 處理中繼資料
            content: 轉錄內容
        
        Returns:
            完整的 Markdown 內容字串
        """
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
        }
        
        # 可選欄位
        if analysis.dialogue_format:
            frontmatter["dialogue_format"] = analysis.dialogue_format
        
        if analysis.segments:
            frontmatter["segments"] = [
                {
                    "section_type": s.section_type,
                    "title": s.title,
                    "start_quote": s.start_quote
                }
                for s in analysis.segments
            ]
        
        if analysis.key_entities:
            frontmatter["key_entities"] = analysis.key_entities
        
        # 處理中繼資料
        frontmatter["analyzed_by"] = processing.analyzed_by
        frontmatter["analyzed_at"] = processing.analyzed_at.isoformat()
        frontmatter["pipeline_version"] = processing.pipeline_version
        frontmatter["source_path"] = processing.source_path
        
        # Pipeline 狀態
        frontmatter["status"] = PipelineStatus.PENDING.value
        frontmatter["source_id"] = None
        
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
