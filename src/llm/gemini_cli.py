"""
Knowledge Pipeline - Gemini CLI Provider

使用 Google Gemini CLI 進行語意分析（stdin 優化版）。
透過 stdin 一次性傳遞 prompt 和 transcript，將 API 呼叫次數從 3-4 次降至 1 次。
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
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
class GeminiCLIProvider:
    """
    Gemini CLI Provider 實作（stdin 優化版）
    
    使用 Google Gemini CLI (`gemini` 指令) 進行語意分析。
    
    優化重點：
    - 透過 stdin 直接傳遞內容，避免 Gemini Agent 呼叫 read_file 工具
    - 預期將每部影片的 API 呼叫次數從 3-4 次降至 1 次
    - 保留 temp/debug/ 目錄用於記錄輸入內容，確保可觀測性
    
    Attributes:
        provider_type: Provider 類型（固定為 GEMINI_CLI）
        project_dir: 專案根目錄
        temp_dir: 臨時檔案目錄（用於除錯記錄）
        model: 使用的模型名稱（如 gemini-2.5-pro）
        timeout: 呼叫超時秒數
        max_retries: 最大重試次數
        initial_retry_delay: 初始重試延遲秒數
        prompt_loader: Prompt 載入器
        output_parser: 輸出解析器
        debug_input: 是否記錄輸入內容到 temp/debug/
    """
    
    provider_type: ProviderType = field(default=ProviderType.GEMINI_CLI)
    project_dir: Path = field(default_factory=lambda: Path.cwd())
    temp_dir: Path | None = None
    model: str = "gemini-2.5-pro"
    timeout: int = 300
    max_retries: int = 3
    initial_retry_delay: int = 3
    prompt_loader: PromptLoader = field(default_factory=PromptLoader)
    output_parser: OutputParser = field(default_factory=OutputParser)
    debug_input: bool = False  # 預設關閉除錢記錄
    
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
        執行語意分析（stdin 優化版）
        
        流程：
        1. 載入並格式化 prompt
        2. 準備 transcript 內容
        3. 組合輸入（prompt + transcript）
        4. （可選）記錄除錢輸入到 temp/debug/
        5. 透過 stdin 傳給 Gemini（1 次 API 呼叫）
        6. 解析結果
        
        Args:
            input_data: 標準化的轉錄輸入
            prompt_template: prompt 模板名稱（如 "crypto_tech", "ufo_research"）
            output_path: 輸出對話記錄檔路徑（供除錯/審查，可選）
        
        Returns:
            標準化的 AnalysisResult
        
        Raises:
            LLMCallError: 呼叫失敗（非零返回碼或 API 錯誤）
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
            # Step 4: （可選）記錄除錢輸入
            if self.debug_input:
                debug_path = self._save_debug_input(
                    input_data=input_data,
                    combined_input=combined_input,
                    template_name=prompt_template
                )
                # 這裡可以選擇印出 log 或保持靜默
                # print(f"[Debug] 輸入內容已記錄至: {debug_path}")
            
            # Step 5: 執行 Gemini（透過 stdin，1 次呼叫）
            raw_output = self._call_gemini_with_streaming(combined_input)
            
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
            # 直接重新拋出，保持例外鏈
            raise
        except Exception as e:
            # 包裝未預期的錯誤
            raise LLMCallError(f"分析過程發生錯誤: {e}") from e
    
    def health_check(self) -> bool:
        """
        檢查 Provider 是否可用
        
        Returns:
            True 表示可用，False 表示不可用
        """
        try:
            result = subprocess.run(
                ["gemini", "--help"],
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
            "name": "Gemini",
            "version": self.model,
            "capabilities": [
                "text_analysis",
                "semantic_understanding",
                "json_output"
            ]
        }
    
    def _prepare_transcript_content(self, input_data: TranscriptInput) -> str:
        """
        準備 transcript 內容
        
        將 transcript 包裝為帶有 metadata 的格式，方便 Gemini 理解。
        
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
        儲存實際傳入 stdin 的內容，供除錢檢查
        
        這讓使用者可以：
        1. 檢查 prompt 是否正確組裝
        2. 確認 transcript 內容是否完整
        3. 手動複製內容測試 Gemini CLI
        
        Args:
            input_data: 轉錄輸入
            combined_input: 實際傳入 stdin 的完整內容
            template_name: 使用的模板名稱
            
        Returns:
            儲存的除錢檔案路徑
        """
        # 產生檔名：debug_{channel}_{video_id}_{timestamp}.md
        timestamp = datetime.now().strftime("%H%M%S")
        safe_channel = self._sanitize_filename(input_data.channel)
        video_id = input_data.video_id or "unknown"
        filename = f"debug_{safe_channel}_{video_id}_{timestamp}.md"
        
        debug_path = self.temp_dir / "debug" / filename
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 寫入內容，包含 metadata 方便識別
        header = f"""# Debug Input Record

