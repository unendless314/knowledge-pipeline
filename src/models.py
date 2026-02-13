"""
Knowledge Pipeline - 核心資料模型

此模組定義所有核心資料結構，為其他模組提供型別契約。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ============================================================================
# Enum 定義
# ============================================================================


class ContentType(str, Enum):
    """內容類型"""
    TECHNICAL_ANALYSIS = "technical_analysis"
    OPINION_DISCUSSION = "opinion_discussion"
    NEWS = "news"
    EDUCATIONAL = "educational"
    INTERVIEW = "interview"
    NARRATIVE = "narrative"


class ContentDensity(str, Enum):
    """資訊密度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TemporalRelevance(str, Enum):
    """時效性"""
    EVERGREEN = "evergreen"
    TIME_SENSITIVE = "time_sensitive"
    NEWS = "news"


class DialogueFormat(str, Enum):
    """對話形式"""
    MONOLOGUE = "monologue"
    INTERVIEW = "interview"
    DISCUSSION = "discussion"
    PRESENTATION = "presentation"


class PipelineStatus(str, Enum):
    """Pipeline 處理狀態"""
    PENDING = "pending"
    APPROVED = "approved"
    UPLOADED = "uploaded"
    FAILED = "failed"


# ============================================================================
# 原始資料模型 (來自 YouTube Transcriber)
# ============================================================================


@dataclass
class TranscriptMetadata:
    """
    YouTube Transcriber 輸出的原始 metadata
    
    Attributes:
        channel: 頻道名稱
        video_id: YouTube Video ID (11碼)
        title: 影片標題
        published_at: 發布日期
        duration: 影片長度 (格式: "HH:MM:SS" 或 "MM:SS")
        word_count: 轉錄字數
    """
    channel: str
    video_id: str
    title: str
    published_at: date
    duration: str
    word_count: int


@dataclass
class TranscriptFile:
    """
    待處理的轉錄檔案
    
    Attributes:
        path: 檔案絕對路徑
        metadata: 解析後的 frontmatter
        content: 轉錄內容（不含 frontmatter）
        status: 處理狀態（從 frontmatter 讀取，可能為 None）
        source_id: ON 回傳的 source ID（已上傳時有值）
    """
    path: Path
    metadata: TranscriptMetadata
    content: str
    status: PipelineStatus | None = None
    source_id: str | None = None
    
    @property
    def video_id(self) -> str:
        """Shortcut to metadata.video_id"""
        return self.metadata.video_id
    
    @property
    def channel(self) -> str:
        """Shortcut to metadata.channel"""
        return self.metadata.channel


# ============================================================================
# LLM 分析結果模型 (從 llm 模組匯入)
# ============================================================================

# Note: AnalysisResult 和 Segment 統一使用 src.llm 的定義
# 在執行時從 llm 模組匯入，避免循環依賴


# ============================================================================
# 處理中繼資料模型
# ============================================================================


@dataclass
class ProcessingMetadata:
    """
    Pipeline 處理中繼資料
    
    注意：analyzed_by 和 analyzed_at 在 llm.AnalysisResult 也有，
    此處用於統一管理，格式為 "{provider}/{model}"
    
    Attributes:
        analyzed_by: LLM Provider 與模型名稱（例: "gemini_cli/gemini-2.5-pro"）
        analyzed_at: 分析時間
        pipeline_version: Pipeline 版本
        source_path: 原始檔案路徑
    """
    analyzed_by: str
    analyzed_at: datetime
    pipeline_version: str
    source_path: str


@dataclass
class ErrorInfo:
    """
    錯誤資訊
    
    Attributes:
        error: 錯誤訊息
        error_code: 錯誤代碼
        failed_at: 失敗時間
    """
    error: str
    error_code: str
    failed_at: datetime


# ============================================================================
# 完整分析後的檔案模型
# ============================================================================


