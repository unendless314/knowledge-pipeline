"""
Knowledge Pipeline - State 模組

負責管理檔案的處理狀態，包括 frontmatter 讀寫、冪等性檢查、檔案搬移等操作。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.discovery import FrontmatterParser
from src.llm import AnalysisResult
from src.models import (
    AnalyzedTranscript,
    ErrorInfo,
    PipelineStatus,
    ProcessingMetadata,
    TranscriptMetadata,
)


# ============================================================================
# 例外定義
# ============================================================================

class StateError(Exception):
    """狀態模組錯誤基類"""
    pass


class FrontmatterReadError(StateError):
    """Frontmatter 讀取失敗"""
    pass


class FrontmatterWriteError(StateError):
    """Frontmatter 寫入失敗"""
    pass


class FileMoveError(StateError):
    """檔案搬移失敗"""
    pass


# ============================================================================
# File State
# ============================================================================

@dataclass
class FileState:
    """
    檔案完整狀態
    
    Attributes:
        filepath: 檔案路徑
        status: 處理狀態
        source_id: Source ID（若已上傳）
        error: 錯誤資訊（若失敗）
        can_process: 是否可處理（未處理或允許重試）
    """
    filepath: Path
    status: PipelineStatus | None
    source_id: str | None
    error: ErrorInfo | None
    can_process: bool


# ============================================================================
# Frontmatter Reader
# ============================================================================

class FrontmatterReader:
    """
    Frontmatter 讀取器
    
    讀取 Markdown 檔案的 YAML frontmatter。
    """
    
    def __init__(self, parser: FrontmatterParser | None = None):
        """
        初始化讀取器
        
        Args:
            parser: Frontmatter 解析器
        """
        self.parser = parser or FrontmatterParser()
    
    def read(self, filepath: Path) -> dict:
        """
        讀取 frontmatter
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            frontmatter 字典（若無 frontmatter 則回傳空 dict）
            
        Raises:
            FileNotFoundError: 檔案不存在
            FrontmatterReadError: 讀取或解析失敗
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"檔案不存在: {filepath}")
        
        try:
            frontmatter, _ = self.parser.parse_file(filepath)
            return frontmatter
        except Exception as e:
            raise FrontmatterReadError(f"讀取 frontmatter 失敗: {e}") from e
    
    def read_status(self, filepath: Path) -> PipelineStatus | None:
        """
        快速讀取 status 欄位
        
        只解析 frontmatter 中的 status 欄位，避免完整解析。
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            PipelineStatus 或 None
        """
        try:
            frontmatter = self.read(filepath)
            status_str = frontmatter.get("status")
            
            if not status_str:
                return None
            
            return PipelineStatus(status_str)
        except (FileNotFoundError, FrontmatterReadError):
            return None
        except ValueError:
            return None
    
    def read_source_id(self, filepath: Path) -> str | None:
        """
        快速讀取 source_id 欄位
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            source_id 字串或 None
        """
        try:
            frontmatter = self.read(filepath)
            return frontmatter.get("source_id")
        except (FileNotFoundError, FrontmatterReadError):
            return None


# ============================================================================
# Frontmatter Writer
# ============================================================================

