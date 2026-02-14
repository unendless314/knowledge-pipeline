"""
Knowledge Pipeline - Uploader 模組

負責將分析完成的內容透過 API 上傳至 Open Notebook。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml

from src.models import (
    AnalyzedTranscript,
    NotebookLinkRequest,
    OpenNotebookConfig,
    SourceCreateRequest,
    SourceCreateResponse,
    SourceUpdateRequest,
)


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
# Upload Result & Statistics
# ============================================================================

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


# ============================================================================
# API Retry Strategy
# ============================================================================

class FixedDelayRetry:
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
    ):
        """
        初始化重試策略
        
        Args:
            max_attempts: 最大嘗試次數
            delay: 重試延遲（秒）
        """
        self.max_attempts = max_attempts
        self.delay = delay
    
    def should_retry(self, status_code: int | None, attempt: int) -> bool:
        """
        判斷是否應該重試
        
        Args:
            status_code: HTTP 狀態碼
            attempt: 當前嘗試次數
            
        Returns:
            True 表示應該重試
        """
        if attempt >= self.max_attempts:
            return False
        
        # 5xx 錯誤重試
        if status_code and 500 <= status_code < 600:
            return True
        
        # 429 Rate Limit 重試
        if status_code == 429:
            return True
        
        # Timeout (None) 重試
        if status_code is None:
            return True
        
        return False
    
    def get_delay(self, attempt: int) -> float:
        """
        取得重試延遲時間
        
        Args:
            attempt: 當前嘗試次數
            
        Returns:
            延遲秒數
        """
        return self.delay


# ============================================================================
# Open Notebook Client
# ============================================================================

class OpenNotebookClient:
    """
    Open Notebook API 客戶端
    
    封裝所有 ON API 呼叫，處理認證與錯誤重試。
    """
    
    def __init__(
        self,
        config: OpenNotebookConfig,
        retry_strategy: FixedDelayRetry | None = None
    ):
        """
        初始化客戶端
        
        Args:
            config: Open Notebook 配置
            retry_strategy: 重試策略
        """
        self.config = config
        self.retry_strategy = retry_strategy or FixedDelayRetry()
        self.session = requests.Session()
        
        # 設定認證 header
        self.session.headers.update({
            "Authorization": f"Bearer {config.password}",
            "Content-Type": "application/json"
        })
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> dict:
        """
        執行 HTTP 請求（含重試邏輯）
        
        Args:
            method: HTTP 方法
            endpoint: API 端點（不含 base_url）
            **kwargs: 額外參數
            
        Returns:
            回應 JSON
            
        Raises:
            APIError: API 錯誤
            AuthenticationError: 認證失敗
            SourceNotFoundError: Source 不存在
            NotebookNotFoundError: Notebook 不存在
            RateLimitError: 速率限制
        """
        url = urljoin(self.config.base_url, endpoint)
        
        for attempt in range(1, self.retry_strategy.max_attempts + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # 檢查狀態碼
                if response.status_code == 200 or response.status_code == 201:
                    return response.json() if response.text else {}
                
                if response.status_code == 401:
                    raise AuthenticationError("認證失敗，請檢查 API 密碼")
                
                if response.status_code == 404:
                    if "notebook" in endpoint.lower():
                        raise NotebookNotFoundError(f"Notebook 不存在: {endpoint}")
                    else:
                        raise SourceNotFoundError(f"Source 不存在: {endpoint}")
                
                if response.status_code == 429:
                    if self.retry_strategy.should_retry(429, attempt):
                        time.sleep(self.retry_strategy.get_delay(attempt))
                        continue
                    raise RateLimitError("API 速率限制")
                
                # 其他錯誤
                if self.retry_strategy.should_retry(response.status_code, attempt):
                    time.sleep(self.retry_strategy.get_delay(attempt))
                    continue
                
                raise APIError(
                    f"API 錯誤: {response.status_code} - {response.text}",
                    status_code=response.status_code
                )
                
            except requests.Timeout:
                if self.retry_strategy.should_retry(None, attempt):
                    time.sleep(self.retry_strategy.get_delay(attempt))
                    continue
                raise APIError("請求超時")
            
            except requests.RequestException as e:
                if self.retry_strategy.should_retry(None, attempt):
                    time.sleep(self.retry_strategy.get_delay(attempt))
                    continue
                raise APIError(f"請求失敗: {e}")
    
    def health_check(self) -> bool:
        """
        健康檢查
        
        呼叫 GET /health 確認服務可用。
        
        Returns:
            True 表示服務正常
        """
        try:
            response = self.session.get(
                urljoin(self.config.base_url, "/health"),
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
    
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
        data = {
            "type": request.type,
            "title": request.title,
            "content": request.content,
            "embed": request.embed
        }
        
        result = self._make_request("POST", "/api/sources/json", json=data)
        
        return SourceCreateResponse(
            id=result.get("id", ""),
            title=result.get("title", ""),
            content=result.get("full_text", ""),
            created_at=result.get("created", "")
        )
    
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
        data = {"topics": request.topics}
        
        # API 需要完整 ID (含 source: 前綴)
        # 確保 source_id 有前綴
        if not source_id.startswith("source:"):
            source_id = f"source:{source_id}"
        
        self._make_request("PUT", f"/api/sources/{source_id}", json=data)
    
    def link_source_to_notebook(
        self,
        notebook_id: str,
        source_id: str
    ) -> None:
        """
        將 Source 關聯至 Notebook
        
        呼叫 POST /api/notebooks/{id}/sources/{source_id}
        
        Args:
            notebook_id: Notebook ID（格式: "notebook:xxxxx"）
            source_id: Source ID（格式: "source:xxxxx"）
            
        Raises:
            APIError: API 呼叫失敗
            NotebookNotFoundError: Notebook 不存在
            SourceNotFoundError: Source 不存在
        """
        # API 需要完整 ID (含前綴)
        if not source_id.startswith("source:"):
            source_id = f"source:{source_id}"
        
        if not notebook_id.startswith("notebook:"):
            notebook_id = f"notebook:{notebook_id}"
        
        self._make_request(
            "POST",
            f"/api/notebooks/{notebook_id}/sources/{source_id}"
        )
    
    def ensure_notebook_exists(self, notebook_name: str) -> str:
        """
        確保 Notebook 存在
        
        若 Notebook 不存在則建立，回傳 Notebook ID。
        
        Args:
            notebook_name: Notebook 名稱
            
        Returns:
            Notebook ID
        """
        try:
            # 嘗試取得 Notebook 列表
            response = self._make_request("GET", "/api/notebooks")
            
            # API 直接回傳 list，不是 dict
            if isinstance(response, list):
                notebooks = response
            else:
                notebooks = response.get("notebooks", [])
            
            # 尋找是否存在
            for notebook in notebooks:
                if notebook.get("name") == notebook_name:
                    return notebook.get("id")
            
            # 不存在則建立
            create_response = self._make_request(
                "POST",
                "/api/notebooks",
                json={"name": notebook_name}
            )
            return create_response.get("id")
            
        except APIError:
            # 如果 API 不支援，假設 Notebook 已存在
            return notebook_name
    
    def trigger_embedding(self, source_id: str) -> None:
        """
        觸發 Source 嵌入 (Embedding)
        
        呼叫 POST /api/embed
        
        務必在 Topics 更新完成後呼叫，確保索引包含最新的 Metadata。
        
        Args:
            source_id: Source ID
            
        Raises:
            APIError: API 呼叫失敗
            SourceNotFoundError: Source 不存在
        """
        # 確保 source_id 有前綴
        if not source_id.startswith("source:"):
            source_id = f"source:{source_id}"
        
        # 呼叫正確的嵌入端點
        try:
            self._make_request("POST", "/api/embed", json={
                "item_id": source_id,
                "item_type": "source",
                "async_processing": False
            })
        except APIError as e:
            if e.status_code == 404:
                # 端點不存在，可能是舊版本，忽略錯誤
                pass
            else:
                raise  # 其他錯誤（500, 401 等）應該拋出
    
    def create_insight(
        self,
        source_id: str,
        transformation_id: str,
        model_id: str | None = None
    ) -> dict:
        """
        建立 Source Insight（觸發模型分析）
        
        呼叫 POST /api/sources/{source_id}/insights
        這是非同步操作，會立即回傳 202 Accepted，實際分析在背景執行。
        
        Args:
            source_id: Source ID
            transformation_id: Transformation ID（如 "transformation:xxx"）
            model_id: 可選，指定模型 ID（如 "model:xxx"）
            
        Returns:
            API 回應（包含 status, message, command_id）
        """
        # 確保 source_id 有前綴
        if not source_id.startswith("source:"):
            source_id = f"source:{source_id}"
        
        data = {"transformation_id": transformation_id}
        if model_id:
            data["model_id"] = model_id
        
        try:
            result = self._make_request(
                "POST",
                f"/api/sources/{source_id}/insights",
                json=data
            )
            return result if isinstance(result, dict) else {}
        except APIError as e:
            # 記錄錯誤但不拋出，避免影響上傳流程
            if e.status_code == 404:
                return {"status": "error", "message": "Insights API not available"}
            return {"status": "error", "message": str(e)}
    
    def get_transformations(self) -> list[dict]:
        """
        取得所有可用的 Transformations
        
        Returns:
            Transformation 列表
        """
        try:
            result = self._make_request("GET", "/api/transformations")
            return result if isinstance(result, list) else []
        except APIError:
            return []


# ============================================================================
# Source Builder
# ============================================================================

class SourceBuilder:
    """
    Source 請求建構器
    
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
            file_path: 分析後檔案路徑（若提供，從此檔案讀取內容）
            
        Returns:
            SourceCreateRequest
        """
        return SourceCreateRequest(
            type="text",
            title=self.build_title(analyzed),
            content=self.build_content(analyzed, file_path),
            embed=False  # 稍後手動觸發
        )
    
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
        topics = analyzed.analysis.key_topics.copy()
        
        # 加入建議的主題
        if analyzed.analysis.suggested_topic:
            suggested = analyzed.analysis.suggested_topic
            if suggested not in topics:
                topics.insert(0, suggested)
        
        return SourceUpdateRequest(topics=topics)
    
    def build_title(self, analyzed: AnalyzedTranscript) -> str:
        """
        建構 Source 標題
        
        格式: "{channel} | {title} | {published_at}"
        
        Args:
            analyzed: 分析完成的轉錄資料
            
        Returns:
            標題字串
        """
        original = analyzed.original
        published_at = original.published_at.isoformat()
        return f"{original.channel} | {original.title} | {published_at}"
    
    def build_content(self, analyzed: AnalyzedTranscript, file_path: Path | None = None) -> str:
        """
        建構 Source 內容
        
        包含完整的 frontmatter YAML + 轉錄內容。
        
        Args:
            analyzed: 分析完成的轉錄資料
            file_path: 分析後檔案路徑（若提供，從此檔案讀取內容）
            
        Returns:
            內容字串
        """
        original = analyzed.original
        analysis = analyzed.analysis
        processing = analyzed.processing
        
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
        
        # 序列化 YAML
        yaml_content = yaml.dump(
            frontmatter,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False
        )
        
        # 讀取內容 - 優先從提供的 file_path 讀取，否則回退到 source_path
        content = ""
        content_source = file_path if file_path else Path(processing.source_path)
        if content_source and content_source.exists():
            try:
                from src.discovery import FrontmatterParser
                _, content = FrontmatterParser().parse_file(content_source)
            except Exception:
                pass
        
        return f"""---
{yaml_content}---

