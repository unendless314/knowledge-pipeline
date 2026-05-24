"""
Knowledge Pipeline - Antigravity CLI Provider

使用 Google Antigravity CLI (agy) 進行語意分析（非互動式終端直輸優化版）。
此模組旨在作為 Gemini CLI 的現代化替代方案，完美因應 2026 年 6 月 18 日即將到來的 Gemini CLI 停用。

優化重點：
- 透過 stdin 直接傳遞內容，避免 AI 呼叫 read_file 工具
- 使用 agy --print 與 --dangerously-skip-permissions 實現純背景、非互動式的安全自動化
- 簡化指令：直接使用系統配置的預設最強模型，不再需要硬編碼指定模型型號
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.llm.exceptions import (
    LLMCallError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.llm.models import AnalysisResult, ProviderType, TranscriptInput
from src.llm.prompts import OutputParser, PromptLoader


@dataclass
class AntigravityCLIProvider:
    """
    Antigravity CLI Provider 實作
    
    使用 Google Antigravity CLI (`agy` 指令) 進行高效的語意分析與結構化提取。
    
    Attributes:
        provider_type: Provider 類型（固定為 ANTIGRAVITY_CLI）
        project_dir: 專案根目錄
        temp_dir: 臨時檔案目錄（用於除錯記錄）
        model: 當前使用的模型標識符（預設為 default）
        timeout: 呼叫超時秒數
        max_retries: 最大重試次數
        initial_retry_delay: 初始重試延遲秒數
        prompt_loader: Prompt 載入器
        output_parser: 輸出解析器
        debug_input: 是否記錄輸入內容到 temp/debug/
    """
    
    provider_type: ProviderType = field(default=ProviderType.ANTIGRAVITY_CLI)
    project_dir: Path = field(default_factory=lambda: Path.cwd())
    temp_dir: Path | None = None
    model: str = "default"
    timeout: int = 300
    max_retries: int = 3
    initial_retry_delay: int = 3
    prompt_loader: PromptLoader = field(default_factory=PromptLoader)
    output_parser: OutputParser = field(default_factory=OutputParser)
    debug_input: bool = False  # 預設關閉除錯記錄
    
    def __post_init__(self):
        """初始化後處理"""
        if self.temp_dir is None:
            self.temp_dir = self.project_dir / "temp"
        
        self.temp_dir = Path(self.temp_dir)
        self.project_dir = Path(self.project_dir)
        
        # 確保 temp 目錄存在（包含 debug 子目錄）
        (self.temp_dir / "debug").mkdir(parents=True, exist_ok=True)
    
    def analyze(
        self,
        input_data: TranscriptInput,
        prompt_template: str,
        output_path: Path | None = None
    ) -> AnalysisResult:
        """
        執行語意分析（非互動式終端直輸優化版）
        
        流程：
        1. 載入並格式化 prompt
        2. 準備 transcript 內容
        3. 組合輸入（prompt + transcript）
        4. （可選）記錄除錯輸入到 temp/debug/
        5. 透過 stdin 傳給 agy（1 次 API 呼叫，直接輸出結果到 stdout）
        6. 解析結果
        
        Args:
            input_data: 標準化的轉錄輸入
            prompt_template: prompt 模板名稱（如 "crypto_tech", "spiritual"）
            output_path: 輸出對話記錄檔路徑（可選）
        
        Returns:
            標準化的 AnalysisResult
        
        Raises:
            LLMCallError: 呼叫失敗
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        # Step 1: 載入並格式化 prompt
        prompt_content = self.prompt_loader.format(
            template_name=prompt_template,
            input_data=input_data
        )
        
        # Step 2: 準備 transcript 內容
        transcript_content = self._prepare_transcript_content(input_data)
        
        # Step 3: 組合完整輸入
        combined_input = f"{prompt_content}\n{transcript_content}"
        
        try:
            # Step 4: （可選）記錄除錯輸入
            if self.debug_input:
                debug_path = self._save_debug_input(
                    input_data=input_data,
                    combined_input=combined_input,
                    template_name=prompt_template
                )
            
            # Step 5: 執行 agy（透過 stdin，1 次呼叫）
            raw_output = self._call_agy_with_streaming(combined_input)
            
            # Step 6: 記錄對話（可選）
            if output_path:
                self._save_conversation(combined_input, raw_output, output_path)
            
            # Step 7: 解析結果
            response = self.output_parser.extract_response(raw_output)
            analysis_result = self.output_parser.parse_analysis_result(response)
            
            # Step 8: 設定 provider 資訊
            analysis_result.provider = self.provider_type.value
            analysis_result.model = self.model
            
            return analysis_result
            
        except (LLMCallError, LLMTimeoutError, LLMRateLimitError):
            # 直接重新拋出
            raise
        except Exception as e:
            # 包裝未預期的錯誤
            raise LLMCallError(f"Antigravity 分析過程發生錯誤: {e}") from e
    
    def health_check(self) -> bool:
        """
        檢查 Provider (agy 指令) 是否可用
        
        Returns:
            True 表示可用，False 表示不可用
        """
        try:
            result = subprocess.run(
                ["agy", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def get_model_info(self) -> dict:
        """
        取得模型資訊
        
        Returns:
            {"name": str, "version": str, "capabilities": list[str]}
        """
        return {
            "name": "Antigravity",
            "version": self.model,
            "capabilities": [
                "text_analysis",
                "semantic_understanding",
                "json_output"
            ]
        }
    
    def _prepare_transcript_content(self, input_data: TranscriptInput) -> str:
        """
        準備 transcript 內容並加上 Metadata 區塊
        
        Args:
            input_data: 轉錄輸入
            
        Returns:
            格式化後的 transcript 內容
        """
        return f"""---TRANSCRIPT-BEGIN---

Metadata:
- Channel: {input_data.channel}
- Title: {input_data.title}
- Word Count: {input_data.word_count}
- Video ID: {input_data.video_id or "N/A"}

Content:

{input_data.content}

---TRANSCRIPT-END---"""
    
    def _save_debug_input(
        self,
        input_data: TranscriptInput,
        combined_input: str,
        template_name: str
    ) -> Path:
        """
        儲存實際傳入 stdin 的內容以供除錯檢查
        
        Args:
            input_data: 轉錄輸入
            combined_input: 實際傳入 stdin 的完整內容
            template_name: 使用的模板名稱
            
        Returns:
            儲存的除錯檔案路徑
        """
        timestamp = datetime.now().strftime("%H%M%S")
        safe_channel = self._sanitize_filename(input_data.channel)
        video_id = input_data.video_id or "unknown"
        filename = f"debug_agy_{safe_channel}_{video_id}_{timestamp}.md"
        
        debug_path = self.temp_dir / "debug" / filename
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        
        header = f"""# Debug Antigravity Input Record

## Metadata
- Template: `{template_name}`
- Channel: {input_data.channel}
- Title: {input_data.title}
- Video ID: {video_id}
- Timestamp: {datetime.now().isoformat()}
- Model: {self.model} (Default System Model)

## Notes
此檔案記錄了實際透過 stdin 傳給 Antigravity CLI 的完整內容。
若要手動測試，可使用：
  cat {filename} | agy --dangerously-skip-permissions --print "Analyze and output JSON"

========================================
## 以下為實際傳入 agy stdin 的內容
========================================

"""
        debug_path.write_text(header + combined_input, encoding="utf-8")
        return debug_path
    
    def _call_agy_with_streaming(self, combined_input: str) -> str:
        """
        執行 Antigravity CLI，利用 stdin 和 --print 參數直輸結果
        
        Args:
            combined_input: 組合後的完整輸入（prompt + transcript）
            
        Returns:
            Antigravity CLI 的輸出內容 (AI 的回答)
            
        Raises:
            LLMCallError: 呼叫失敗
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        # 簡短的引導 prompt，指示任務與限制格式為 JSON
        meta_prompt = (
            "You are provided with analysis instructions followed by a video transcript. "
            "Follow the instructions to analyze the transcript and output valid JSON only."
        )
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # 簡化命令：直接使用預設模型，省去 -m 參數指定
                result = subprocess.run(
                    [
                        "agy",
                        "--dangerously-skip-permissions",  # 自動核准權限，避免卡死背景
                        "--print",                         # 單次印出模式
                        meta_prompt,                       # 引導 prompt
                    ],
                    input=combined_input,                  # 關鍵：透過 stdin 傳入
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(self.project_dir)
                )
                
                if result.returncode == 0:
                    return result.stdout
                
                # 檢查配額限制或頻率限制錯誤
                stderr_lower = result.stderr.lower()
                if "exhausted your capacity" in stderr_lower or "rate limit" in stderr_lower or "quota" in stderr_lower:
                    if attempt < self.max_retries:
                        delay = min(
                            self.initial_retry_delay * (2 ** (attempt - 1)),
                            60
                        )
                        time.sleep(delay)
                        continue
                    raise LLMRateLimitError(
                        "Antigravity API 配額耗盡或被限流",
                        retry_after=delay if attempt < self.max_retries else None
                    )
                
                # 其他錯誤
                raise LLMCallError(
                    f"Antigravity CLI 執行失敗: {result.stderr}",
                    exit_code=result.returncode,
                    stderr=result.stderr
                )
                
            except subprocess.TimeoutExpired:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(
                        f"Antigravity CLI 呼叫超時（{self.timeout} 秒）",
                        timeout_seconds=self.timeout
                    )
                # 指數退避重試
                time.sleep(self.initial_retry_delay * attempt)
    
    def _sanitize_filename(self, text: str) -> str:
        """清理文字以便用於檔案名稱"""
        import re
        sanitized = re.sub(r'[^\w]', '_', text)
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized[:30].strip('_')
    
    def _save_conversation(
        self,
        prompt: str,
        response: str,
        output_path: Path
    ) -> None:
        """儲存對話歷史紀錄供後續審計"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = f"""# Antigravity LLM 對話記錄

## Prompt

```markdown
{prompt[:10000]}{"..." if len(prompt) > 10000 else ""}
```

## Response

```
{response}
```

---
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Provider: {self.provider_type.value}
Model: {self.model} (System Default Model)
"""
        output_path.write_text(content, encoding="utf-8")
