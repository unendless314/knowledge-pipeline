"""
Knowledge Pipeline - LLM Provider 抽象層介面定義

此模組定義 LLM Provider 的抽象介面與資料模型，
支援多種 LLM 實作（Gemini CLI、OpenAI API、Gemini API、Local LLM 等）。

架構:
    LLMClient (通用入口)
        └── LLMProvider (Protocol)
            ├── GeminiCLIProvider (當前實作)
            ├── OpenAIProvider (預留)
            └── LocalLLMProvider (預留)

使用範例:
    from src.llm import LLMClient, TranscriptInput
    
    client = LLMClient.from_config({
        "provider": "gemini_cli",
        "project_dir": "/path/to/project",
        "timeout": 300
    })
    
    result = client.analyze(
        input_data=transcript_input,
        prompt_template="crypto_tech"
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Protocol, runtime_checkable


# ============================================================================
# Enum 定義
# ============================================================================

class ProviderType(str, Enum):
    """支援的 LLM Provider 類型"""
    GEMINI_CLI = "gemini_cli"
    OPENAI_API = "openai_api"
    GEMINI_API = "gemini_api"
    LOCAL_LLM = "local_llm"


# ============================================================================
# 輸入輸出資料模型
# ============================================================================

@dataclass
class TranscriptInput:
    """
    輸入給 LLM 的標準化轉錄資料
    
    所有 Provider 都使用此統一格式作為輸入。
    
    Attributes:
        channel: YouTube 頻道名稱
        title: 影片標題
        content: 完整轉錄內容（純文字）
        published_at: 發布日期（ISO 8601 格式字串）
        word_count: 轉錄字數
        file_path: 原始檔案路徑
        video_id: YouTube Video ID（可選）
        duration: 影片長度（可選）
    """
    channel: str
    title: str
    content: str
    published_at: str
    word_count: int
    file_path: Path
    video_id: str | None = None
    duration: str | None = None
    
    @property
    def content_preview(self, max_chars: int = 500) -> str:
        """內容預覽（用於 prompt）"""
        if len(self.content) <= max_chars:
            return self.content
        return self.content[:max_chars] + "..."


@dataclass
class Segment:
    """
    內容分段（用於結構化分段）
    
    Attributes:
        section_type: 段落類型 (intro, key_point, conclusion, etc.)
        title: 段落標題
        start_quote: 錨點文字（段落起始句，約 10-20 字）
    """
    section_type: str
    title: str
    start_quote: str


@dataclass  
class AnalysisResult:
    """
    統一的 LLM 分析結果格式
    
    所有 Provider 都必須將輸出轉換為此標準格式。
    
    Attributes:
        semantic_summary: 內容摘要（100-200 字）
        key_topics: 關鍵主題（3-5 個）
        suggested_topic: AI 建議的歸檔類別 ID（對應 topics.yaml 中的 key）
        content_type: 內容類型 (technical_analysis, opinion_discussion, news, ...)
        content_density: 資訊密度 (high, medium, low)
        temporal_relevance: 時效性 (evergreen, time_sensitive, news)
        dialogue_format: 對話形式（可選）
        segments: 敘事結構分段（可選，用於結構化分段）
        key_entities: 關鍵實體（可選，如 [[Entity Name]]）
        
        # 中繼資料
        provider: 使用的 Provider 類型
        model: 使用的模型名稱
        processed_at: 處理時間
    """
    semantic_summary: str
    key_topics: list[str]
    suggested_topic: str
    content_type: str  # technical_analysis, opinion_discussion, news, educational, interview
    content_density: str  # high, medium, low
    temporal_relevance: str  # evergreen, time_sensitive, news
    
    # 可選欄位
    dialogue_format: str | None = None
    segments: list[Segment] | None = None
    key_entities: list[str] | None = None
    
    # 中繼資料（由 Provider 自動填入）
    provider: str = ""
    model: str = ""
    processed_at: datetime | None = None
    
    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now()
    
    def to_dict(self) -> dict:
        """轉換為字典（用於序列化）"""
        return {
            "semantic_summary": self.semantic_summary,
            "key_topics": self.key_topics,
            "suggested_topic": self.suggested_topic,
            "content_type": self.content_type,
            "content_density": self.content_density,
            "temporal_relevance": self.temporal_relevance,
            "dialogue_format": self.dialogue_format,
            "segments": [
                {"section_type": s.section_type, "title": s.title, "start_quote": s.start_quote}
                for s in (self.segments or [])
            ],
            "key_entities": self.key_entities or [],
            "analyzed_by": f"{self.provider}/{self.model}" if self.model else self.provider,
            "analyzed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


# ============================================================================
# Provider Protocol 定義
# ============================================================================

@runtime_checkable
class LLMProvider(Protocol):
    """
    LLM Provider 抽象介面
    
    所有 LLM 實作都必須遵循此介面。
    
    實作範例:
        class GeminiCLIProvider:
            provider_type = ProviderType.GEMINI_CLI
            
            def analyze(self, input_data, prompt_template, output_path):
                # 實作呼叫邏輯
                pass
            
            def health_check(self):
                # 檢查 gemini CLI 是否可用
                pass
    """
    
    provider_type: ProviderType
    
    def analyze(
        self,
        input_data: TranscriptInput,
        prompt_template: str,
        output_path: Path | None = None
    ) -> AnalysisResult:
        """
        執行語意分析
        
        Args:
            input_data: 標準化的轉錄輸入
            prompt_template: prompt 模板名稱（如 "crypto_tech", "ufo_research"）
            output_path: 輸出記錄檔路徑（供除錯/審查，可選）
                
                若提供，Provider 應將完整對話記錄儲存至此路徑，
                使用 Markdown 格式：
                ```
                # LLM 對話記錄
                ## Prompt
                ...
                ## Response
                ...
                ```
        
        Returns:
            標準化的 AnalysisResult
        
        Raises:
            LLMCallError: 呼叫失敗（含錯誤碼）
            LLMTimeoutError: 呼叫超時
            LLMRateLimitError: 配額耗盡
        """
        ...
    
    def health_check(self) -> bool:
        """
        檢查 Provider 是否可用
        
        Returns:
            True 表示可用，False 表示不可用
        """
        ...
    
    def get_model_info(self) -> dict:
        """
        取得模型資訊
        
        Returns:
            {"name": str, "version": str, "capabilities": list[str]}
        """
        ...


# ============================================================================
# 通用 LLM 客戶端介面
# ============================================================================

class LLMClientInterface(Protocol):
    """
    通用 LLM 客戶端介面
    
    工廠模式實作，根據配置動態選擇 Provider。
    
    實作範例:
        class LLMClient:
            def __init__(self, provider: LLMProvider):
                self._provider = provider
            
            @classmethod
            def from_config(cls, config):
                if config["provider"] == "gemini_cli":
                    provider = GeminiCLIProvider(...)
                return cls(provider)
    """
    
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
        """
        ...
    
    def health_check(self) -> bool:
        """檢查底層 Provider 是否可用"""
        ...
    
    def get_provider_name(self) -> str:
        """取得目前使用的 Provider 名稱"""
        ...