## Metadata
- Template: `{template_name}`
- Channel: {input_data.channel}
- Title: {input_data.title}
- Video ID: {video_id}
- Timestamp: {datetime.now().isoformat()}
- Model: {self.model}

## Notes
此檔案記錄了實際透過 stdin 傳給 Gemini CLI 的完整內容。
若要手動測試，可使用：
  cat {filename} | gemini -p "Analyze and output JSON"

========================================
## 以下為實際傳入 Gemini stdin 的內容
========================================

"""
        debug_path.write_text(header + combined_input, encoding="utf-8")
        
        return debug_path
    
    def _call_gemini_with_streaming(self, combined_input: str) -> str:
        """
        執行 Gemini CLI（stdin streaming 版本）
        
        透過 stdin 傳遞所有內容，避免 Gemini Agent 呼叫 read_file 工具。
        預期效果：每部影片從 3-4 次呼叫降至 1 次。
        
        Args:
            combined_input: 組合後的完整輸入（prompt + transcript）
            
        Returns:
            Gemini CLI 輸出
            
        Raises:
            LLMCallError: 呼叫失敗
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        # 簡短的 meta prompt，告訴模型任務
        meta_prompt = (
            "You are provided with analysis instructions followed by a video transcript. "
            "Follow the instructions to analyze the transcript and output valid JSON only."
        )
        
        for attempt in range(1, self.max_retries + 1):
            try:
                result = subprocess.run(
                    [
                        "gemini",
                        "-m", self.model,                   # 指定模型
                        "-p", meta_prompt,                   # headless 模式
                        "--approval-mode", "yolo",           # 自動接受，避免互動
                    ],
                    input=combined_input,                    # 關鍵：透過 stdin 傳遞
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(self.project_dir)
                )
                
                if result.returncode == 0:
                    return result.stdout
                
                # 檢查是否為配額耗盡
                stderr_lower = result.stderr.lower()
                if "exhausted your capacity" in stderr_lower or "rate limit" in stderr_lower:
                    if attempt < self.max_retries:
                        delay = min(
                            self.initial_retry_delay * (2 ** (attempt - 1)),
                            60  # 最大延遲 60 秒
                        )
                        time.sleep(delay)
                        continue
                    raise LLMRateLimitError(
                        "Gemini API 配額耗盡",
                        retry_after=delay if attempt < self.max_retries else None
                    )
                
                # 其他錯誤
                raise LLMCallError(
                    f"Gemini CLI 失敗: {result.stderr}",
                    exit_code=result.returncode,
                    stderr=result.stderr
                )
                
            except subprocess.TimeoutExpired:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(
                        f"Gemini CLI 超時（{self.timeout} 秒）",
                        timeout_seconds=self.timeout
                    )
                # 指數退避重試
                time.sleep(self.initial_retry_delay * attempt)
    
    def _sanitize_filename(self, text: str) -> str:
        """
        清理文字以便用於檔案名稱
        
        Args:
            text: 原始文字
            
        Returns:
            清理後的文字（只保留 alphanumeric 和底線）
        """
        import re
        # 移除非 alphanumeric 字元，保留底線
        sanitized = re.sub(r'[^\w]', '_', text)
        # 移除連續的底線
        sanitized = re.sub(r'_+', '_', sanitized)
        # 限制長度
        return sanitized[:30].strip('_')
    
    def _save_conversation(
        self,
        prompt: str,
        response: str,
        output_path: Path
    ) -> None:
        """
        儲存對話記錄
        
        Args:
            prompt: Prompt 內容
            response: 回應內容
            output_path: 輸出路徑
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = f"""# LLM 對話記錄

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
Model: {self.model}
"""
        output_path.write_text(content, encoding="utf-8")
    
    # =========================================================================
    # 以下方法為向後相容保留，但不再用於主要流程
    # =========================================================================
    
    @contextmanager
    def _temp_transcript_file(self, input_data: TranscriptInput):
        """
        （已棄用）建立臨時轉錄檔案
        
        此方法保留供向後相容，但 stdin 優化版已不再需要。
        主要流程現在直接透過 _prepare_transcript_content() 準備內容。
        
        Args:
            input_data: 轉錄輸入
            
        Yields:
            臨時檔案路徑
        """
        # 產生唯一檔名
        content_hash = hash(input_data.content[:100]) % 10000
        temp_name = f"{input_data.channel}_{content_hash}.md"
        temp_path = self.temp_dir / temp_name
        
        # 寫入內容
        content = f"""---
