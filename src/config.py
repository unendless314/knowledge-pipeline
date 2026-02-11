"""
Knowledge Pipeline - 配置管理模組

負責載入與驗證系統配置，支援環境變數覆蓋。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from src.models import (
    PipelineConfig,
    OpenNotebookConfig,
    TopicConfig,
    ChannelConfig,
)


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
# 環境變數提供者
# ============================================================================


class EnvironmentProvider:
    """
    環境變數提供者
    
    提供環境變數覆蓋機制。
    """
    
    ENV_OPEN_NOTEBOOK_PASSWORD = "OPEN_NOTEBOOK_PASSWORD"
    ENV_TRANSCRIBER_OUTPUT_PATH = "TRANSCRIBER_OUTPUT_PATH"
    ENV_INTERMEDIATE_PATH = "INTERMEDIATE_PATH"
    
    def get_open_notebook_password(self) -> str | None:
        """取得 Open Notebook API 密碼"""
        return os.environ.get(self.ENV_OPEN_NOTEBOOK_PASSWORD)
    
    def get_transcriber_output_path(self) -> str | None:
        """取得覆蓋的輸入路徑"""
        return os.environ.get(self.ENV_TRANSCRIBER_OUTPUT_PATH)
    
    def get_intermediate_path(self) -> str | None:
        """取得覆蓋的中間態路徑"""
        return os.environ.get(self.ENV_INTERMEDIATE_PATH)


# ============================================================================
# 配置載入器
# ============================================================================


class ConfigLoader:
    """
    配置載入器
    
    負責從各種來源載入配置，並處理優先順序：
    1. 預設值（最低優先）
    2. 配置文件
    3. 環境變數（最高優先）
    """
    
    def __init__(self, env_provider: EnvironmentProvider | None = None):
        self.env = env_provider or EnvironmentProvider()
    
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
        if config_path is None:
            config_path = Path("config/config.yaml")
        
        if not config_path.exists():
            raise ConfigNotFoundError(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML 解析錯誤: {e}") from e
        
        # 解析路徑
        transcriber_output = Path(data["paths"]["transcriber_output"])
        intermediate = Path(data["paths"]["intermediate"])
        
        # 環境變數覆蓋
        env_transcriber = self.env.get_transcriber_output_path()
        if env_transcriber:
            transcriber_output = Path(env_transcriber)
        
        env_intermediate = self.env.get_intermediate_path()
        if env_intermediate:
            intermediate = Path(env_intermediate)
        
        # Open Notebook 配置
        on_password = data["open_notebook"].get("password", "")
        env_password = self.env.get_open_notebook_password()
        if env_password:
            on_password = env_password
        
        open_notebook = OpenNotebookConfig(
            base_url=data["open_notebook"]["base_url"],
            password=on_password,
        )
        
        # 批次設定（使用預設值若未指定）
        batch = data.get("batch", {})
        
        return PipelineConfig(
            transcriber_output=transcriber_output,
            intermediate=intermediate,
            open_notebook=open_notebook,
            min_word_count=data.get("min_word_count", 100),
            max_concurrent=batch.get("max_concurrent", 3),
            retry_attempts=batch.get("retry_attempts", 3),
            retry_delay=batch.get("retry_delay", 5),
        )
    
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
        if topics_path is None:
            topics_path = Path("config/topics.yaml")
        
        if not topics_path.exists():
            raise ConfigNotFoundError(f"主題配置文件不存在: {topics_path}")
        
        try:
            with open(topics_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML 解析錯誤: {e}") from e
        
        topics = {}
        for topic_id, topic_data in data.get("topics", {}).items():
            topics[topic_id] = TopicConfig(
                name=topic_data["name"],
                description=topic_data["description"],
                notebook=topic_data["notebook"],
                prompt_template=topic_data["prompt_template"],
                channels=topic_data.get("channels", []),
            )
        
        return topics
    
    def load_channels_config(self, topics_path: Path | None = None) -> dict[str, ChannelConfig]:
        """
        載入頻道預設配置
        
        從 topics.yaml 的 channels 區段讀取。
        
        Args:
            topics_path: 主題配置文件路徑，預設為 "config/topics.yaml"
            
        Returns:
            頻道名稱到 ChannelConfig 的對應字典
        """
        if topics_path is None:
            topics_path = Path("config/topics.yaml")
        
        if not topics_path.exists():
            raise ConfigNotFoundError(f"主題配置文件不存在: {topics_path}")
        
        try:
            with open(topics_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML 解析錯誤: {e}") from e
        
        channels = {}
        for channel_name, channel_data in data.get("channels", {}).items():
            channels[channel_name] = ChannelConfig(
                default_topic=channel_data["default_topic"],
            )
        
        return channels


# ============================================================================
# 配置驗證器
# ============================================================================


class ConfigValidator:
    """
    配置驗證器
    
    驗證配置內容的有效性。
    """
    
    def validate_pipeline_config(self, config: PipelineConfig) -> list[str]:
        """
        驗證 Pipeline 配置
        
        Args:
            config: 待驗證的配置
            
        Returns:
            錯誤訊息列表，空列表表示驗證通過
        """
        errors = []
        
        # 驗證路徑
        if not config.transcriber_output.exists():
            errors.append(f"Transcriber 輸出目錄不存在: {config.transcriber_output}")
        
        if not config.transcriber_output.is_dir():
            errors.append(f"Transcriber 輸出路徑不是目錄: {config.transcriber_output}")
        
        # 驗證 URL
        try:
            result = urlparse(config.open_notebook.base_url)
            if not all([result.scheme, result.netloc]):
                errors.append(f"無效的 Open Notebook base_url: {config.open_notebook.base_url}")
        except Exception as e:
            errors.append(f"URL 解析錯誤: {e}")
        
        # 驗證數值範圍
        if config.min_word_count < 0:
            errors.append(f"min_word_count 不能為負數: {config.min_word_count}")
        
        if config.max_concurrent < 1:
            errors.append(f"max_concurrent 至少為 1: {config.max_concurrent}")
        
        if config.retry_attempts < 0:
            errors.append(f"retry_attempts 不能為負數: {config.retry_attempts}")
        
        if config.retry_delay < 0:
            errors.append(f"retry_delay 不能為負數: {config.retry_delay}")
        
        return errors
    
    def validate_topics_config(self, topics: dict[str, TopicConfig]) -> list[str]:
        """
        驗證主題配置
        
        Args:
            topics: 主題配置字典
            
        Returns:
            錯誤訊息列表，空列表表示驗證通過
        """
        errors = []
        
        for topic_id, topic in topics.items():
            if not topic.name:
                errors.append(f"主題 {topic_id}: name 不能為空")
            
            if not topic.notebook:
                errors.append(f"主題 {topic_id}: notebook 不能為空")
            
            if not topic.prompt_template:
                errors.append(f"主題 {topic_id}: prompt_template 不能為空")
        
        return errors


# ============================================================================
# 主題解析器
# ============================================================================


class TopicResolver:
    """
    主題解析器
    
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
        # 優先使用 suggested_topic
        if suggested_topic and suggested_topic in topics_config:
            return suggested_topic
        
        # 其次使用 channel 的預設主題
        if channel in channels_config:
            default_topic = channels_config[channel].default_topic
            if default_topic in topics_config:
                return default_topic
        
        # 最後使用第一個可用的主題
        if topics_config:
            return next(iter(topics_config.keys()))
        
        raise TopicNotFoundError("沒有可用的主題配置")
    
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
        if topic_id not in topics_config:
            raise TopicNotFoundError(f"主題不存在: {topic_id}")
        
        return topics_config[topic_id].notebook
    
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
        if topic_id not in topics_config:
            raise TopicNotFoundError(f"主題不存在: {topic_id}")
        
        return topics_config[topic_id].prompt_template


