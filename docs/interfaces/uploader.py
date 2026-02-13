"""
Knowledge Pipeline - Open Notebook 上傳模組介面定義

此模組負責將分析完成的內容透過 API 上傳至 Open Notebook。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from models import (
    AnalyzedTranscript,
    OpenNotebookConfig,
    SourceCreateRequest,
    SourceCreateResponse,
    SourceUpdateRequest,
)


class OpenNotebookClient(Protocol):
    """
    Open Notebook API 客戶端介面
    
    封裝所有 ON API 呼叫，處理認證與錯誤重試。
    """
    
    def __init__(self, config: OpenNotebookConfig): ...
    
    def health_check(self) -> bool:
        """
        健康檢查
        
        呼叫 GET /health 確認服務可用。
        
        Returns:
            True 表示服務正常
        """
        ...
    
    def create_source(
        self,
        request: SourceCreateRequest
    ) -> SourceCreateResponse:
        """
        建立 Source
        
        呼叫 POST /api/sources/json（注意：不是 /api/sources）
        
        Args:
            request: 建立請求
            
        Returns:
            建立成功的回應（包含 source_id）
            
        Raises:
            APIError: API 呼叫失敗
            AuthenticationError: 認證失敗
        """
        ...
    
    def update_source_topics(
        self,
        source_id: str,
        request: SourceUpdateRequest
    ) -> None:
        """
        更新 Source Topics
        
        呼叫 PUT /api/sources/{id}
        
        ⚠️ 注意：topics 必須在建立後用 PUT 更新，
        無法在 create_source 時一起設定。
        
        Args:
            source_id: Source ID（格式: "source:xxxxx"）
            request: 更新請求
            
        Raises:
            APIError: API 呼叫失敗
            SourceNotFoundError: Source 不存在
        """
        ...
    
    def link_source_to_notebook(
        self,
        notebook_id: str,
        source_id: str
    ) -> None:
        """
        將 Source 關聯至 Notebook
        
        呼叫 POST /api/notebooks/{id}/sources/{source_id}
        
        Args:
            notebook_id: Notebook ID
            source_id: Source ID
            
        Raises:
            APIError: API 呼叫失敗
            NotebookNotFoundError: Notebook 不存在
            SourceNotFoundError: Source 不存在
        """
        ...
    
    def ensure_notebook_exists(
        self,
        notebook_name: str
    ) -> str:
        """
        確保 Notebook 存在
        
        若 Notebook 不存在則建立，回傳 Notebook ID。
        
        Args:
            notebook_name: Notebook 名稱
            
        Returns:
            Notebook ID
        """
        ...

    def trigger_embedding(
        self,
        source_id: str
    ) -> None:
        """
        觸發 Source 嵌入 (Embedding)
        
        呼叫 POST /api/embed (或對應端點)
        
        務必在 Topics 更新完成後呼叫，確保索引包含最新的 Metadata。
        
        Args:
            source_id: Source ID
            
        Raises:
            APIError: API 呼叫失敗
            SourceNotFoundError: Source 不存在
        """
        ...


class SourceBuilder(Protocol):
    """
    Source 請求建構器介面
    
    將 AnalyzedTranscript 轉換為 API 請求格式。
    """
    
    def build_create_request(
        self,
        analyzed: AnalyzedTranscript,
        file_path: Path | None = None
    ) -> SourceCreateRequest:
        """
        建構建立 Source 請求
        
        Args:
            analyzed: 分析完成的轉錄資料
            file_path: 分析後檔案路徑（若提供，從此檔案讀取內容而非原始檔案）
            
        Returns:
            SourceCreateRequest
        """
        ...
    
    def build_update_request(
        self,
        analyzed: AnalyzedTranscript
    ) -> SourceUpdateRequest:
        """
        建構更新 Topics 請求
        
        Args:
            analyzed: 分析完成的轉錄資料
            
        Returns:
            SourceUpdateRequest
        """
        ...
    
    def build_title(self, analyzed: AnalyzedTranscript) -> str:
        """
        建構 Source 標題
        
        格式: "{channel} | {title} | {published_at}"
        
        Args:
            analyzed: 分析完成的轉錄資料
            
        Returns:
            標題字串
        """
        ...
    
    def build_content(self, analyzed: AnalyzedTranscript, file_path: Path | None = None) -> str:
        """
        建構 Source 內容
        
        包含完整的 frontmatter YAML + 轉錄內容。
        
        ⚠️ 重要：必須從分析後檔案（*_analyzed.md）讀取內容，而非原始檔案。
        原始檔案（processing.source_path）可能含 timestamps 等未清理內容。
        
        Args:
            analyzed: 分析完成的轉錄資料
            file_path: 分析後檔案路徑（若提供，從此檔案讀取內容）
            
        Returns:
            內容字串
        """
        ...


class UploaderService(Protocol):
    """
    上傳服務介面
    
    整合 API 客戶端與請求建構，提供高階上傳 API。
    """
    
    def upload(
        self,
        analyzed: AnalyzedTranscript,
        notebook_name: str,
        file_path: Path | None = None
    ) -> str:
        """
        上傳單個分析結果
        
        完整流程：
        1. 確保 Notebook 存在
        2. 建立 Source（從 file_path 讀取分析後內容）
        3. 更新 Topics
        4. 關聯 Notebook
        
        Args:
            analyzed: 分析完成的轉錄資料
            notebook_name: 目標 Notebook 名稱
            file_path: 分析後檔案路徑（用於讀取清理後的內容）
            
        Returns:
            Source ID（格式: "source:xxxxx"）
            
        Raises:
            UploadError: 上傳過程中發生錯誤（已重試後仍失敗）
        """
        ...
    
    def upload_batch(
        self,
        analyzed_list: list[tuple[AnalyzedTranscript, str]]
    ) -> list[UploadResult]:
        """
        批次上傳多個分析結果
        
        Args:
            analyzed_list: (AnalyzedTranscript, notebook_name) 元組列表
            
        Returns:
            UploadResult 列表（順序與輸入相同）
        """
        ...
    
    def get_statistics(self) -> UploadStatistics:
        """
        取得上傳統計資訊
        
        Returns:
            上傳過程的統計資料
        """
        ...


@dataclass
class UploadResult:
    """
    單個上傳結果
    
    Attributes:
        success: 是否成功
        source_id: Source ID（成功時有值）
        error: 錯誤訊息（失敗時有值）
        error_code: 錯誤代碼（失敗時有值）
    """
    success: bool
    source_id: str | None = None
    error: str | None = None
    error_code: str | None = None


@dataclass
class UploadStatistics:
    """
    上傳過程統計
    
    Attributes:
        total_uploaded: 上傳的檔案總數
        successful: 成功上傳數
        failed: 失敗數
        retried: 發生重試的次數
        avg_duration_ms: 平均上傳耗時（毫秒）
    """
    total_uploaded: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    avg_duration_ms: float = 0.0


class APIRetryStrategy(Protocol):
    """
    API 重試策略介面
    
    不同於 LLM 的重試策略，API 重試使用固定間隔。
    """
    
    def should_retry(self, status_code: int, attempt: int) -> bool:
        """
        判斷是否應該重試
        
        Args:
            status_code: HTTP 狀態碼
            attempt: 當前嘗試次數
            
        Returns:
            True 表示應該重試
        """
        ...
    
    def get_delay(self, attempt: int) -> float:
        """
        取得重試延遲時間
        
        Args:
            attempt: 當前嘗試次數
            
        Returns:
            延遲秒數
        """
        ...


class FixedDelayRetry(APIRetryStrategy, Protocol):
    """
    固定延遲重試策略
    
    適用於 API 呼叫，固定間隔重試。
    例如：5s -> 5s -> 5s
    
    重試條件：
    - 5xx 錯誤
    - 429 Rate Limit
    - Timeout
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 5.0
    ): ...


