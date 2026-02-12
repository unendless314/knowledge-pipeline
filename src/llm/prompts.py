"""
Knowledge Pipeline - LLM Prompt 模組

負責載入和格式化 prompt templates。
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Formatter

from src.llm.exceptions import PromptTemplateNotFoundError
from src.llm.models import TranscriptInput


class PromptLoader:
    """
    Prompt 載入器
    
    從 prompts/{task_type}/{template}.md 載入並格式化 prompt。
    """
    
    def __init__(self, prompts_dir: Path | None = None):
        """
        初始化載入器
        
        Args:
            prompts_dir: Prompts 目錄路徑，預設為專案根目錄下的 prompts/
        """
        if prompts_dir is None:
            # 預設為專案根目錄下的 prompts/
            self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)
    
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
        template_path = self.prompts_dir / task_type / f"{template_name}.md"
        
        if not template_path.exists():
            # 嘗試載入預設 template
            if template_name != "default":
                return self.load("default", task_type)
            raise PromptTemplateNotFoundError(
                f"Prompt template 不存在: {template_path}"
            )
        
        return template_path.read_text(encoding="utf-8")
    
    def format(
        self,
        template_name: str,
        input_data: TranscriptInput,
        task_type: str = "analysis",
        **extra_vars
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
            **extra_vars: 額外的變數
        
        Returns:
            完整的 prompt 字串
        """
        template = self.load(template_name, task_type)
        
        # 準備變數
        vars_dict = {
            "channel": input_data.channel,
            "title": input_data.title,
            "word_count": input_data.word_count,
            "content_preview": input_data.content_preview,
            **extra_vars
        }
        
        # 安全格式化：只替換存在的變數
        return self._safe_format(template, vars_dict)
    
    def _safe_format(self, template: str, vars_dict: dict) -> str:
        """
        安全格式化 template
        
        只替換 template 中存在的變數，保留其他內容。
        
        Args:
            template: Template 字串
            vars_dict: 變數字典
            
        Returns:
            格式化後的字串
        """
        result = template
        
        # 找到所有需要替換的變數
        for var_name in self._get_template_vars(template):
            if var_name in vars_dict:
                # 使用正規表達式替換 {var_name} 但不替換 {{var_name}}
                pattern = r"(?<!\{)\{" + re.escape(var_name) + r"\}(?!\})"
                result = re.sub(pattern, str(vars_dict[var_name]), result)
        
        return result
    
    def _get_template_vars(self, template: str) -> set[str]:
        """
        取得 template 中的所有變數名稱
        
        Args:
            template: Template 字串
            
        Returns:
            變數名稱集合
        """
        vars_set = set()
        
        for _, field_name, _, _ in Formatter().parse(template):
            if field_name is not None:
                vars_set.add(field_name)
        
        return vars_set


class OutputParser:
    """
    LLM 輸出解析器
    
    從原始 LLM 輸出提取結構化資料。
    """
    
    def extract_response(self, output: str) -> str:
        """
        從完整輸出提取 Response 區塊
        
        支援格式：
        1. JSON 格式（gemini -o json）：
           {"response": "實際內容", "stats": {...}}
        
        2. 文字格式：
           ## Response
           {實際回應內容}
        
        Args:
            output: 完整輸出
            
        Returns:
            Response 區塊內容
        """
        import json
        
        # 策略 1: 嘗試解析為 JSON（gemini -o json 格式）
        try:
            data = json.loads(output.strip())
            if "response" in data:
                return data["response"].strip()
        except json.JSONDecodeError:
            pass
        
        # 策略 2: 尋找 ## Response 標記（文字格式）
        lines = output.split("\n")
        in_response = False
        response_lines = []
        
        for line in lines:
            if line.strip() == "## Response":
                in_response = True
                continue
            
            if in_response:
                # 檢查是否遇到下一個區塊
                if line.strip().startswith("## ") and line.strip() != "## Response":
                    break
                response_lines.append(line)
        
        if response_lines:
            return "\n".join(response_lines).strip()
        
        # 如果沒有找到 Response 區塊，返回整個輸出
        return output.strip()
    
    def parse_analysis_result(self, response: str) -> "AnalysisResult":
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
        from src.llm.exceptions import LLMParseError
        from src.llm.models import AnalysisResult, Segment
        
        # 嘗試提取 JSON 區塊
        try:
            data = self._extract_json_block(response)
        except LLMParseError:
            # 嘗試直接解析整個回應
            try:
                import json
                data = json.loads(response.strip())
            except json.JSONDecodeError:
                raise LLMParseError(f"無法解析 LLM 輸出: {response[:200]}...")
        
        # 構建 AnalysisResult
        segments = None
        if "segments" in data and data["segments"]:
            segments = [
                Segment(
                    section_type=s.get("section_type", "section"),
                    title=s.get("title", ""),
                    start_quote=s.get("start_quote", "")
                )
                for s in data["segments"]
            ]
        
        return AnalysisResult(
            semantic_summary=data.get("semantic_summary", ""),
            key_topics=data.get("key_topics", []),
            suggested_topic=data.get("suggested_topic", ""),
            content_type=data.get("content_type", ""),
            content_density=data.get("content_density", ""),
            temporal_relevance=data.get("temporal_relevance", ""),
            dialogue_format=data.get("dialogue_format"),
            segments=segments,
            key_entities=data.get("key_entities"),
            provider="",
            model=""
        )
    
    def _extract_json_block(self, text: str) -> dict:
        """
        從文字中提取 JSON 區塊
        
        處理場景：
        1. 純 JSON 輸出
        2. JSON 前後有雜訊文字
        3. 思考過程 + JSON 回覆
        4. 多個 JSON 區塊（取最後一個）
        
        Args:
            text: 原始文字
        
        Returns:
            解析後的 dict
        
        Raises:
            LLMParseError: 找不到有效的 JSON
        """
        import json
        
        from src.llm.exceptions import LLMParseError
        
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
        end_idx = None
        
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
