"""
Knowledge Pipeline - 核心資料模型介面定義

此模組定義所有核心資料結構，為其他模組提供型別契約。
實作時請嚴格遵循這些介面，確保資料流的一致性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol, TypeVar


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
# LLM 相關模型
# ============================================================================

# Note: TranscriptInput, AnalysisResult, Segment 已定義於 llm.py
# 請從 src.llm 匯入這些類別以確保一致性
# from src.llm import TranscriptInput, AnalysisResult, Segment


# ============================================================================
# LLM 分析結果模型
# ============================================================================

# Note: AnalysisResult 和 Segment 統一使用 src.llm 的定義
# 從 llm 匯入以確保單一真相來源
# 
# from src.llm import AnalysisResult, Segment
#
# AnalysisResult 包含欄位：
#   - semantic_summary, key_topics, suggested_topic
#   - content_type, content_density, temporal_relevance
#   - dialogue_format, segments, key_entities
#   - provider, model, processed_at (LLM 填入的中繼資料)
#
# Segment 包含欄位：
#   - section_type, title, start_quote


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
        analyzed_by: LLM Provider 與模型名稱（例: "gemini_cli/gemini-2.0-flash"）
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
        analysis: LLM 分析結果
        processing: 處理中繼資料
        error: 錯誤資訊（失敗時有值）
        status: 處理狀態
        source_id: ON 回傳的 source ID
    """
    original: TranscriptMetadata
    analysis: AnalysisResult
    processing: ProcessingMetadata
    error: ErrorInfo | None = None
    status: PipelineStatus = PipelineStatus.PENDING
    source_id: str | None = None
    
    def to_frontmatter_dict(self) -> dict:
        """
        轉換為 frontmatter 用的字典格式
        
        Returns:
            可序列化為 YAML 的字典
        """
        ...
    
    @classmethod
    def from_frontmatter_dict(cls, data: dict) -> AnalyzedTranscript:
        """
        從 frontmatter 字典解析
        
        Args:
            data: YAML frontmatter 解析後的字典
            
        Returns:
            AnalyzedTranscript 實例
        """
        ...


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
    """
    type: Literal["text", "link", "upload"]
    title: str
    content: str


@dataclass
class SourceCreateResponse:
    """
    POST /api/sources/json 回應
    
    Attributes:
        id: Source ID（格式: "source:xxxxx"）
        title: 建立時的標題
        content: 建立時的內容
        created_at: 建立時間
    """
    id: str
    title: str
    content: str
    created_at: datetime


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
    
    此端點通常不需要請求體，或僅需要空的 JSON。
    """
    pass


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
class PipelineConfig:
    """
    config.yaml 中的 Pipeline 配置
    
    Attributes:
        transcriber_output: YouTube Transcriber 輸出目錄路徑
        intermediate: 中間態檔案存放路徑
        open_notebook: ON API 配置
        min_word_count: 最小字數限制（預設 100）
        max_concurrent: 同時處理檔案數（預設 3）
        retry_attempts: API 失敗重試次數（預設 3）
        retry_delay: 重試間隔秒數（預設 5）
    """
    transcriber_output: Path
    intermediate: Path
    open_notebook: OpenNotebookConfig
    min_word_count: int = 100
    max_concurrent: int = 3
    retry_attempts: int = 3
    retry_delay: int = 5


# ============================================================================
# Protocol 定義（供依賴注入使用）
# ============================================================================

T = TypeVar('T')


class Serializable(Protocol):
    """支援序列化/反序列化的協議"""
    
    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, data: dict) -> Serializable: ...


class Validatable(Protocol):
    """支援驗證的協議"""
    
    def validate(self) -> bool: ...
    
    def validation_errors(self) -> list[str]: ...


# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. TranscriptFile
   - 能正確從檔案路徑與 frontmatter 建立
   - channel/video_id 屬性正確運作

2. AnalysisResult
   - 能正確序列化為 YAML-compatible dict
   - 能正確從 dict 解析

3. AnalyzedTranscript
   - to_frontmatter_dict() 輸出包含所有必要欄位
   - from_frontmatter_dict() 能正確還原
   - 處理缺失欄位時有合理的預設值

4. Enum 類別
   - 所有 enum 值與 PRD 定義一致
   - 支援字串比較（因繼承 str）

執行驗收測試：
    python docs/interfaces/tests/test_models.py
"""
