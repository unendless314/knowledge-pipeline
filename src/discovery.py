"""
Knowledge Pipeline - Discovery 模組

負責掃描 YouTube Transcriber 輸出目錄，識別需要處理的新增轉錄稿。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

import yaml

from src.models import PipelineStatus, TranscriptFile, TranscriptMetadata


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
# Discovery Statistics
# ============================================================================

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
# File Scanner
# ============================================================================

class FileScanner:
    """
    檔案掃描器
    
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
        root_path = Path(root_dir)
        
        if not root_path.exists():
            raise DirectoryNotFoundError(f"掃描目錄不存在: {root_dir}")
        
        if not root_path.is_dir():
            raise DirectoryNotFoundError(f"路徑不是目錄: {root_dir}")
        
        # 遞迴搜尋所有符合 pattern 的檔案
        for file_path in root_path.rglob(pattern):
            if file_path.is_file():
                yield file_path


# ============================================================================
# Frontmatter Parser
# ============================================================================

class FrontmatterParser:
    """
    Frontmatter 解析器
    
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
            
        Raises:
            FrontmatterParseError: YAML 語法錯誤
        """
        content = content.strip()
        
        # 檢查是否有 frontmatter（以 --- 開頭）
        if not content.startswith("---"):
            return {}, content
        
        # 尋找結束的 ---
        # 從第 3 個字元開始找（跳過開頭的 ---）
        end_match = content.find("\n---", 3)
        
        if end_match == -1:
            # 沒有找到結束標記，視為無 frontmatter
            return {}, content
        
        # 提取 frontmatter 內容
        frontmatter_text = content[3:end_match].strip()
        body_content = content[end_match + 4:].strip()
        
        # 解析 YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise FrontmatterParseError(f"YAML 解析失敗: {e}") from e
        
        return frontmatter, body_content
    
    def parse_file(self, filepath: Path) -> tuple[dict, str]:
        """
        解析 Markdown 檔案
        
        Args:
            filepath: Markdown 檔案路徑
            
        Returns:
            Tuple[frontmatter_dict, body_content]
            
        Raises:
            FileNotFoundError: 檔案不存在
            FrontmatterParseError: 解析失敗
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"檔案不存在: {filepath}")
        
        content = filepath.read_text(encoding="utf-8")
        return self.parse(content)


# ============================================================================
# Transcript Metadata Extractor
# ============================================================================

class TranscriptMetadataExtractor:
    """
    轉錄 Metadata 提取器
    
    從 frontmatter 字典提取結構化的 TranscriptMetadata。
    """
    
    # 必要的欄位
    REQUIRED_FIELDS = ["channel", "video_id", "title", "published_at"]
    
    def extract(
        self,
        frontmatter: dict,
        filepath: Path | None = None
    ) -> TranscriptMetadata:
        """
        提取 metadata
        
        Args:
            frontmatter: YAML frontmatter 解析後的字典
            filepath: 檔案路徑（用於錯誤報告和提取 video_id）
            
        Returns:
            TranscriptMetadata 實例
            
        Raises:
            MetadataExtractionError: 缺少必要欄位或格式錯誤
        """
        # 檢查必要欄位
        missing_fields = [
            field for field in self.REQUIRED_FIELDS
            if field not in frontmatter or frontmatter[field] is None
        ]
        
        if missing_fields:
            # 嘗試從檔名提取 video_id
            if "video_id" in missing_fields and filepath:
                try:
                    video_id = self.extract_video_id(filepath, frontmatter)
                    frontmatter = {**frontmatter, "video_id": video_id}
                    missing_fields.remove("video_id")
                except MetadataExtractionError:
                    pass
            
            if missing_fields:
                raise MetadataExtractionError(
                    f"缺少必要欄位: {', '.join(missing_fields)}"
                )
        
        # 解析 published_at
        published_at = self._parse_date(frontmatter["published_at"])
        
        # 提取 duration（可選）
        duration = frontmatter.get("duration", "")
        
        # 提取 word_count（可選，預設 0）
        word_count = frontmatter.get("word_count", 0) or 0
        
        return TranscriptMetadata(
            channel=frontmatter["channel"],
            video_id=frontmatter["video_id"],
            title=frontmatter["title"],
            published_at=published_at,
            duration=duration,
            word_count=word_count
        )
    
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
            
        Raises:
            MetadataExtractionError: 無法提取 video_id
        """
        # 優先從 frontmatter 取得
        if "video_id" in frontmatter and frontmatter["video_id"]:
            return frontmatter["video_id"]
        
        # 從檔名解析
        # 檔名格式: {published_at}_{video_id}_{slug}.md
        # 例如: 2026-02-05_h7zj0SDWmkw_AI-on-Ethereum.md
        filename = filepath.stem  # 不含副檔名
        
        # YouTube Video ID 格式：11個英數字和 -_
        # 嘗試匹配常見 pattern
        patterns = [
            r"^\d{4}-\d{2}-\d{2}_([A-Za-z0-9_-]{11})_",  # 日期前綴
            r"^\d{8}_([A-Za-z0-9_-]{11})_",  # 無分隔日期
            r"_([A-Za-z0-9_-]{11})_",  # 任意位置
            r"([A-Za-z0-9_-]{11})$",  # 結尾
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                video_id = match.group(1)
                # 驗證：YouTube ID 通常是 11 碼
                if len(video_id) == 11:
                    return video_id
        
        # 嘗試直接從檔名提取 11 碼的英數字
        video_id_match = re.search(r"([A-Za-z0-9_-]{11})", filename)
        if video_id_match:
            return video_id_match.group(1)
        
        raise MetadataExtractionError(
            f"無法從檔名提取 video_id: {filepath.name}"
        )
    
    def _parse_date(self, date_value) -> date:
        """
        解析日期值
        
        支援格式:
        - date 物件
        - datetime 物件
        - 字串: YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD
        """
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        if isinstance(date_value, str):
            # 嘗試多種格式
            formats = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y%m%d",
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_value.strip(), fmt).date()
                except ValueError:
                    continue
            
            raise MetadataExtractionError(f"無法解析日期格式: {date_value}")
        
        raise MetadataExtractionError(f"不支援的日期類型: {type(date_value)}")


