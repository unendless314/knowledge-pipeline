"""
Knowledge Pipeline - 檔案發現模組介面定義

此模組負責掃描 YouTube Transcriber 輸出目錄，識別需要處理的新增轉錄稿。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Iterator

from models import TranscriptFile, TranscriptMetadata, PipelineStatus


class FileScanner(Protocol):
    """
    檔案掃描器介面
    
    遞迴掃描目錄，找出所有 Markdown 轉錄檔案。
    """
    
    def scan(
        self,
        root_dir: Path,
        pattern: str = "*.md"
    ) -> Iterator[Path]:
        """
        掃描目錄中的所有轉錄檔案
        
        Args:
            root_dir: 掃描根目錄（如 transcriber_output/）
            pattern: 檔案匹配模式，預設 "*.md"
            
        Yields:
            符合條件的檔案路徑
            
        Raises:
            DirectoryNotFoundError: 根目錄不存在
            PermissionError: 無權限讀取目錄
        """
        ...


class FrontmatterParser(Protocol):
    """
    Frontmatter 解析器介面
    
    解析 Markdown 檔案頂部的 YAML frontmatter。
    """
    
    def parse(self, content: str) -> tuple[dict, str]:
        """
        解析 Markdown 內容
        
        Args:
            content: 完整的 Markdown 檔案內容
            
        Returns:
            Tuple[frontmatter_dict, body_content]
            - frontmatter_dict: YAML 解析後的字典，若無 frontmatter 則為空 dict
            - body_content: Markdown 正文（不含 frontmatter）
        """
        ...
    
    def parse_file(self, filepath: Path) -> tuple[dict, str]:
        """
        解析 Markdown 檔案
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            Tuple[frontmatter_dict, body_content]
        """
        ...


class TranscriptMetadataExtractor(Protocol):
    """
    轉錄 Metadata 提取器介面
    
    從 frontmatter 字典提取結構化的 TranscriptMetadata。
    """
    
    def extract(self, frontmatter: dict, filepath: Path | None = None) -> TranscriptMetadata:
        """
        提取 metadata
        
        Args:
            frontmatter: YAML frontmatter 解析後的字典
            filepath: 檔案路徑（用於錯誤報告）
            
        Returns:
            TranscriptMetadata 實例
            
        Raises:
            MetadataExtractionError: 缺少必要欄位或格式錯誤
        """
        ...
    
    def extract_video_id(self, filepath: Path, frontmatter: dict) -> str:
        """
        提取 Video ID
        
        優先從 frontmatter 的 video_id 欄位取得，
        若不存在則嘗試從檔名解析。
        
        Args:
            filepath: 檔案路徑
            frontmatter: frontmatter 字典
            
        Returns:
            YouTube Video ID（11碼）
        """
        ...


class FileFilter(Protocol):
    """
    檔案過濾器介面
    
    根據各種條件過濾檔案。
    """
    
    def should_process(
        self,
        metadata: TranscriptMetadata,
        frontmatter: dict,
        filepath: Path
    ) -> tuple[bool, str | None]:
        """
        判斷檔案是否應該處理
        
        Args:
            metadata: 解析後的 metadata
            frontmatter: 原始 frontmatter 字典（包含 status 等 pipeline 欄位）
            filepath: 檔案路徑
            
        Returns:
            Tuple[should_process, reason]
            - should_process: True 表示應該處理
            - reason: 若不應該處理，原因說明；否則為 None
        """
        ...


class DiscoveryService(Protocol):
    """
    檔案發現服務介面
    
    整合掃描、解析、過濾流程，提供高階發現 API。
    """
    
    def discover(
        self,
        root_dir: Path,
        min_word_count: int = 100,
        channel_whitelist: list[str] | None = None,
        channel_blacklist: list[str] | None = None
    ) -> list[TranscriptFile]:
        """
        發現待處理的轉錄檔案
        
        完整流程：
        1. 掃描目錄中的所有 .md 檔案
        2. 解析 frontmatter 與 content
        3. 檢查 status 欄位，跳過已處理檔案
        4. 檢查字數，過濾過短內容
        5. 檢查頻道白名單/黑名單
        
        Args:
            root_dir: 掃描根目錄
            min_word_count: 最小字數限制（預設 100）
            channel_whitelist: 頻道白名單，None 表示不限制
            channel_blacklist: 頻道黑名單，None 表示不限制
            
        Returns:
            待處理的 TranscriptFile 列表
        """
        ...
    
    def get_statistics(self) -> DiscoveryStatistics:
        """
        取得發現統計資訊
        
        Returns:
            發現過程的統計資料
        """
        ...
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        清理過期的臨時檔案
        
        掃描 temp/ 目錄，刪除超過指定時間的殘留檔案。
        應在 discover() 執行前呼叫。
        
        Args:
            max_age_hours: 檔案保留時限（小時），預設 24
            
        Returns:
            刪除的檔案數量
        """
        ...