@dataclass
class AnalyzedTranscript:
    """
    經過 LLM 分析後的完整檔案資料
    
    此為內部處理用資料結構，最終會被儲存為 Markdown 檔案。
    
    Attributes:
        original: 原始轉錄 metadata
        analysis: LLM 分析結果 (llm.AnalysisResult)
        processing: 處理中繼資料
        error: 錯誤資訊（失敗時有值）
        status: 處理狀態
        source_id: ON 回傳的 source ID
    """
    original: TranscriptMetadata
    analysis: Any  # 執行時為 llm.AnalysisResult，避免循環匯入
    processing: ProcessingMetadata
    error: ErrorInfo | None = None
    status: PipelineStatus = PipelineStatus.PENDING
    source_id: str | None = None
    
    def to_frontmatter_dict(self) -> dict[str, Any]:
        """
        轉換為 frontmatter 用的字典格式
        
        Returns:
            可序列化為 YAML 的字典
        """
        # 延遲匯入避免循環依賴
        from src.llm import AnalysisResult
        
        analysis = self.analysis
        if isinstance(analysis, AnalysisResult):
            analysis_dict = analysis.to_dict()
        else:
            # 假設已經是 dict
            analysis_dict = analysis
        
        # 組合 frontmatter，不包含中繼資料欄位
        frontmatter = {
            # 原始資訊
            "channel": self.original.channel,
            "video_id": self.original.video_id,
            "title": self.original.title,
            "published_at": self.original.published_at.isoformat(),
            "duration": self.original.duration,
            "word_count": self.original.word_count,
            
            # 語意分析結果（來自 llm.AnalysisResult.to_dict()）
            "semantic_summary": analysis_dict.get("semantic_summary"),
            "key_topics": analysis_dict.get("key_topics"),
            "suggested_topic": analysis_dict.get("suggested_topic"),
            "content_type": analysis_dict.get("content_type"),
            "content_density": analysis_dict.get("content_density"),
            "temporal_relevance": analysis_dict.get("temporal_relevance"),
            "dialogue_format": analysis_dict.get("dialogue_format"),
            "segments": analysis_dict.get("segments"),
            "key_entities": analysis_dict.get("key_entities"),
            
            # 處理中繼資料
            "analyzed_by": self.processing.analyzed_by,
            "analyzed_at": self.processing.analyzed_at.isoformat(),
            "pipeline_version": self.processing.pipeline_version,
            "source_path": self.processing.source_path,
            
            # Pipeline 狀態
            "status": self.status.value,
        }
        
        # 加入 source_id（若有）
        if self.source_id:
            frontmatter["source_id"] = self.source_id
        
        # 加入錯誤資訊（若有）
        if self.error:
            frontmatter["error"] = self.error.error
            frontmatter["error_code"] = self.error.error_code
            frontmatter["failed_at"] = self.error.failed_at.isoformat()
        
        return frontmatter
    
    @classmethod
    def from_frontmatter_dict(
        cls,
        data: dict[str, Any],
        analysis_result: Any = None
    ) -> AnalyzedTranscript:
        """
        從 frontmatter 字典解析
        
        Args:
            data: YAML frontmatter 解析後的字典
            analysis_result: 預先建立的 AnalysisResult 物件（可選）
            
        Returns:
            AnalyzedTranscript 實例
        """
        from src.llm import AnalysisResult, Segment
        
        # 解析原始 metadata
        original = TranscriptMetadata(
            channel=data["channel"],
            video_id=data["video_id"],
            title=data["title"],
            published_at=date.fromisoformat(data["published_at"]),
            duration=data["duration"],
            word_count=data["word_count"],
        )
        
        # 解析 AnalysisResult
        if analysis_result is None:
            # 從字典建立
            segments_data = data.get("segments", [])
            segments = [
                Segment(
                    section_type=s["section_type"],
                    title=s["title"],
                    start_quote=s["start_quote"]
                )
                for s in (segments_data or [])
            ]
            
            analysis = AnalysisResult(
                semantic_summary=data.get("semantic_summary", ""),
                key_topics=data.get("key_topics", []),
                suggested_topic=data.get("suggested_topic", ""),
                content_type=data.get("content_type", "educational"),
                content_density=data.get("content_density", "medium"),
                temporal_relevance=data.get("temporal_relevance", "evergreen"),
                dialogue_format=data.get("dialogue_format"),
                segments=segments if segments else None,
                key_entities=data.get("key_entities"),
                provider="",
                model="",
            )
        else:
            analysis = analysis_result
        
        # 解析 ProcessingMetadata
        processing = ProcessingMetadata(
            analyzed_by=data.get("analyzed_by", ""),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            pipeline_version=data.get("pipeline_version", "1.0"),
            source_path=data.get("source_path", ""),
        )
        
        # 解析錯誤資訊
        error = None
        if "error" in data:
            error = ErrorInfo(
                error=data["error"],
                error_code=data.get("error_code", ""),
                failed_at=datetime.fromisoformat(data.get("failed_at", data["analyzed_at"]))
            )
        
        # 解析狀態
        status = PipelineStatus(data.get("status", "pending"))
        source_id = data.get("source_id")
        
        return cls(
            original=original,
            analysis=analysis,
            processing=processing,
            error=error,
            status=status,
            source_id=source_id,
        )