# ============================================================================
# Status Checker
# ============================================================================

class StatusChecker:
    """
    狀態檢查器
    
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
        status_str = frontmatter.get("status")
        
        if not status_str:
            return None
        
        try:
            return PipelineStatus(status_str)
        except ValueError:
            return None
    
    def is_processed(self, frontmatter: dict) -> bool:
        """
        檢查檔案是否已處理
        
        若 status 為 uploaded, approved, pending 則視為已處理。
        
        Args:
            frontmatter: frontmatter 字典
            
        Returns:
            True 表示已處理（應該跳過）
        """
        status = self.get_status(frontmatter)
        
        if status is None:
            return False
        
        return status in (
            PipelineStatus.UPLOADED,
            PipelineStatus.APPROVED,
            PipelineStatus.PENDING
        )
    
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
        status = self.get_status(frontmatter)
        
        # 無 status 或 None，視為新檔案，應該處理
        if status is None:
            return True
        
        # failed 狀態
        if status == PipelineStatus.FAILED:
            return force
        
        # 其他狀態（uploaded, approved, pending）視為已處理
        return False


# ============================================================================
# File Filter
# ============================================================================

class FileFilter:
    """
    檔案過濾器
    
    根據各種條件過濾檔案。
    """
    
    def __init__(
        self,
        status_checker: StatusChecker | None = None,
        min_word_count: int = 100
    ):
        """
        初始化檔案過濾器
        
        Args:
            status_checker: 狀態檢查器實例
            min_word_count: 最小字數限制
        """
        self.status_checker = status_checker or StatusChecker()
        self.min_word_count = min_word_count
    
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
        # 檢查 status
        if self.status_checker.is_processed(frontmatter):
            status = self.status_checker.get_status(frontmatter)
            return False, f"已處理 (status={status.value})"
        
        # 檢查字數
        if metadata.word_count < self.min_word_count:
            return False, f"字數不足 ({metadata.word_count} < {self.min_word_count})"
        
        return True, None
    
    def filter_by_channel(
        self,
        metadata: TranscriptMetadata,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None
    ) -> tuple[bool, str | None]:
        """
        根據頻道過濾
        
        Args:
            metadata: 轉錄 metadata
            whitelist: 頻道白名單，None 表示不限制
            blacklist: 頻道黑名單，None 表示不限制
            
        Returns:
            Tuple[should_process, reason]
        """
        channel = metadata.channel
        
        # 檢查白名單
        if whitelist is not None and channel not in whitelist:
            return False, f"頻道不在白名單中 ({channel})"
        
        # 檢查黑名單
        if blacklist is not None and channel in blacklist:
            return False, f"頻道在黑名單中 ({channel})"
        
        return True, None


# ============================================================================
# Discovery Service
# ============================================================================

class DiscoveryService:
    """
    檔案發現服務
    
    整合掃描、解析、過濾流程，提供高階發現 API。
    """
    
    def __init__(
        self,
        scanner: FileScanner | None = None,
        parser: FrontmatterParser | None = None,
        extractor: TranscriptMetadataExtractor | None = None,
        status_checker: StatusChecker | None = None,
        file_filter: FileFilter | None = None,
        temp_dir: Path | None = None
    ):
        """
        初始化發現服務
        
        Args:
            scanner: 檔案掃描器
            parser: Frontmatter 解析器
            extractor: Metadata 提取器
            status_checker: 狀態檢查器
            file_filter: 檔案過濾器
            temp_dir: 臨時檔案目錄
        """
        self.scanner = scanner or FileScanner()
        self.parser = parser or FrontmatterParser()
        self.extractor = extractor or TranscriptMetadataExtractor()
        self.status_checker = status_checker or StatusChecker()
        self.file_filter = file_filter or FileFilter(self.status_checker)
        self.temp_dir = temp_dir or Path("temp")
        
        self._stats = DiscoveryStatistics()
    
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
        # 重置統計
        self._stats = DiscoveryStatistics()
        
        # 更新過濾器的最小字數
        self.file_filter.min_word_count = min_word_count
        
        results: list[TranscriptFile] = []
        
        # 掃描所有檔案
        for file_path in self.scanner.scan(root_dir):
            self._stats.total_scanned += 1
            
            try:
                # 解析 frontmatter
                frontmatter, content = self.parser.parse_file(file_path)
                self._stats.parsed_success += 1
                
                # 提取 metadata
                metadata = self.extractor.extract(frontmatter, file_path)
                
                # 檢查是否應該處理
                should_process, reason = self.file_filter.should_process(
                    metadata, frontmatter, file_path
                )
                
                if not should_process:
                    if "已處理" in reason:
                        self._stats.filtered_by_status += 1
                    elif "字數" in reason:
                        self._stats.filtered_by_word_count += 1
                    continue
                
                # 檢查頻道限制
                should_process, reason = self.file_filter.filter_by_channel(
                    metadata, channel_whitelist, channel_blacklist
                )
                
                if not should_process:
                    self._stats.filtered_by_channel += 1
                    continue
                
                # 取得 status
                status = self.status_checker.get_status(frontmatter)
                source_id = frontmatter.get("source_id")
                
                # 建立 TranscriptFile
                transcript = TranscriptFile(
                    path=file_path,
                    metadata=metadata,
                    content=content,
                    status=status,
                    source_id=source_id
                )
                
                results.append(transcript)
                self._stats.ready_to_process += 1
                
            except (FrontmatterParseError, MetadataExtractionError) as e:
                self._stats.parsed_failed += 1
                # 記錄錯誤但繼續處理
                continue
            except Exception as e:
                self._stats.parsed_failed += 1
                continue
        
        return results
    
    def get_statistics(self) -> DiscoveryStatistics:
        """
        取得發現統計資訊
        
        Returns:
            發現過程的統計資料
        """
        return self._stats
    
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
        if not self.temp_dir.exists():
            return 0
        
        deleted_count = 0
        max_age = datetime.now().timestamp() - (max_age_hours * 3600)
        
        for file_path in self.temp_dir.iterdir():
            if file_path.is_file():
                try:
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < max_age:
                        file_path.unlink()
                        deleted_count += 1
                except OSError:
                    pass
        
        return deleted_count
