"""
Knowledge Pipeline - LLM Provider 資料模型

定義 LLM 相關的資料結構，供 models.py 和其他模組使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


# ============================================================================
# Enum 定義
# ============================================================================


class ProviderType(str, Enum):
    """支援的 LLM Provider 類型"""
    GEMINI_CLI = "gemini_cli"
    OPENAI_API = "openai_api"
    GEMINI_API = "gemini_api"
    LOCAL_LLM = "local_llm"


# ============================================================================
# 輸入輸出資料模型
# ============================================================================


@dataclass
class TranscriptInput:
    """
    輸入給 LLM 的標準化轉錄資料
    
    所有 Provider 都使用此統一格式作為輸入。
    
    Attributes:
        channel: YouTube 頻道名稱
        title: 影片標題
        content: 完整轉錄內容（純文字）
        published_at: 發布日期（ISO 8601 格式字串）
        word_count: 轉錄字數
        file_path: 原始檔案路徑
        video_id: YouTube Video ID（可選）
        duration: 影片長度（可選）
    """
    channel: str
    title: str
    content: str
    published_at: str
    word_count: int
    file_path: Path
    video_id: str | None = None
    duration: str | None = None
    
    @property
    def content_preview(self, max_chars: int = 500) -> str:
        """內容預覽（用於 prompt）"""
        if len(self.content) <= max_chars:
            return self.content
        return self.content[:max_chars] + "..."


@dataclass
class Segment:
    """
    內容分段（用於結構化分段）
    
    Attributes:
        section_type: 段落類型 (intro, key_point, conclusion, etc.)
        title: 段落標題
        start_quote: 錨點文字（段落起始句，約 10-20 字）
    """
    section_type: str
    title: str
    start_quote: str


@dataclass
class AnalysisResult:
    """
    統一的 LLM 分析結果格式
    
    所有 Provider 都必須將輸出轉換為此標準格式。
    
    Attributes:
        semantic_summary: 內容摘要（100-200 字）
        key_topics: 關鍵主題（3-5 個）
        suggested_topic: AI 建議的歸檔類別 ID（對應 topics.yaml 中的 key）
        content_type: 內容類型 (technical_analysis, opinion_discussion, news, ...)
        content_density: 資訊密度 (high, medium, low)
        temporal_relevance: 時效性 (evergreen, time_sensitive, news)
        dialogue_format: 對話形式（可選）
        segments: 敘事結構分段（可選，用於結構化分段）
        key_entities: 關鍵實體（可選，如 [[Entity Name]]）
        
        # 中繼資料（由 Provider 自動填入）
        provider: 使用的 Provider 類型
        model: 使用的模型名稱
        processed_at: 處理時間
    """
    semantic_summary: str
    key_topics: list[str]
    suggested_topic: str
    content_type: str  # technical_analysis, opinion_discussion, news, educational, interview
    content_density: str  # high, medium, low
    temporal_relevance: str  # evergreen, time_sensitive, news
    
    # 可選欄位
    dialogue_format: str | None = None
    segments: list[Segment] | None = None
    key_entities: list[str] | None = None
    
    # 中繼資料（由 Provider 自動填入）
    provider: str = ""
    model: str = ""
    processed_at: datetime | None = None
    
    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now()
    
    def to_dict(self) -> dict:
        """轉換為字典（用於序列化）"""
        return {
            "semantic_summary": self.semantic_summary,
            "key_topics": self.key_topics,
            "suggested_topic": self.suggested_topic,
            "content_type": self.content_type,
            "content_density": self.content_density,
            "temporal_relevance": self.temporal_relevance,
            "dialogue_format": self.dialogue_format,
            "segments": [
                {"section_type": s.section_type, "title": s.title, "start_quote": s.start_quote}
                for s in (self.segments or [])
            ] if self.segments else None,
            "key_entities": self.key_entities if self.key_entities else None,
            "analyzed_by": f"{self.provider}/{self.model}" if self.model else self.provider,
            "analyzed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> AnalysisResult:
        """從字典建立實例"""
        segments_data = data.get("segments")
        segments = None
        if segments_data:
            segments = [
                Segment(
                    section_type=s["section_type"],
                    title=s["title"],
                    start_quote=s["start_quote"]
                )
                for s in segments_data
            ]
        
        # 解析 analyzed_by 格式 "provider/model"
        analyzed_by = data.get("analyzed_by", "")
        provider = ""
        model = ""
        if analyzed_by:
            parts = analyzed_by.split("/", 1)
            provider = parts[0]
            model = parts[1] if len(parts) > 1 else ""
        
        # 解析 analyzed_at
        processed_at = None
        if "analyzed_at" in data and data["analyzed_at"]:
            if isinstance(data["analyzed_at"], str):
                processed_at = datetime.fromisoformat(data["analyzed_at"])
            else:
                processed_at = data["analyzed_at"]
        
        return cls(
            semantic_summary=data.get("semantic_summary", ""),
            key_topics=data.get("key_topics", []),
            suggested_topic=data.get("suggested_topic", ""),
            content_type=data.get("content_type", "educational"),
            content_density=data.get("content_density", "medium"),
            temporal_relevance=data.get("temporal_relevance", "evergreen"),
            dialogue_format=data.get("dialogue_format"),
            segments=segments,
            key_entities=data.get("key_entities"),
            provider=provider,
            model=model,
            processed_at=processed_at,
        )


# ============================================================================
# 配置資料模型
# ============================================================================


@dataclass
class GeminiCLIConfig:
    """Gemini CLI Provider 配置"""
    project_dir: Path
    temp_dir: Path | None = None  # 預設 project_dir/temp
    timeout: int = 300
    max_retries: int = 3
    initial_retry_delay: int = 3


@dataclass
class OpenAIConfig:
    """OpenAI API Provider 配置（預留）"""
    api_key: str
    model: str = "gpt-4"
    base_url: str | None = None  # 用於自定義端點
    timeout: int = 60
    max_retries: int = 3


@dataclass
class LLMConfig:
    """通用 LLM 配置"""
    provider: ProviderType
    gemini_cli: GeminiCLIConfig | None = None
    openai: OpenAIConfig | None = None
