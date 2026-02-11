"""
Knowledge Pipeline - 配置管理模組介面定義

此模組負責載入與驗證系統配置。
實作時需確保配置來源的正確優先順序。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from models import PipelineConfig, TopicConfig, ChannelConfig


class ConfigLoader(Protocol):
    """
    配置載入器介面
    
    負責從各種來源載入配置，並處理優先順序：
    1. 預設值（最低優先）
    2. 配置文件（config/config.yaml, config/topics.yaml）
    3. 環境變數（最高優先）
    """
    
    def load_pipeline_config(self, config_path: Path | None = None) -> PipelineConfig:
        """
        載入 Pipeline 主要配置
        
        Args:
            config_path: 配置文件路徑，預設為 "config/config.yaml"
            
        Returns:
            PipelineConfig 實例
            
        Raises:
            ConfigNotFoundError: 配置文件不存在
            ConfigValidationError: 配置格式錯誤
        """
        ...
    
    def load_topics_config(self, topics_path: Path | None = None) -> dict[str, TopicConfig]:
        """
        載入主題配置
        
        Args:
            topics_path: 主題配置文件路徑，預設為 "config/topics.yaml"
            
        Returns:
            主題 ID 到 TopicConfig 的對應字典
            
        Raises:
            ConfigNotFoundError: 配置文件不存在
            ConfigValidationError: 配置格式錯誤
        """
        ...
    
    def load_channels_config(self, topics_path: Path | None = None) -> dict[str, ChannelConfig]:
        """
        載入頻道預設配置
        
        從 topics.yaml 的 channels 區段讀取。
        
        Args:
            topics_path: 主題配置文件路徑，預設為 "config/topics.yaml"
            
        Returns:
            頻道名稱到 ChannelConfig 的對應字典
        """
        ...


class ConfigValidator(Protocol):
    """
    配置驗證器介面
    
    驗證配置內容的有效性，包括：
    - 路徑是否存在且可存取
    - URL 格式是否正確
    - 數值範圍是否合理
    - 必要欄位是否齊全
    """
    
    def validate_pipeline_config(self, config: PipelineConfig) -> list[str]:
        """
        驗證 Pipeline 配置
        
        Args:
            config: 待驗證的配置
            
        Returns:
            錯誤訊息列表，空列表表示驗證通過
        """
        ...
    
    def validate_topics_config(self, topics: dict[str, TopicConfig]) -> list[str]:
        """
        驗證主題配置
        
        Args:
            topics: 主題配置字典
            
        Returns:
            錯誤訊息列表，空列表表示驗證通過
        """
        ...


class EnvironmentProvider(Protocol):
    """
    環境變數提供者介面
    
    提供環境變數覆蓋機制，支援：
    - OPEN_NOTEBOOK_PASSWORD: ON API 密碼
    - TRANSCRIBER_OUTPUT_PATH: 覆蓋輸入路徑
    - INTERMEDIATE_PATH: 覆蓋中間態路徑
    """
    
    def get_open_notebook_password(self) -> str | None:
        """取得 Open Notebook API 密碼"""
        ...
    
    def get_transcriber_output_path(self) -> str | None:
        """取得覆蓋的輸入路徑"""
        ...
    
    def get_intermediate_path(self) -> str | None:
        """取得覆蓋的中間態路徑"""
        ...


class TopicResolver(Protocol):
    """
    主題解析器介面
    
    根據頻道名稱與 LLM 建議決定最終主題分類。
    """
    
    def resolve_topic(
        self,
        channel: str,
        suggested_topic: str | None,
        topics_config: dict[str, TopicConfig],
        channels_config: dict[str, ChannelConfig]
    ) -> str:
        """
        解析最終主題
        
        解析邏輯：
        1. 優先使用 suggested_topic（如果有效）
        2. 否則使用 channels_config 中的預設主題
        3. 否則使用第一個可用的主題
        
        Args:
            channel: 頻道名稱
            suggested_topic: LLM 建議的主題 ID
            topics_config: 所有主題配置
            channels_config: 所有頻道配置
            
        Returns:
            最終主題 ID
        """
        ...
    
    def get_notebook_for_topic(
        self,
        topic_id: str,
        topics_config: dict[str, TopicConfig]
    ) -> str:
        """
        取得主題對應的 Notebook 名稱
        
        Args:
            topic_id: 主題 ID
            topics_config: 主題配置
            
        Returns:
            Notebook 名稱
            
        Raises:
            TopicNotFoundError: 主題不存在
        """
        ...
    
    def get_prompt_template_for_topic(
        self,
        topic_id: str,
        topics_config: dict[str, TopicConfig]
    ) -> str:
        """
        取得主題對應的 prompt template 名稱
        
        Args:
            topic_id: 主題 ID
            topics_config: 主題配置
            
        Returns:
            Prompt template 名稱（如 "crypto_tech"）
        """
        ...


class PromptLoader(Protocol):
    """
    Prompt 載入器介面
    
    從 prompts/analysis/ 目錄載入 LLM 分析用的 prompt 檔案。
    """
    
    def load_analysis_prompt(
        self,
        template_name: str,
        prompts_dir: Path | None = None
    ) -> str:
        """
        載入分析 prompt
        
        Args:
            template_name: Prompt template 名稱（如 "default", "crypto_tech"）
            prompts_dir: Prompt 檔案目錄，預設為 "prompts/analysis/"
            
        Returns:
            Prompt 文字內容
            
        Raises:
            PromptNotFoundError: Prompt 檔案不存在
        """
        ...


# ============================================================================
# 例外定義
# ============================================================================

class ConfigError(Exception):
    """配置相關錯誤基類"""
    pass


class ConfigNotFoundError(ConfigError):
    """配置文件不存在"""
    pass


class ConfigValidationError(ConfigError):
    """配置驗證失敗"""
    pass


class TopicNotFoundError(ConfigError):
    """主題不存在"""
    pass


class PromptNotFoundError(ConfigError):
    """Prompt 檔案不存在"""
    pass


# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. ConfigLoader
   - 正確載入 config.yaml 與 topics.yaml
   - 環境變數正確覆蓋配置檔案值
   - 缺失必要欄位時拋出 ConfigValidationError

2. ConfigValidator
   - 檢測不存在的路徑並回報錯誤
   - 檢測無效的 URL 格式
   - 檢測負數或過大的數值

3. TopicResolver
   - 優先使用 suggested_topic
   - 其次使用 channel 的預設主題
   - 正確解析 notebook 名稱

4. PromptLoader
   - 正確載入指定 template
   - 檔案不存在時拋出 PromptNotFoundError
   - 回傳內容為純文字（無 frontmatter 等額外格式）

執行驗收測試：
    python docs/interfaces/tests/test_config.py
"""