# ============================================================================
# 例外定義
# ============================================================================

class UploadError(Exception):
    """上傳模組錯誤基類"""
    pass


class APIError(UploadError):
    """API 呼叫錯誤"""
    
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(APIError):
    """認證失敗（401）"""
    pass


class SourceNotFoundError(APIError):
    """Source 不存在（404）"""
    pass


class NotebookNotFoundError(APIError):
    """Notebook 不存在（404）"""
    pass


class RateLimitError(APIError):
    """速率限制（429）"""
    pass


# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. OpenNotebookClient
   - 正確設定 Authorization: Bearer header
   - health_check() 正確判斷服務狀態
   - create_source() 使用正確的端點 (/api/sources/json)
   - update_source_topics() 在建立後正確執行
   - 正確處理各種 HTTP 錯誤碼

2. SourceBuilder
   - title 格式正確: "{channel} | {title} | {published_at}"
   - content 包含完整的 frontmatter YAML
   - content 中的 YAML 可被正確解析

3. UploaderService
   - 完整流程：確保 Notebook -> 建立 Source -> 更新 Topics -> 關聯
   - 批次處理不中斷（單一失敗不影響其他）
   - 回傳的 source_id 格式正確（source:xxxxx）

4. APIRetryStrategy
   - 5xx 錯誤正確重試
   - 429 錯誤正確重試
   - 4xx 錯誤（除 429）不重試
   - 固定延遲時間正確

5. 錯誤處理
   - 認證錯誤（401）拋出 AuthenticationError
   - 資源不存在（404）拋出對應 NotFoundError
   - 速率限制（429）拋出 RateLimitError

執行驗收測試：
    python docs/interfaces/tests/test_uploader.py
"""
