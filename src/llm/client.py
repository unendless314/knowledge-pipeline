"""
Knowledge Pipeline - LLM Client

通用 LLM 客戶端，使用工廠模式根據配置動態選擇 Provider。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.llm.exceptions import LLMError
from src.llm.models import AnalysisResult, ProviderType, TranscriptInput

if TYPE_CHECKING:
    from src.llm.provider import LLMProvider


class LLMClient:
    """
    通用 LLM 客戶端（工廠模式）
    
    使用範例:
        from src.llm import LLMClient
        
        client = LLMClient.from_config({
            "provider": "gemini_cli",
            "project_dir": "/path/to/project",
            "timeout": 300,
            "max_retries": 3
        })
        
        result = client.analyze(
            input_data=transcript_input,
            prompt_template="crypto_tech"
        )
    """
    
    def __init__(self, provider: "LLMProvider"):
        """
        初始化 LLM Client
        
        Args:
            provider: LLM Provider 實例
        """
        self._provider = provider
    
    @classmethod
    def from_config(cls, config: dict) -> "LLMClient":
        """
        根據配置建立對應的 Provider
        
        Args:
            config: {
                "provider": "gemini_cli",
                "project_dir": "/path/to/project",
                "timeout": 300,
                "max_retries": 3,
                ...
            }
        
        Returns:
            LLMClient 實例
        
        Raises:
            ValueError: 未知的 provider 類型
            LLMError: 建立 Provider 失敗
        """
        provider_type = ProviderType(config.get("provider", "gemini_cli"))
        
        if provider_type == ProviderType.GEMINI_CLI:
            from src.llm.gemini_cli import GeminiCLIProvider
            
            provider = GeminiCLIProvider(
                project_dir=Path(config["project_dir"]),
                timeout=config.get("timeout", 300),
                max_retries=config.get("max_retries", 3),
                initial_retry_delay=config.get("initial_retry_delay", 3)
            )
        
        elif provider_type == ProviderType.OPENAI_API:
            raise NotImplementedError("OpenAI API provider 尚未實作")
        
        elif provider_type == ProviderType.GEMINI_API:
            raise NotImplementedError("Gemini API provider 尚未實作")
        
        elif provider_type == ProviderType.LOCAL_LLM:
            raise NotImplementedError("Local LLM provider 尚未實作")
        
        else:
            raise ValueError(f"未知的 provider 類型: {provider_type}")
        
        return cls(provider)
    
    def analyze(
        self,
        input_data: TranscriptInput,
        prompt_template: str = "default",
        output_path: Path | None = None
    ) -> AnalysisResult:
        """
        執行分析（委派給底層 Provider）
        
        Args:
            input_data: 轉錄輸入
            prompt_template: prompt 模板名稱
            output_path: 輸出記錄檔路徑（可選）
        
        Returns:
            AnalysisResult
        
        Raises:
            LLMError: 分析失敗
        """
        return self._provider.analyze(input_data, prompt_template, output_path)
    
    def health_check(self) -> bool:
        """
        檢查底層 Provider 是否可用
        
        Returns:
            True 表示可用，False 表示不可用
        """
        return self._provider.health_check()
    
    def get_provider_name(self) -> str:
        """
        取得目前使用的 Provider 名稱
        
        Returns:
            Provider 名稱
        """
        return self._provider.provider_type.value
    
    def get_model_info(self) -> dict:
        """
        取得模型資訊
        
        Returns:
            {"name": str, "version": str, "capabilities": list[str]}
        """
        return self._provider.get_model_info()