# ============================================================================
# 配置資料模型
# ============================================================================

@dataclass
class GeminiCLIConfig:
    """Gemini CLI Provider 配置"""
    project_dir: Path
    temp_dir: Path | None = None  # 預設 project_dir/temp
    timeout: int = 300
    max_retries: int = 3
    initial_retry_delay: int = 3


@dataclass
class OpenAIConfig:
    """OpenAI API Provider 配置（預留）"""
    api_key: str
    model: str = "gpt-4"
    base_url: str | None = None  # 用於自定義端點
    timeout: int = 60
    max_retries: int = 3


@dataclass
class LLMConfig:
    """通用 LLM 配置"""
    provider: ProviderType
    gemini_cli: GeminiCLIConfig | None = None
    openai: OpenAIConfig | None = None


# ============================================================================
# 例外定義
# ============================================================================

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


# ============================================================================
# 輔助類別協議
# ============================================================================

class PromptLoader(Protocol):
    """
    Prompt 載入器介面
    
    從 prompts/{task_type}/{template}.md 載入並格式化 prompt。
    """
    
    def load(self, template_name: str, task_type: str = "analysis") -> str:
        """
        載入 prompt template
        
        Args:
            template_name: Template 名稱（如 "default", "crypto_tech"）
            task_type: 任務類型（預設 "analysis"）
        
        Returns:
            Template 原始內容
        
        Raises:
            PromptTemplateNotFoundError: Template 不存在
        """
        ...
    
    def format(
        self,
        template_name: str,
        input_data: TranscriptInput,
        task_type: str = "analysis"
    ) -> str:
        """
        載入並格式化 prompt
        
        使用 Python str.format() 替換變數：
        - {channel} -> input_data.channel
        - {title} -> input_data.title
        - {file_path} -> 沙盒內的相對路徑
        - {word_count} -> input_data.word_count
        - {content_preview} -> input_data.content_preview
        
        Args:
            template_name: Template 名稱
            input_data: 轉錄輸入
            task_type: 任務類型
        
        Returns:
            完整的 prompt 字串
        """
        ...