@dataclass
class DiscoveryStatistics:
    """
    發現過程統計
    
    Attributes:
        total_scanned: 掃描的檔案總數
        parsed_success: 成功解析的檔案數
        parsed_failed: 解析失敗的檔案數
        filtered_by_status: 因 status 被過濾的檔案數
        filtered_by_word_count: 因字數被過濾的檔案數
        filtered_by_channel: 因頻道限制被過濾的檔案數
        ready_to_process: 準備處理的檔案數
    """
    total_scanned: int = 0
    parsed_success: int = 0
    parsed_failed: int = 0
    filtered_by_status: int = 0
    filtered_by_word_count: int = 0
    filtered_by_channel: int = 0
    ready_to_process: int = 0


# ============================================================================
# 狀態檢查相關
# ============================================================================

class StatusChecker(Protocol):
    """
    狀態檢查器介面
    
    檢查檔案的 pipeline 處理狀態。
    """
    
    def get_status(self, frontmatter: dict) -> PipelineStatus | None:
        """
        取得檔案狀態
        
        Args:
            frontmatter: frontmatter 字典
            
        Returns:
            PipelineStatus 或 None（若無 status 欄位）
        """
        ...
    
    def is_processed(self, frontmatter: dict) -> bool:
        """
        檢查檔案是否已處理
        
        若 status 為 uploaded, approved, pending 則視為已處理。
        
        Args:
            frontmatter: frontmatter 字典
            
        Returns:
            True 表示已處理（應該跳過）
        """
        ...
    
    def should_retry(self, frontmatter: dict, force: bool = False) -> bool:
        """
        檢查失敗檔案是否應該重試
        
        邏輯：
        - 預設 (force=False): status=failed 時回傳 False（不重試，避免無窮迴圈）。
        - 強制 (force=True): status=failed 時回傳 True。
        
        Args:
            frontmatter: frontmatter 字典
            force: 是否強制重試失敗檔案
            
        Returns:
            True 表示應該重試
        """
        ...


# ============================================================================
# 例外定義
# ============================================================================

class DiscoveryError(Exception):
    """發現模組錯誤基類"""
    pass


class DirectoryNotFoundError(DiscoveryError):
    """掃描目錄不存在"""
    pass


class MetadataExtractionError(DiscoveryError):
    """Metadata 提取失敗"""
    pass


class FrontmatterParseError(DiscoveryError):
    """Frontmatter 解析失敗"""
    pass


# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. FileScanner
   - 正確遞迴掃描所有子目錄
   - 正確過濾 *.md 檔案
   - 正確處理空目錄

2. FrontmatterParser
   - 正確解析 YAML frontmatter（各種格式）
   - 正確分離 frontmatter 與 body
   - 無 frontmatter 時回傳空 dict
   - YAML 語法錯誤時拋出 FrontmatterParseError

3. TranscriptMetadataExtractor
   - 正確提取所有必要欄位
   - 正確解析日期格式
   - 從檔名解析 video_id（當 frontmatter 缺失時）
   - 缺少必要欄位時拋出 MetadataExtractionError

4. FileFilter / StatusChecker
   - status=uploaded/approved/pending 時正確跳過
   - status=failed 時視為可重試
   - word_count < min_word_count 時正確過濾
   - channel 在白名單/黑名單時正確處理

5. DiscoveryService (整合測試)
   - 完整流程：掃描 → 解析 → 過濾 → 輸出
   - 統計資訊正確
   - 錯誤檔案不中斷流程

執行驗收測試：
    python docs/interfaces/tests/test_discovery.py
"""
