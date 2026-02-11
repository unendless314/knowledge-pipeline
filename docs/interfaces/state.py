"""
Knowledge Pipeline - 狀態管理模組介面定義

此模組負責管理檔案的處理狀態，包括 frontmatter 讀寫、
冪等性檢查、檔案搬移等操作。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from models import (
    TranscriptFile,
    AnalyzedTranscript,
    PipelineStatus,
    ErrorInfo,
)


class FrontmatterReader(Protocol):
    """
    Frontmatter 讀取器介面
    
    讀取 Markdown 檔案的 YAML frontmatter。
    """
    
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
        ...
    
    def read_status(self, filepath: Path) -> PipelineStatus | None:
        """
        快速讀取 status 欄位
        
        只解析 frontmatter 中的 status 欄位，避免完整解析。
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            PipelineStatus 或 None
        """
        ...
    
    def read_source_id(self, filepath: Path) -> str | None:
        """
        快速讀取 source_id 欄位
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            source_id 字串或 None
        """
        ...


class FrontmatterWriter(Protocol):
    """
    Frontmatter 寫入器介面
    
    更新 Markdown 檔案的 YAML frontmatter，保留正文內容。
    """
    
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
        ...
    
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
        ...
    
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
        ...
    
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
        ...


class IdempotencyChecker(Protocol):
    """
    冪等性檢查器介面
    
    檢查檔案是否已處理，避免重複上傳。
    """
    
    def is_processed(self, filepath: Path) -> bool:
        """
        檢查檔案是否已處理
        
        若 status 為 uploaded 且有 source_id，則視為已處理。
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示已處理（應該跳過）
        """
        ...
    
    def is_pending(self, filepath: Path) -> bool:
        """
        檢查檔案是否等待審查
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 pending
        """
        ...
    
    def is_approved(self, filepath: Path) -> bool:
        """
        檢查檔案是否已核准
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 approved
        """
        ...
    
    def is_failed(self, filepath: Path) -> bool:
        """
        檢查檔案是否處理失敗
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            True 表示 status 為 failed
        """
        ...
    
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
        ...


class FileMover(Protocol):
    """
    檔案搬移器介面
    
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
        ...
    
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
        ...
    
    def ensure_directory(self, path: Path) -> None:
        """
        確保目錄存在
        
        Args:
            path: 目錄路徑
        """
        ...


class StateManager(Protocol):
    """
    狀態管理器介面
    
    整合 frontmatter 操作、冪等性檢查、檔案搬移的高階 API。
    """
    
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
        ...
    
    def mark_as_approved(self, filepath: Path) -> None:
        """
        標記為已核准狀態
        
        更新 frontmatter status 為 approved。
        
        Args:
            filepath: 檔案路徑
        """
        ...
    
    def mark_as_uploaded(
        self,
        filepath: Path,
        source_id: str,
        intermediate_dir: Path
    ) -> Path:
        """
        標記為已上傳狀態
        
        流程：
        1. 更新 frontmatter status 為 uploaded
        2. 寫入 source_id
        3. 搬移至 intermediate/approved/{channel}/{YYYY-MM}/
        
        Args:
            filepath: 檔案路徑
            source_id: Source ID
            intermediate_dir: intermediate 根目錄
            
        Returns:
            搬移後的檔案路徑
        """
        ...
    
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
        ...
    
    def get_file_status(self, filepath: Path) -> FileState:
        """
        取得檔案完整狀態
        
        Args:
            filepath: 檔案路徑
            
        Returns:
            FileState 實例
        """
        ...


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


class StatePersistence(Protocol):
    """
    狀態持久化介面
    
    負責將 AnalyzedTranscript 儲存為 Markdown 檔案。
    """
    
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
        ...
    
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
        ...


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
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. FrontmatterReader / FrontmatterWriter
   - 正確讀取/寫入 frontmatter
   - 保留 Markdown 正文內容不變
   - 無 frontmatter 時回傳空 dict
   - preserve_format=True 時盡量保留格式

2. IdempotencyChecker
   - status=uploaded + 有 source_id => is_processed=True
   - status=pending => is_pending=True
   - status=approved => is_approved=True
   - status=failed => is_failed=True
   - 正確判斷 should_retry

3. FileMover
   - 正確建立目標目錄結構
   - 搬移後原始檔案不存在
   - 搬移後內容正確
   - 處理目標已存在的情況

4. StateManager (整合測試)
   - mark_as_pending 正確更新 status 與搬移檔案
   - mark_as_uploaded 正確更新 status/source_id 與搬移檔案
   - mark_as_failed 正確寫入錯誤資訊
   - get_file_status 回傳完整資訊

5. StatePersistence
   - save_analyzed_transcript 產生的檔案可被正確載入
   - frontmatter 包含所有必要欄位
   - 內容格式正確

執行驗收測試：
    python docs/interfaces/tests/test_state.py
"""