# ============================================================================
# Prompt 載入器
# ============================================================================


class PromptLoader:
    """
    Prompt 載入器
    
    從 prompts/analysis/ 目錄載入 LLM 分析用的 prompt 檔案。
    """
    
    DEFAULT_PROMPTS_DIR = Path("prompts/analysis")
    
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
        if prompts_dir is None:
            prompts_dir = self.DEFAULT_PROMPTS_DIR
        
        # 嘗試 .md 副檔名
        prompt_file = prompts_dir / f"{template_name}.md"
        
        if not prompt_file.exists():
            raise PromptNotFoundError(f"Prompt 檔案不存在: {prompt_file}")
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        except IOError as e:
            raise PromptNotFoundError(f"無法讀取 prompt 檔案: {e}") from e


# ============================================================================
# 便捷函數
# ============================================================================


def load_config(
    config_path: Path | None = None,
    topics_path: Path | None = None
) -> tuple[PipelineConfig, dict[str, TopicConfig], dict[str, ChannelConfig]]:
    """
    一次性載入所有配置
    
    Args:
        config_path: Pipeline 配置文件路徑
        topics_path: 主題配置文件路徑
        
    Returns:
        (pipeline_config, topics_config, channels_config)
    """
    loader = ConfigLoader()
    
    pipeline_config = loader.load_pipeline_config(config_path)
    topics_config = loader.load_topics_config(topics_path)
    channels_config = loader.load_channels_config(topics_path)
    
    return pipeline_config, topics_config, channels_config
