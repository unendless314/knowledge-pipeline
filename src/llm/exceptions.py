"""
Knowledge Pipeline - LLM 模組例外定義
"""


class LLMError(Exception):
    """LLM 模組錯誤基類"""
    pass


class LLMCallError(LLMError):
    """LLM 呼叫失敗（非零返回碼或 API 錯誤）"""
    
    def __init__(self, message: str, exit_code: int | None = None, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class LLMTimeoutError(LLMError):
    """LLM 呼叫超時"""
    
    def __init__(self, message: str, timeout_seconds: int = 0):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


class LLMRateLimitError(LLMError):
    """LLM 配額耗盡或速率限制"""
    
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # 建議等待秒數


class LLMParseError(LLMError):
    """LLM 輸出解析失敗"""
    pass


class PromptTemplateNotFoundError(LLMError):
    """Prompt 模板不存在"""
    pass