channel: {input_data.channel}
title: {input_data.title}
word_count: {input_data.word_count}
---

{input_data.content}
"""
        temp_path.write_text(content, encoding="utf-8")
        
        try:
            yield temp_path
        finally:
            # 清理臨時檔案
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
    
    def _write_prompt_file(self, prompt_content: str, input_data: TranscriptInput) -> Path:
        """
        （已棄用）將 prompt 內容寫入 temp 檔案
        
        此方法保留供向後相容，但 stdin 優化版已不再需要。
        
        Args:
            prompt_content: 格式化後的 prompt 內容
            input_data: 轉錄輸入（用於產生唯一檔名）
            
        Returns:
            Prompt 檔案路徑
        """
        # 產生唯一檔名
        content_hash = hash(prompt_content) % 10000
        temp_name = f"prompt_task_{input_data.channel}_{content_hash}.md"
        temp_path = self.temp_dir / temp_name
        
        # 寫入 prompt 內容
        temp_path.write_text(prompt_content, encoding="utf-8")
        
        return temp_path
    
    def _cleanup_temp_file(self, temp_path: Path) -> None:
        """
        （已棄用）清理臨時檔案
        
        此方法保留供向後相容。
        
        Args:
            temp_path: 要清理的檔案路徑
        """
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
    
    def _call_gemini_with_retry(self, meta_prompt: str) -> str:
        """
        （已棄用）執行 Gemini CLI（檔案讀取版本）
        
        此方法為舊版實作，透過 meta_prompt 讓 Gemini 讀取檔案。
        需要 3-4 次 API 呼叫（啟動 + 讀 prompt + 讀 transcript + 分析）。
        
        新版請使用 _call_gemini_with_streaming()，透過 stdin 只需 1 次呼叫。
        
        Args:
            meta_prompt: 簡短的 meta prompt（引用 temp 檔案名稱）
            
        Returns:
            Gemini CLI 輸出
        """
        # 此為舊版實作，保留供參考或緊急 fallback
        for attempt in range(1, self.max_retries + 1):
            try:
                result = subprocess.run(
                    [
                        "gemini",
                        "-m", self.model,
                        "-p", meta_prompt,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(self.project_dir)
                )
                
                if result.returncode == 0:
                    return result.stdout
                
                if "exhausted your capacity" in result.stderr.lower():
                    if attempt < self.max_retries:
                        delay = min(
                            self.initial_retry_delay * (2 ** (attempt - 1)),
                            60
                        )
                        time.sleep(delay)
                        continue
                    raise LLMRateLimitError(
                        "Gemini API 配額耗盡",
                        retry_after=delay if attempt < self.max_retries else None
                    )
                
                raise LLMCallError(
                    f"Gemini CLI 失敗: {result.stderr}",
                    exit_code=result.returncode,
                    stderr=result.stderr
                )
                
            except subprocess.TimeoutExpired:
                if attempt == self.max_retries:
                    raise LLMTimeoutError(
                        f"Gemini CLI 超時（{self.timeout} 秒）",
                        timeout_seconds=self.timeout
                    )
                time.sleep(self.initial_retry_delay * attempt)