class FrontmatterWriter:
    """
    Frontmatter 寫入器
    
    更新 Markdown 檔案的 YAML frontmatter，保留正文內容。
    """
    
    def __init__(self, parser: FrontmatterParser | None = None):
        """
        初始化寫入器
        
        Args:
            parser: Frontmatter 解析器
        """
        self.parser = parser or FrontmatterParser()
    
    def write(
        self,
        filepath: Path,
        updates: dict,
        preserve_format: bool = True
    ) -> None:
        """
        更新 frontmatter
        
        Args:
            filepath: Markdown 檔案路徑
            updates: 要更新的欄位字典
            preserve_format: 是否盡量保留原始 YAML 格式
            
        Raises:
            FileNotFoundError: 檔案不存在
            FrontmatterWriteError: 寫入失敗
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"檔案不存在: {filepath}")
        
        try:
            # 讀取現有內容
            content = filepath.read_text(encoding="utf-8")
            frontmatter, body = self.parser.parse(content)
            
            # 更新 frontmatter
            updated_frontmatter = {**frontmatter, **updates}
            
            # 序列化為 YAML
            yaml_content = yaml.dump(
                updated_frontmatter,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False
            )
            
            # 組合新的 Markdown 內容
            new_content = f"---\n{yaml_content}---\n\n{body}"
            
            # 寫入檔案
            filepath.write_text(new_content, encoding="utf-8")
            
        except Exception as e:
            raise FrontmatterWriteError(f"寫入 frontmatter 失敗: {e}") from e
    
    def write_status(
        self,
        filepath: Path,
        status: PipelineStatus
    ) -> None:
        """
        更新 status 欄位
        
        Args:
            filepath: Markdown 檔案路徑
            status: 新狀態
        """
        self.write(filepath, {"status": status.value})
    
    def write_source_id(
        self,
        filepath: Path,
        source_id: str
    ) -> None:
        """
        更新 source_id 欄位
        
        Args:
            filepath: Markdown 檔案路徑
            source_id: Source ID
        """
        self.write(filepath, {"source_id": source_id})
    
    def write_error(
        self,
        filepath: Path,
        error: ErrorInfo
    ) -> None:
        """
        寫入錯誤資訊
        
        同時設定 status 為 failed。
        
        Args:
            filepath: Markdown 檔案路徑
            error: 錯誤資訊
        """
        error_dict = {
            "error": error.message,
            "error_code": error.code,
            "failed_at": error.timestamp.isoformat() if error.timestamp else datetime.now().isoformat(),
            "status": PipelineStatus.FAILED.value
        }
        self.write(filepath, error_dict)


# ============================================================================
# Idempotency Checker
# ============================================================================

class IdempotencyChecker:
    """
    冪等性檢查器
    
    檢查檔案是否已處理，避免重複上傳。
    """
    
    def __init__(self, reader: FrontmatterReader | None = None):
        """
        初始化檢查器
        
        Args:
            reader: Frontmatter 讀取器
        """
        self.reader = reader or FrontmatterReader()
    
    def is_processed(self, filepath: Path) -> bool:
        """
        檢查檔案是否已處理
        
        若 status 為 uploaded 且有 source_id，則視為已處理。
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示已處理（應該跳過）
        """
        status = self.reader.read_status(filepath)
        source_id = self.reader.read_source_id(filepath)
        
        return status == PipelineStatus.UPLOADED and source_id is not None
    
    def is_pending(self, filepath: Path) -> bool:
        """
        檢查檔案是否等待審查
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 pending
        """
        status = self.reader.read_status(filepath)
        return status == PipelineStatus.PENDING
    
    def is_approved(self, filepath: Path) -> bool:
        """
        檢查檔案是否已核准
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 approved
        """
        status = self.reader.read_status(filepath)
        return status == PipelineStatus.APPROVED
    
    def is_failed(self, filepath: Path) -> bool:
        """
        檢查檔案是否處理失敗
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 failed
        """
        status = self.reader.read_status(filepath)
        return status == PipelineStatus.FAILED
    
    def should_retry(self, filepath: Path, force: bool = False) -> bool:
        """
        檢查失敗檔案是否應該重試
        
        判斷邏輯：
        - 預設 (force=False): 若 status 為 failed，回傳 False（不重試）。
        - 強制 (force=True): 若 status 為 failed，回傳 True（允許重試）。
        
        Args:
            filepath: Markdown 檔案路徑
            force: 是否強制重試
            
        Returns:
            True 表示應該重試
        """
        status = self.reader.read_status(filepath)
        
        # 無 status，視為新檔案
        if status is None:
            return True
        
        # failed 狀態
        if status == PipelineStatus.FAILED:
            return force
        
        # 其他狀態（uploaded, approved, pending）視為已處理
        return False


# ============================================================================
# File Mover
# ============================================================================

class FileMover:
    """
    檔案搬移器
    
    負責在不同狀態目錄間搬移檔案。
    """
    
    def move_to_pending(
        self,
        source_path: Path,
        intermediate_dir: Path,
        channel: str,
        year_month: str
    ) -> Path:
        """
        將檔案搬移至 pending 目錄
        
        Args:
            source_path: 原始檔案路徑
            intermediate_dir: intermediate 根目錄
            channel: 頻道名稱
            year_month: 年月（格式: YYYY-MM）
            
        Returns:
            目標路徑
        """
        target_dir = intermediate_dir / "pending" / channel / year_month
        return self._move_file(source_path, target_dir)
    
    def move_to_approved(
        self,
        source_path: Path,
        intermediate_dir: Path,
        channel: str,
        year_month: str
    ) -> Path:
        """
        將檔案搬移至 approved 目錄
        
        Args:
            source_path: 原始檔案路徑
            intermediate_dir: intermediate 根目錄
            channel: 頻道名稱
            year_month: 年月（格式: YYYY-MM）
            
        Returns:
            目標路徑
        """
        target_dir = intermediate_dir / "approved" / channel / year_month
        return self._move_file(source_path, target_dir)
    
    def _move_file(self, source_path: Path, target_dir: Path) -> Path:
        """
        搬移檔案到目標目錄
        
        Args:
            source_path: 原始檔案路徑
            target_dir: 目標目錄
            
        Returns:
            目標路徑
            
        Raises:
            FileMoveError: 搬移失敗
        """
        try:
            # 確保目標目錄存在
            self.ensure_directory(target_dir)
            
            target_path = target_dir / source_path.name
            
            # 如果目標已存在，先刪除
            if target_path.exists():
                target_path.unlink()
            
            # 搬移檔案
            shutil.move(str(source_path), str(target_path))
            
            return target_path
            
        except Exception as e:
            raise FileMoveError(f"搬移檔案失敗: {source_path} -> {target_dir}: {e}") from e
    
    def ensure_directory(self, path: Path) -> None:
        """
        確保目錄存在
        
        Args:
            path: 目錄路徑
        """
        path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# State Persistence
# ============================================================================

class StatePersistence:
    """
    狀態持久化
    
    負責將 AnalyzedTranscript 儲存為 Markdown 檔案。
    """
    
    def __init__(self, parser: FrontmatterParser | None = None):
        """
        初始化持久化器
        
        Args:
            parser: Frontmatter 解析器
        """
        self.parser = parser or FrontmatterParser()
    
    def save_analyzed_transcript(
        self,
        analyzed: AnalyzedTranscript,
        filepath: Path
    ) -> None:
        """
        儲存分析結果
        
        將 AnalyzedTranscript 序列化為 Markdown 檔案，
        包含完整的 frontmatter 與內容。
        
        Args:
            analyzed: 分析完成的資料
            filepath: 目標檔案路徑
        """
        # 確保目錄存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 構建 frontmatter
        frontmatter = self._build_frontmatter(analyzed)
        
        # 序列化為 YAML
        yaml_content = yaml.dump(
            frontmatter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False
        )
        
        # 組合 Markdown 內容
        # 內容部分需要重新取得，AnalyzedTranscript 不直接儲存內容
        # 這裡我們需要從原始路徑讀取內容，或從其他來源取得
        content = self._get_content(analyzed)
        
        markdown_content = f"---\n{yaml_content}---\n\n{content}"
        
        # 寫入檔案
        filepath.write_text(markdown_content, encoding="utf-8")
    
    def _build_frontmatter(self, analyzed: AnalyzedTranscript) -> dict:
        """
        從 AnalyzedTranscript 構建 frontmatter 字典
        
        Args:
            analyzed: 分析完成的資料
            
        Returns:
            frontmatter 字典
        """
        original = analyzed.original
        analysis = analyzed.analysis
        processing = analyzed.processing
        
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
        frontmatter["status"] = analyzed.status.value
        
        if analyzed.source_id:
            frontmatter["source_id"] = analyzed.source_id
        
        if analyzed.error:
            frontmatter["error"] = analyzed.error.message
            frontmatter["error_code"] = analyzed.error.code
            if analyzed.error.timestamp:
                frontmatter["failed_at"] = analyzed.error.timestamp.isoformat()
        
        return frontmatter
    
    def _get_content(self, analyzed: AnalyzedTranscript) -> str:
        """
        取得轉錄內容
        
        這是一個輔助方法，實際實作可能需要從原始檔案讀取內容。
        為了簡化，這裡返回空字串，實際使用時應該覆寫或修改。
        
        Args:
            analyzed: 分析完成的資料
            
        Returns:
            內容字串
        """
        # 從原始路徑讀取內容
        source_path = Path(analyzed.processing.source_path)
        if source_path.exists():
            try:
                _, content = self.parser.parse_file(source_path)
                return content
            except Exception:
                pass
        
        return ""
    
    def load_analyzed_transcript(
        self,
        filepath: Path
    ) -> AnalyzedTranscript:
        """
        載入分析結果
        
        從 Markdown 檔案解析 AnalyzedTranscript。
        
        Args:
            filepath: 檔案路徑
            
        Returns:
            AnalyzedTranscript 實例
        """
        frontmatter, content = self.parser.parse_file(filepath)
        
        # 解析原始資訊
        original = TranscriptMetadata(
            channel=frontmatter["channel"],
            video_id=frontmatter["video_id"],
            title=frontmatter["title"],
            published_at=self._parse_date(frontmatter["published_at"]),
            duration=frontmatter.get("duration", ""),
            word_count=frontmatter.get("word_count", 0) or 0
        )
        
        # 解析分析結果
        from src.llm.models import Segment
        
        segments = None
        if "segments" in frontmatter and frontmatter["segments"]:
            segments = [
                Segment(
                    section_type=s["section_type"],
                    title=s["title"],
                    start_quote=s["start_quote"]
                )
                for s in frontmatter["segments"]
            ]
        
        analysis = AnalysisResult(
            semantic_summary=frontmatter["semantic_summary"],
            key_topics=frontmatter.get("key_topics", []),
            suggested_topic=frontmatter.get("suggested_topic", ""),
            content_type=frontmatter.get("content_type", ""),
            content_density=frontmatter.get("content_density", ""),
            temporal_relevance=frontmatter.get("temporal_relevance", ""),
            dialogue_format=frontmatter.get("dialogue_format"),
            segments=segments,
            key_entities=frontmatter.get("key_entities"),
            provider=frontmatter.get("analyzed_by", "").split("/")[0] if "/" in frontmatter.get("analyzed_by", "") else frontmatter.get("analyzed_by", ""),
            model=frontmatter.get("analyzed_by", "").split("/")[1] if "/" in frontmatter.get("analyzed_by", "") else "",
            processed_at=self._parse_datetime(frontmatter.get("analyzed_at"))
        )
        
        # 解析處理中繼資料
        processing = ProcessingMetadata(
            analyzed_by=frontmatter.get("analyzed_by", ""),
            analyzed_at=self._parse_datetime(frontmatter.get("analyzed_at")),
            pipeline_version=frontmatter.get("pipeline_version", ""),
            source_path=frontmatter.get("source_path", str(filepath))
        )
        
        # 解析狀態
        status = PipelineStatus(frontmatter.get("status", "pending"))
        source_id = frontmatter.get("source_id")
        
        # 解析錯誤資訊
        error = None
        if "error" in frontmatter:
            error = ErrorInfo(
                message=frontmatter["error"],
                code=frontmatter.get("error_code", ""),
                timestamp=self._parse_datetime(frontmatter.get("failed_at"))
            )
        
        return AnalyzedTranscript(
            original=original,
            analysis=analysis,
            processing=processing,
            error=error,
            status=status,
            source_id=source_id
        )
    
    def _parse_date(self, date_value) -> datetime:
        """解析日期值"""
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            return datetime.fromisoformat(date_value).date()
        return date_value
    
    def _parse_datetime(self, dt_value) -> datetime:
        """解析日期時間值"""
        if isinstance(dt_value, datetime):
            return dt_value
        if isinstance(dt_value, str):
            return datetime.fromisoformat(dt_value)
        return datetime.now()


# ============================================================================
# State Manager
# ============================================================================

class StateManager:
    """
    狀態管理器
    
    整合 frontmatter 操作、冪等性檢查、檔案搬移的高階 API。
    """
    
    def __init__(
        self,
        reader: FrontmatterReader | None = None,
        writer: FrontmatterWriter | None = None,
        checker: IdempotencyChecker | None = None,
        mover: FileMover | None = None,
        persistence: StatePersistence | None = None
    ):
        """
        初始化狀態管理器
        
        Args:
            reader: Frontmatter 讀取器
            writer: Frontmatter 寫入器
            checker: 冪等性檢查器
            mover: 檔案搬移器
            persistence: 狀態持久化器
        """
        self.reader = reader or FrontmatterReader()
        self.writer = writer or FrontmatterWriter()
        self.checker = checker or IdempotencyChecker(self.reader)
        self.mover = mover or FileMover()
        self.persistence = persistence or StatePersistence()
    
    def mark_as_pending(
        self,
        analyzed: AnalyzedTranscript,
        intermediate_dir: Path
    ) -> Path:
        """
        標記為待審查狀態
        
        流程：
        1. 更新 frontmatter status 為 pending
        2. 搬移至 intermediate/pending/{channel}/{YYYY-MM}/
        
        Args:
            analyzed: 分析完成的資料
            intermediate_dir: intermediate 根目錄
            
        Returns:
            儲存後的檔案路徑
        """
        original = analyzed.original
        
        # 計算年月
        year_month = original.published_at.strftime("%Y-%m")
        
        # 構建輸出路徑
        output_path = self._build_output_path(
            intermediate_dir / "pending",
            original,
            year_month
        )
        
        # 設定狀態為 pending
        analyzed.status = PipelineStatus.PENDING
        
        # 儲存檔案
        self.persistence.save_analyzed_transcript(analyzed, output_path)
        
        return output_path
    
    def mark_as_approved(self, filepath: Path) -> None:
        """
        標記為已核准狀態
        
        更新 frontmatter status 為 approved。
        
        Args:
            filepath: 檔案路徑
        """
        self.writer.write_status(filepath, PipelineStatus.APPROVED)
    
    def mark_as_uploaded(
        self,
        filepath: Path,
        source_id: str,
        intermediate_dir: Path,
        original_filepath: Path | None = None
    ) -> Path:
        """
        標記為已上傳狀態
        
        流程：
        1. 更新 frontmatter status 為 uploaded
        2. 寫入 source_id
        3. 搬移至 intermediate/approved/{channel}/{YYYY-MM}/
        4. （可選）同步更新原始字幕檔案的 frontmatter
        
        Args:
            filepath: 檔案路徑
            source_id: Source ID
            intermediate_dir: intermediate 根目錄
            original_filepath: 原始字幕檔案路徑（若提供，會同步更新其 frontmatter）
            
        Returns:
            搬移後的檔案路徑
        """
        # 更新狀態和 source_id
        self.writer.write_status(filepath, PipelineStatus.UPLOADED)
        self.writer.write_source_id(filepath, source_id)
        
        # 同步更新原始字幕檔案的 frontmatter（若提供路徑）
        if original_filepath and original_filepath.exists():
            try:
                self.writer.write_status(original_filepath, PipelineStatus.UPLOADED)
                self.writer.write_source_id(original_filepath, source_id)
            except Exception as e:
                # 記錄錯誤但不影響主要流程
                print(f"警告: 無法更新原始檔案狀態 {original_filepath}: {e}")
        
        # 讀取 frontmatter 以取得 channel 和 published_at
        frontmatter = self.reader.read(filepath)
        channel = frontmatter.get("channel", "unknown")
        published_at_str = frontmatter.get("published_at", "")
        
        # 解析年月
        try:
            published_at = datetime.fromisoformat(published_at_str)
            year_month = published_at.strftime("%Y-%m")
        except (ValueError, TypeError):
            year_month = datetime.now().strftime("%Y-%m")
        
        # 搬移到 approved 目錄
        target_path = self.mover.move_to_approved(
            filepath, intermediate_dir, channel, year_month
        )
        
        return target_path
    
    def mark_as_failed(
        self,
        filepath: Path,
        error: str,
        error_code: str
    ) -> None:
        """
        標記為失敗狀態
        
        更新 frontmatter：
        - status: failed
        - error: 錯誤訊息
        - error_code: 錯誤代碼
        - failed_at: 失敗時間
        
        Args:
            filepath: 檔案路徑
            error: 錯誤訊息
            error_code: 錯誤代碼
        """
        error_info = ErrorInfo(
            message=error,
            code=error_code,
            timestamp=datetime.now()
        )
        self.writer.write_error(filepath, error_info)
    
    def get_file_status(self, filepath: Path) -> FileState:
        """
        取得檔案完整狀態
        
        Args:
            filepath: 檔案路徑
            
        Returns:
            FileState 實例
        """
        status = self.reader.read_status(filepath)
        source_id = self.reader.read_source_id(filepath)
        
        # 檢查錯誤資訊
        error = None
        try:
            frontmatter = self.reader.read(filepath)
            if "error" in frontmatter:
                error = ErrorInfo(
                    message=frontmatter["error"],
                    code=frontmatter.get("error_code", ""),
                    timestamp=datetime.fromisoformat(frontmatter["failed_at"]) if "failed_at" in frontmatter else None
                )
        except Exception:
            pass
        
        # 判斷是否可以處理
        can_process = False
        if status is None:
            can_process = True
        elif status == PipelineStatus.FAILED:
            can_process = False  # 預設不重試失敗檔案
        
        return FileState(
            filepath=filepath,
            status=status,
            source_id=source_id,
            error=error,
            can_process=can_process
        )
    
    def _build_output_path(
        self,
        base_dir: Path,
        metadata: TranscriptMetadata,
        year_month: str
    ) -> Path:
        """
        構建輸出檔案路徑
        
        Args:
            base_dir: 基礎目錄
            metadata: 轉錄 metadata
            year_month: 年月（YYYY-MM）
            
        Returns:
            輸出檔案路徑
        """
        # 產生 slug（標題的簡化版本）
        slug = self._slugify(metadata.title, max_length=50)
        
        # 檔名格式: {published_at}_{video_id}_{slug}_analyzed.md
        filename = (
            f"{metadata.published_at.strftime('%Y%m%d')}"
            f"_{metadata.video_id}"
            f"_{slug}"
            f"_analyzed.md"
        )
        
        return base_dir / metadata.channel / year_month / filename
    
    def _slugify(self, text: str, max_length: int = 50) -> str:
        """
        將標題轉換為 slug
        
        Args:
            text: 原始文字
            max_length: 最大長度
            
        Returns:
            slug 字串
        """
        import re
        # 移除非 alphanumeric 字元，保留 hyphen
        slug = re.sub(r"[^\w\s-]", "", text)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:max_length].strip("-")
