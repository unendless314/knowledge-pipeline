"""
Knowledge Pipeline - Gemini CLI Provider

使用 Google Gemini CLI 進行語意分析。
"""

from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    Gemini CLI Provider 實作
    
    使用 Google Gemini CLI (`gemini` 指令) 進行語意分析。
    
    重要注意事項：
    - Gemini CLI 有沙盒限制，只能存取執行目錄下的檔案
    - 必須使用 `-p` 參數啟動 headless 模式
    - 建議使用 `--approval-mode plan` 確保唯讀
    """
    
    provider_type: ProviderType = field(default=ProviderType.GEMINI_CLI)
    project_dir: Path = field(default_factory=lambda: Path.cwd())
    temp_dir: Path | None = None
    timeout: int = 300
    max_retries: int = 3
    initial_retry_delay: int = 3
    prompt_loader: PromptLoader = field(default_factory=PromptLoader)
    output_parser: OutputParser = field(default_factory=OutputParser)
    
    def __post_init__(self):
        """初始化後處理"""
        if self.temp_dir is None:
            self.temp_dir = self.project_dir / "temp"
        
        self.temp_dir = Path(self.temp_dir)
        self.project_dir = Path(self.project_dir)
        
        # 確保 temp 目錄存在
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze(
        self,
        input_data: TranscriptInput,
        prompt_template: str,
        output_path: Path | None = None
    ) -> AnalysisResult:
        """
        執行語意分析
        
        使用兩個 temp 檔案傳遞給 Gemini：
        1. prompt_task_xxx.md - 包含完整 prompt 任務說明
        2. transcript_xxx.md - 包含轉錄稿內容
        
        Shell 只傳遞簡短的 meta prompt，避免特殊字元轉義問題。
        
        Args:
            input_data: 標準化的轉錄輸入
            prompt_template: prompt 模板名稱（如 "crypto_tech", "ufo_research"）
            output_path: 輸出記錄檔路徑（供除錯/審查，可選）
        
        Returns:
            標準化的 AnalysisResult
        
        Raises:
            LLMCallError: 呼叫失敗（非零返回碼或 API 錯誤）
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        # 使用 context manager 確保 temp 檔案被清理
        with self._temp_transcript_file(input_data) as transcript_path:
            # 載入並格式化 prompt
            prompt_content = self.prompt_loader.format(
                template_name=prompt_template,
                input_data=input_data,
                file_path=transcript_path.name  # 關鍵：只給檔名！
            )
            
            # 將 prompt 寫入 temp 檔案
            prompt_path = self._write_prompt_file(prompt_content, input_data)
            
            try:
                # 使用簡短的 meta prompt，讓 Gemini 讀取 prompt 檔案
                meta_prompt = (
                    f"請讀取 {prompt_path.name} 並按照其中指示分析 "
                    f"{transcript_path.name}，然後輸出 JSON 結果"
                )
                
                # 執行 Gemini（含重試邏輯）
                raw_output = self._call_gemini_with_retry(meta_prompt)
                
                # 記錄對話（可選）
                if output_path:
                    self._save_conversation(prompt_content, raw_output, output_path)
                
                # 解析結果
                response = self.output_parser.extract_response(raw_output)
                analysis_result = self.output_parser.parse_analysis_result(response)
                
                # 設定 provider 資訊
                analysis_result.provider = self.provider_type.value
                analysis_result.model = "gemini-2.0-flash"  # 預設模型
                
                return analysis_result
            
            finally:
                # 清理 prompt temp 檔案
                self._cleanup_temp_file(prompt_path)
    
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
            "version": "2.0-flash",
            "capabilities": [
                "text_analysis",
                "semantic_understanding",
                "json_output"
            ]
        }
    
    @contextmanager
    def _temp_transcript_file(self, input_data: TranscriptInput):
        """
        建立臨時轉錄檔案
        
        使用 context manager 確保 temp 檔案一定被清理。
        
        Args:
            input_data: 轉錄輸入
            
        Yields:
            臨時檔案路徑
        """
        # 產生唯一檔名
        content_hash = hash(input_data.content[:100]) % 10000
        temp_name = f"{input_data.channel}_{content_hash}.md"
        temp_path = self.temp_dir / temp_name
        
        # 寫入內容（含基本 frontmatter 供 Gemini 參考）
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
        將 prompt 內容寫入 temp 檔案
        
        Args:
            prompt_content: 格式化後的 prompt 內容
            input_data: 轉錄輸入（用於產生唯一檔名）
            
        Returns:
            Prompt 檔案路徑
        """
        # 產生唯一檔名（使用 hash 避免衝突）
        content_hash = hash(prompt_content) % 10000
        temp_name = f"prompt_task_{input_data.channel}_{content_hash}.md"
        temp_path = self.temp_dir / temp_name
        
        # 寫入 prompt 內容
        temp_path.write_text(prompt_content, encoding="utf-8")
        
        return temp_path
    
    def _cleanup_temp_file(self, temp_path: Path) -> None:
        """
        清理臨時檔案
        
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
        執行 Gemini CLI（含指數退避重試）
        
        重要：必須使用 -p/--prompt 參數啟動 headless 模式
        否則會進入互動模式，導致無法擷取輸出
        
        Args:
            meta_prompt: 簡短的 meta prompt（引用 temp 檔案名稱）
            
        Returns:
            Gemini CLI 輸出
            
        Raises:
            LLMCallError: 呼叫失敗
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # 注意：不使用 -o json 參數，直接使用純文字輸出
                # 原因：簡化解析流程，避免多層 JSON 包裝
                # 若未來需要 token 使用量等統計資料，可改為：
                #   ["gemini", "-p", meta_prompt, "-o", "json"]
                # 並確保 OutputParser.extract_response() 支援 JSON 格式解析
                result = subprocess.run(
                    [
                        "gemini",
                        "-p", meta_prompt,               # headless 模式（必要）
                        # 注意：移除 --approval-mode，讓 Gemini CLI 使用預設行為
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(self.project_dir)  # 關鍵：在 project_dir 執行！
                )
                
                if result.returncode == 0:
                    return result.stdout
                
                # 檢查是否為配額耗盡
                if "exhausted your capacity" in result.stderr.lower():
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
                # 重試
                time.sleep(self.initial_retry_delay * attempt)
    
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

{prompt}

## Response

{response}

---
Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}
"""
        output_path.write_text(content, encoding="utf-8")