{content}
"""


# ============================================================================
# Uploader Service
# ============================================================================

class UploaderService:
    """
    上傳服務
    
    整合 API 客戶端與請求建構，提供高階上傳 API。
    """
    
    def __init__(
        self,
        client: OpenNotebookClient,
        builder: SourceBuilder | None = None,
        auto_insights: bool = True,
        transformation_ids: list[str] | None = None
    ):
        """
        初始化上傳服務
        
        Args:
            client: Open Notebook 客戶端
            builder: Source 請求建構器
            auto_insights: 是否在上傳後自動生成 insights（預設 True）
            transformation_ids: 要執行的 transformation ID 列表，None 表示自動偵測
        """
        self.client = client
        self.builder = builder or SourceBuilder()
        self._stats = UploadStatistics()
        self.auto_insights = auto_insights
        self.transformation_ids = transformation_ids
        self._cached_transformations: list[str] | None = None
    
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
        2. 建立 Source
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
        self._stats.total_uploaded += 1
        start_time = time.time()
        
        try:
            # Step 1: 確保 Notebook 存在
            notebook_id = self.client.ensure_notebook_exists(notebook_name)
            
            # Step 2: 建立 Source（從分析後檔案讀取內容）
            create_request = self.builder.build_create_request(analyzed, file_path)
            create_response = self.client.create_source(create_request)
            source_id = create_response.id
            
            # Step 3: 更新 Topics
            update_request = self.builder.build_update_request(analyzed)
            self.client.update_source_topics(source_id, update_request)
            
            # Step 4: 關聯 Notebook
            self.client.link_source_to_notebook(notebook_id, source_id)
            
            # Step 5: 觸發嵌入
            self.client.trigger_embedding(source_id)
            
            # Step 6: 自動生成 Insights（背景執行，不等待結果）
            if self.auto_insights:
                self._trigger_insights_async(source_id)
            
            # 更新統計
            self._stats.successful += 1
            duration_ms = (time.time() - start_time) * 1000
            self._update_avg_duration(duration_ms)
            
            return source_id
            
        except APIError as e:
            self._stats.failed += 1
            raise UploadError(f"上傳失敗: {e}") from e
    
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
        results = []
        
        for analyzed, notebook_name in analyzed_list:
            try:
                source_id = self.upload(analyzed, notebook_name)
                results.append(UploadResult(success=True, source_id=source_id))
            except UploadError as e:
                results.append(UploadResult(
                    success=False,
                    error=str(e),
                    error_code="UPLOAD_ERROR"
                ))
        
        return results
    
    def get_statistics(self) -> UploadStatistics:
        """
        取得上傳統計資訊
        
        Returns:
            上傳過程的統計資料
        """
        return self._stats
    
    def _update_avg_duration(self, duration_ms: float) -> None:
        """
        更新平均耗時
        
        Args:
            duration_ms: 本次耗時（毫秒）
        """
        n = self._stats.successful
        if n == 1:
            self._stats.avg_duration_ms = duration_ms
        else:
            self._stats.avg_duration_ms = (
                (self._stats.avg_duration_ms * (n - 1) + duration_ms) / n
            )
    
    def _trigger_insights_async(self, source_id: str) -> None:
        """
        非同步觸發 Insights 生成（背景執行，不等待結果）
        
        根據設定執行一個或多個 transformation：
        - 若設定了 transformation_ids，使用指定的 IDs
        - 否則自動偵測可用的 transformation（優先使用 Key Insights）
        
        Args:
            source_id: Source ID
        """
        try:
            # 取得要執行的 transformation IDs
            trans_ids = self.transformation_ids
            
            if trans_ids is None:
                # 自動偵測：快取並尋找 "Key Insights"
                if self._cached_transformations is None:
                    transformations = self.client.get_transformations()
                    self._cached_transformations = []
                    
                    # 優先順序：Key Insights > Simple Summary > 第一個可用
                    priority_names = ["Key Insights", "Simple Summary", "Dense Summary"]
                    for priority in priority_names:
                        for t in transformations:
                            if t.get("name") == priority:
                                self._cached_transformations.append(t.get("id"))
                                break
                        if self._cached_transformations:
                            break
                    
                    # 如果都沒找到，使用第一個
                    if not self._cached_transformations and transformations:
                        self._cached_transformations = [transformations[0].get("id")]
                
                trans_ids = self._cached_transformations
            
            # 執行每個 transformation（不等待結果）
            for trans_id in trans_ids:
                if trans_id:
                    result = self.client.create_insight(source_id, trans_id)
                    # 只記錄成功/失敗，不拋出錯誤
                    if result.get("status") == "pending":
                        pass  # 背景執行中，這是預期結果
                        
        except Exception:
            # 完全忽略 insights 相關錯誤，不影響上傳流程
            pass