class OutputParser(Protocol):
    """
    LLM 輸出解析器介面
    
    從原始 LLM 輸出提取結構化資料。
    """
    
    def extract_response(self, output: str) -> str:
        """
        從完整輸出提取 Response 區塊
        
        支援格式：
        ```
        # Gemini Agent 對話記錄
        ## Prompt
        ...
        ## Response
        {實際回應內容}
        ```
        """
        ...
    
    def parse_analysis_result(self, response: str) -> AnalysisResult:
        """
        將 Response 解析為 AnalysisResult
        
        支援 JSON 或 YAML 格式。
        
        Args:
            response: Response 區塊內容
        
        Returns:
            AnalysisResult
        
        Raises:
            LLMParseError: 解析失敗
        """
        ...


# ============================================================================
# 實作指導
# ============================================================================

"""
實作指南與最佳實踐

## 1. GeminiCLIProvider 實作範本

```python
@dataclass
class GeminiCLIProvider:
    provider_type: ProviderType = ProviderType.GEMINI_CLI
    
    def analyze(self, input_data: TranscriptInput, prompt_template: str, 
                output_path: Path | None = None) -> AnalysisResult:
        # Step 1: 準備 transcript temp 檔案
        with self._temp_transcript_file(input_data) as transcript_path:
            # Step 2: 載入並格式化 prompt
            prompt_content = self.prompt_loader.format(
                template_name=prompt_template,
                input_data=input_data,
                file_path=transcript_path.name  # 關鍵：只給檔名！
            )
            
            # Step 3: 將 prompt 寫入 temp 檔案（避免 shell 轉義問題）
            prompt_path = self._write_prompt_file(prompt_content, input_data)
            
            try:
                # Step 4: 使用簡短的 meta prompt 執行 Gemini
                meta_prompt = (
                    f"請讀取 {prompt_path.name} 並按照其中指示分析 "
                    f"{transcript_path.name}，然後輸出 JSON 結果"
                )
                raw_output = self._call_gemini_with_retry(meta_prompt)
                
                # Step 5: 記錄對話（可選）
                if output_path:
                    self._save_conversation(prompt_content, raw_output, output_path)
                
                # Step 6: 解析結果
                analysis_result = self.output_parser.parse_analysis_result(raw_output)
                analysis_result.provider = self.provider_type.value
                analysis_result.model = "gemini-2.0-flash"
                
                return analysis_result
                
            finally:
                # Step 7: 清理 prompt temp 檔案
                self._cleanup_temp_file(prompt_path)
```

## 2. 兩檔案傳遞機制（Prompt + Transcript）

為避免 shell 特殊字元轉義問題，使用兩個獨立檔案傳遞給 Gemini：

```python
def _write_prompt_file(self, prompt_content: str, input_data: TranscriptInput) -> Path:
    '''
    將 prompt 內容寫入 temp 檔案
    
    Args:
        prompt_content: 格式化後的完整 prompt 內容
        input_data: 轉錄輸入（用於產生唯一檔名）
        
    Returns:
        Prompt 檔案路徑（位於 project_dir/temp/ 下）
    '''
    content_hash = hash(prompt_content) % 10000
    temp_name = f"prompt_task_{input_data.channel}_{content_hash}.md"
    temp_path = self.temp_dir / temp_name
    
    temp_path.write_text(prompt_content, encoding="utf-8")
    return temp_path

def _call_gemini_with_retry(self, meta_prompt: str) -> str:
    '''
    執行 Gemini CLI（含指數退避重試）
    
    重要改進：
    - 不再將完整 prompt 傳入 shell 參數
    - 只傳遞簡短的 meta prompt（引用 temp 檔案名稱）
    - Gemini 會先讀取 prompt_task_xxx.md，再依照指示讀取 transcript_xxx.md
    
    Args:
        meta_prompt: 簡短的 meta prompt（如「請讀取 prompt_task_xxx.md...」）
    '''
    for attempt in range(1, self.max_retries + 1):
        try:
            result = subprocess.run(
                [
                    "gemini",
                    "-p", meta_prompt,           # 簡短，無特殊字元風險
                    "-o", "json",                # JSON 輸出
                    "--approval-mode", "plan"    # 唯讀模式
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.project_dir)  # 關鍵：在 project_dir 執行！
            )
            
            if result.returncode == 0:
                return result.stdout
            
            # 檢查是否為配額耗盡
            if "exhausted your capacity" in result.stderr:
                if attempt < self.max_retries:
                    delay = min(3 * (2 ** (attempt - 1)), 30)
                    time.sleep(delay)
                    continue
            
            raise LLMCallError(
                f"Gemini failed: {result.stderr}",
                exit_code=result.returncode,
                stderr=result.stderr
            )
            
        except subprocess.TimeoutExpired:
            if attempt == self.max_retries:
                raise LLMTimeoutError(
                    f"Timeout after {self.timeout}s",
                    timeout_seconds=self.timeout
                )

def _cleanup_temp_file(self, temp_path: Path) -> None:
    '''清理臨時檔案（無論成功失敗都執行）'''
    try:
        if temp_path.exists():
            temp_path.unlink()
    except OSError:
        pass
```

### 為什麼使用兩個檔案？

| 方案 | 優點 | 缺點 |
|-----|------|------|
| **單一檔案（合併）** | Gemini 只讀一次 | 需要修改 prompt 模板；分隔線可能與內容衝突 |
| **兩個檔案（採用）** | 職責分離；prompt 模板無需修改；除錯時可單獨查看 | Gemini 讀兩次（可忽略） |

**temp/ 目錄結構：**
```
temp/
├── prompt_task_Bankless_7842.md   ← 完整 prompt 任務說明（4KB）
└── transcript_Bankless_7842.md    ← 轉錄稿內容（100KB+）
```

**Shell 指令：**
```bash
gemini -p "請讀取 prompt_task_Bankless_7842.md 並按照其中指示分析 transcript_Bankless_7842.md，然後輸出 JSON 結果" \
       -o json \
       --approval-mode plan
```

## 3. 使用 Context Manager 優雅處理

```python
from contextlib import contextmanager

@contextmanager
def temp_transcript_file(project_dir: Path, input_data: TranscriptInput):
    '''
    使用 context manager 確保 temp 檔案一定被清理
    
    使用範例:
        with temp_transcript_file(project_dir, input_data) as temp_path:
            result = provider.analyze(..., file_path=temp_path.name)
    '''
    temp_dir = project_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    temp_path = temp_dir / f"{input_data.channel}_{hash(input_data.content[:100])}.md"
    temp_path.write_text(input_data.content, encoding="utf-8")
    
    try:
        yield temp_path
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

# 使用範例
class GeminiCLIProvider:
    def analyze(self, input_data: TranscriptInput, ...):
        with temp_transcript_file(self.project_dir, input_data) as temp_path:
            prompt = self.prompt_loader.format(
                template_name=prompt_template,
                input_data=input_data,
                file_path=temp_path.name
            )
            raw_output = self._call_gemini(prompt)
            return self.output_parser.parse_analysis_result(raw_output)
```

## 4. LLMClient 工廠模式實作

```python
class LLMClient:
    '''通用 LLM 客戶端（工廠模式）'''
    
    def __init__(self, provider: LLMProvider):
        self._provider = provider
    
    @classmethod
    def from_config(cls, config: dict) -> "LLMClient":
        '''
        根據配置建立對應的 Provider
        
        Args:
            config: {
                "provider": "gemini_cli",
                "project_dir": "/path/to/project",
                "timeout": 300,
                ...
            }
        '''
        provider_type = ProviderType(config.get("provider", "gemini_cli"))
        
        if provider_type == ProviderType.GEMINI_CLI:
            provider = GeminiCLIProvider(
                project_dir=Path(config["project_dir"]),
                timeout=config.get("timeout", 300),
                max_retries=config.get("max_retries", 3)
            )
        elif provider_type == ProviderType.OPENAI_API:
            raise NotImplementedError("OpenAI API provider 尚未實作")
        else:
            raise ValueError(f"未知的 provider: {provider_type}")
        
        return cls(provider)
    
    def analyze(self, input_data: TranscriptInput, 
                prompt_template: str = "default",
                output_path: Path | None = None) -> AnalysisResult:
        '''委派給底層 Provider'''
        return self._provider.analyze(input_data, prompt_template, output_path)
```

## 5. 錯誤處理模式

```python
# 推薦的錯誤處理模式
try:
    result = llm_client.analyze(input_data, prompt_template="crypto_tech")
except LLMRateLimitError as e:
    # 配額耗盡，記錄並標記為稍後重試
    logger.warning(f"Rate limit hit, retry after {e.retry_after}s")
    mark_for_retry(file, delay=e.retry_after)
except LLMTimeoutError as e:
    # 超時，記錄並標記為失敗
    logger.error(f"LLM timeout after {e.timeout_seconds}s")
    mark_as_failed(file, error_code="LLM_TIMEOUT")
except LLMCallError as e:
    # 其他錯誤，區分是否可重試
    if e.exit_code in [5, 6]:  # 假設 5xx 錯誤可重試
        mark_for_retry(file)
    else:
        mark_as_failed(file, error_code="LLM_ERROR", details=e.stderr)
except LLMParseError as e:
    # 解析失敗，通常不重試（prompt 或輸出格式問題）
    logger.error(f"Failed to parse LLM output: {e}")
    mark_as_failed(file, error_code="PARSE_ERROR")
```

## 6. 常見陷阱

| 陷阱 | 錯誤示範 | 正確做法 |
|------|----------|----------|
| **直接傳遞長內容到 shell** | `subprocess.run(["gemini", "-p", long_prompt])` | 寫入 temp 檔案，傳遞簡短引用 |
| 直接傳遞內容 | `subprocess.run(["gemini", content[:50000]])` | 寫入 temp 檔案，傳遞路徑 |
| 忽略 cwd | `subprocess.run([...])` 預設 cwd | 明確指定 `cwd=str(project_dir)` |
| 忘記清理 | 沒有 try/finally | 使用 context manager 或 try/finally |
| 錯誤處理不完整 | 只 catch Exception | 區分 LLMRateLimitError、LLMTimeoutError |
| 檔名衝突 | 固定檔名 `temp/input.md` | 使用 hash 產生唯一檔名 |

### ⚠️ Shell 轉義風險（重要！）

**絕對不要將完整 prompt 直接傳入 shell 參數：**

```python
# ❌ 錯誤：prompt 中的反引號、引號、換行可能破壞 shell 命令
subprocess.run(
    ["gemini", "-p", prompt],  # prompt 可能包含 `code`、"quotes"、\n
# ✅ 正確：使用兩個 temp 檔案，shell 只傳簡短引用
subprocess.run(
    ["gemini", "-p", "請讀取 prompt_task_xxx.md 並按照其中指示分析 transcript_xxx.md"],
```

**原因：**
- Markdown 中的反引號 `` ` `` 在 shell 中有特殊意義
- 多行字串可能導致參數解析錯誤
- 難以預測的特殊字元組合

**解決方案：**
1. 將完整 prompt 寫入 `temp/prompt_task_{hash}.md`
2. Shell 參數只傳遞簡短的 meta prompt（引用檔案名稱）
3. Gemini 會依照 meta prompt 的指示讀取並執行任務

## 7. Gemini CLI 選項參考

> 💡 **提示**：本節整理了與本專案相關的常用選項。若要查看完整命令說明，請在終端機執行：
> ```bash
> gemini --help
> ```

根據 `gemini --help`，以下選項與本專案相關：

### 關鍵選項

| 選項 | 說明 | 建議 |
|------|------|------|
| `-p, --prompt` | **必須使用！** 啟動 non-interactive (headless) 模式 | 絕對必要，否則進入互動模式無法擷取輸出 |
| `-m, --model` | 指定模型 | `gemini-2.5-pro` |
| `-o, --output-format` | 輸出格式：`text`, `json`, `stream-json` | 建議使用 `json` |
| `-s, --sandbox` | 啟用沙盒模式 | 預設已啟用 |
| `--approval-mode` | 核准模式：`default`, `auto_edit`, `yolo`, `plan` | **使用 `plan`**（唯讀，最安全） |

### 實作建議

**最佳命令組合**（headless、JSON 輸出、plan 模式）：

```python
result = subprocess.run(
    [
        "gemini",
        "-p", prompt,                    # headless 模式（必要）
        "-o", "json",                    # JSON 輸出（便於解析）
        "-m", "gemini-2.5-pro",          # 指定模型
        "--approval-mode", "plan"        # plan 模式（唯讀，最安全）
    ],
    capture_output=True,
    text=True,
    timeout=120,                         # 給較長 timeout（冷啟動）
    cwd=str(self.project_dir)
)

# 提取 JSON 區塊（處理可能的雜訊）
json_data = extract_json_block(result.stdout)
```

### 輸出解析：提取 JSON 區塊

Gemini CLI 的輸出可能包含雜訊（如初始化日誌、思考過程），需要穩健地提取 JSON：

```python
import json
import re

def extract_json_block(text: str) -> dict:
    '''
    從 Gemini 輸出中提取 JSON 區塊
    
    處理場景：
    1. 純 JSON 輸出
    2. JSON 前後有雜訊文字
    3. 思考過程 + JSON 回覆
    4. 多個 JSON 區塊（取最後一個）
    
    Args:
        text: Gemini CLI 的原始輸出
    
    Returns:
        解析後的 dict
    
    Raises:
        LLMParseError: 找不到有效的 JSON
    '''
    # 策略 1: 尋找 ```json ... ``` 代碼塊
    json_block_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[-1])  # 取最後一個
        except json.JSONDecodeError:
            pass
    
    # 策略 2: 尋找 ``` ... ```（無語言標記）
    code_block_pattern = r'```\s*(\{.*?\})\s*```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError:
            pass
    
    # 策略 3: 尋找 { ... } 區塊（最寬鬆）
    # 從後往前找，找到第一個完整的 JSON object
    brace_count = 0
    start_idx = None
    
    for i, char in enumerate(reversed(text)):
        if char == '}':
            if brace_count == 0:
                end_idx = len(text) - i
            brace_count += 1
        elif char == '{':
            brace_count -= 1
            if brace_count == 0 and start_idx is None:
                start_idx = len(text) - i - 1
                break
    
    if start_idx is not None and end_idx is not None:
        try:
            return json.loads(text[start_idx:end_idx])
        except json.JSONDecodeError:
            pass
    
    # 策略 4: 嘗試直接解析整個輸出（純 JSON）
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        raise LLMParseError(f"無法從輸出中提取有效的 JSON: {text[:200]}...")
```

### Prompt 設計建議

為了最大化 JSON 輸出的穩定性，建議在 prompt 中明確要求：

```markdown
# prompts/analysis/default.md

你是一個內容分析師。請分析檔案 {file_path} 的內容，並以 JSON 格式回覆。

請嚴格遵守以下格式，不要加入任何其他文字或解釋：

```json
{
  "semantic_summary": "100-200字的內容摘要",
  "key_topics": ["主題1", "主題2", "主題3"],
  "content_type": "technical_analysis",
  "content_density": "high",
  "temporal_relevance": "evergreen"
}
```

重要：
1. 只回覆 JSON，不要有任何前言或結語
2. 確保 JSON 格式正確（無 trailing commas）
3. 所有字串使用雙引號
```

### 冷啟動時間考量

實測發現 Gemini CLI 有明顯的冷啟動時間：
- 首次呼叫：約 5-10 秒（載入憑證、初始化服務）
- 輸出格式：初始化日誌 + 實際回覆

**建議**：
- `timeout` 設為 120 秒（而非 60 秒）
- 批次處理時考慮此延遲

### Approval Mode 選擇

| 模式 | 說明 | 風險 | 建議 |
|------|------|------|------|
| `plan` | 唯讀模式，不允許任何修改 | 最低 | ✅ **採用** |
| `auto_edit` | 自動核准編輯動作 | 中 | 可選 |
| `yolo` | 自動核准所有動作 | 高 | 不建議 |
| `default` | 每次確認 | 會卡住 | 不適合自動化 |

**採用 `plan` 模式的原因**：
- 我們只需要 Gemini **讀取** temp/ 檔案並**回傳分析結果**
- 不需要 Gemini 執行任何檔案修改
- 即使 prompt 被注入惡意指令，`plan` 模式也會阻止執行

"""

# ============================================================================
# 驗收標準
# ============================================================================

"""
驗收測試項目：

1. TranscriptInput
   - 正確建立與屬性存取
   - content_preview 正確截斷

2. AnalysisResult
   - 正確轉換為字典
   - processed_at 自動填入
   - 支援可選欄位

3. LLMProvider Protocol
   - GeminiCLIProvider 符合協議
   - 未來 OpenAIProvider 符合協議

4. LLMClient
   - from_config 正確建立對應 Provider
   - analyze 委派給底層 Provider
   - health_check 正常運作

5. 例外處理
   - LLMCallError、LLMTimeoutError、LLMRateLimitError 正確拋出與捕獲

6. PromptLoader
   - 正確載入 prompts/analysis/{template}.md
   - 正確替換變數
   - Template 不存在時拋出 PromptTemplateNotFoundError

7. OutputParser
   - 正確提取 Response 區塊
   - 正確解析 JSON/YAML
   - 正確轉換為 AnalysisResult

執行驗收測試：
    python docs/interfaces/tests/test_llm.py
"""