# ============================================================================
# Open Notebook API 相關模型
# ============================================================================


@dataclass
class OpenNotebookConfig:
    """
    Open Notebook API 配置
    
    Attributes:
        base_url: API Base URL (e.g., "http://localhost:5055")
        password: API 認證密碼（Bearer token）
    """
    base_url: str
    password: str


@dataclass
class SourceCreateRequest:
    """
    POST /api/sources/json 請求體
    
    Attributes:
        type: 輸入類型，固定為 "text"
        title: Source 標題（格式: "{channel} | {title} | {published_at}"）
        content: 完整內容（含 frontmatter YAML + 轉錄內容）
        embed: 是否立即建立嵌入（建議先設為 False，待 topics 更新後再觸發）
    """
    type: str  # "text", "link", "upload"
    title: str
    content: str
    embed: bool = False


@dataclass
class SourceCreateResponse:
    """
    POST /api/sources/json 回應
    
    Attributes:
        id: Source ID（格式: "source:xxxxx"）
        title: 建立時的標題
        content: 建立時的內容
        created_at: 建立時間（ISO 格式字串）
    """
    id: str
    title: str
    content: str
    created_at: str


@dataclass
class SourceUpdateRequest:
    """
    PUT /api/sources/{id} 請求體
    
    Attributes:
        topics: 關鍵主題列表（對應 analysis.key_topics）
    """
    topics: list[str]


@dataclass
class NotebookLinkRequest:
    """
    POST /api/notebooks/{id}/sources/{source_id} 請求體
    
    用於將 Source 關聯到 Notebook。
    """
    pass  # 通常是空請求體，ID 在 URL 中


# ============================================================================
# 配置相關模型
# ============================================================================


@dataclass
class TopicConfig:
    """
    topics.yaml 中的主題配置
    
    Attributes:
        name: 主題顯示名稱
        description: 主題描述（供 AI 參考）
        notebook: 目標 Notebook 名稱
        prompt_template: 對應的 prompt 檔案（如 "crypto_tech"）
        channels: 屬於此主題的頻道列表（可選）
    """
    name: str
    description: str
    notebook: str
    prompt_template: str
    channels: list[str] = field(default_factory=list)


@dataclass
class ChannelConfig:
    """
    topics.yaml 中的頻道預設配置
    
    Attributes:
        default_topic: 預設主題 ID（當 AI 無法分類時使用）
    """
    default_topic: str


@dataclass
class LLMConfig:
    """
    LLM Provider 配置
    
    Attributes:
        provider: Provider 類型 (gemini_cli / openai_api / gemini_api / local_llm)
        project_dir: Gemini CLI 專案目錄
        timeout: 請求超時時間（秒）
        max_retries: 最大重試次數
    """
    provider: str
    project_dir: Path
    timeout: int = 120
    max_retries: int = 3


@dataclass
class PipelineConfig:
    """
    config.yaml 中的 Pipeline 配置
    
    Attributes:
        transcriber_output: YouTube Transcriber 輸出目錄路徑
        intermediate: 中間態檔案存放路徑
        open_notebook: ON API 配置
        llm: LLM Provider 配置
        min_word_count: 最小字數限制（預設 100）
        max_concurrent: 同時處理檔案數（預設 3）
        retry_attempts: API 失敗重試次數（預設 3）
        retry_delay: 重試間隔秒數（預設 5）
    """
    transcriber_output: Path
    intermediate: Path
    open_notebook: OpenNotebookConfig
    llm: LLMConfig
    min_word_count: int = 100
    max_concurrent: int = 3
    retry_attempts: int = 3
    retry_delay: int = 5


# ============================================================================
# 例外定義
# ============================================================================


class ModelError(Exception):
    """Models 模組錯誤基類"""
    pass


class ValidationError(ModelError):
    """資料驗證錯誤"""
    pass


class SerializationError(ModelError):
    """序列化/反序列化錯誤"""
    pass
