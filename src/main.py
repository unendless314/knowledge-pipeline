#!/usr/bin/env python3
"""
Knowledge Pipeline - CLI 入口

命令行界面，整合 Discovery、Analyzer、Uploader 流程。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from src.analyzer import AnalyzerService
from src.config import ConfigLoader, ConfigValidator
from src.discovery import DiscoveryService
from src.llm import LLMClient
from src.models import PipelineConfig
from src.state import StateManager
from src.uploader import OpenNotebookClient, UploaderService


# ============================================================================
# 設定日誌
# ============================================================================

def setup_logging(level: str = "INFO", format_type: str = "console") -> logging.Logger:
    """
    設定日誌
    
    Args:
        level: 日誌等級 (DEBUG, INFO, WARNING, ERROR)
        format_type: 格式類型 (console, json)
        
    Returns:
        Logger 實例
    """
    logger = logging.getLogger("knowledge_pipeline")
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除現有處理器
    logger.handlers.clear()
    
    # 建立處理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # 設定格式
    if format_type == "json":
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# ============================================================================
# Pipeline 類別
# ============================================================================

class KnowledgePipeline:
    """
    Knowledge Pipeline 主流程
    
    整合 Discovery、Analyzer、Uploader 的完整流程。
    """
    
    def __init__(self, config: PipelineConfig, logger: logging.Logger):
        """
        初始化 Pipeline
        
        Args:
            config: Pipeline 配置
            logger: 日誌實例
        """
        self.config = config
        self.logger = logger
        
        # 初始化各個服務
        self.discovery = DiscoveryService()
        self.state_manager = StateManager()
        
        # LLM Client
        llm_config_dict = {
            "provider": config.llm.provider,
            "project_dir": str(config.llm.project_dir),
            "timeout": config.llm.timeout,
            "max_retries": config.llm.max_retries,
        }
        self.llm_client = LLMClient.from_config(llm_config_dict)
        
        # Analyzer
        self.analyzer = AnalyzerService(
            llm_client=self.llm_client,
            enable_segmentation=True,
            default_template="default"
        )
        
        # Uploader
        self.on_client = OpenNotebookClient(config.open_notebook)
        self.uploader = UploaderService(self.on_client)
    
    def run_discovery(
        self,
        min_word_count: int = 100,
        channel_whitelist: list[str] | None = None
    ) -> int:
        """
        執行發現階段
        
        Args:
            min_word_count: 最小字數限制
            channel_whitelist: 頻道白名單
            
        Returns:
            發現的檔案數量
        """
        self.logger.info("=" * 60)
        self.logger.info("Discovery Phase - 掃描轉錄檔案")
        self.logger.info("=" * 60)
        
        # 清理過期 temp 檔案
        cleaned = self.discovery.cleanup_temp_files()
        if cleaned > 0:
            self.logger.info(f"清理 {cleaned} 個過期臨時檔案")
        
        # 執行發現
        transcriber_output = Path(self.config.transcriber_output)
        transcripts = self.discovery.discover(
            root_dir=transcriber_output,
            min_word_count=min_word_count,
            channel_whitelist=channel_whitelist
        )
        
        # 輸出統計
        stats = self.discovery.get_statistics()
        self.logger.info(f"掃描檔案: {stats.total_scanned}")
        self.logger.info(f"解析成功: {stats.parsed_success}")
        self.logger.info(f"解析失敗: {stats.parsed_failed}")
        self.logger.info(f"已處理跳過: {stats.filtered_by_status}")
        self.logger.info(f"字數不足跳過: {stats.filtered_by_word_count}")
        self.logger.info(f"頻道限制跳過: {stats.filtered_by_channel}")
        self.logger.info(f"待處理: {stats.ready_to_process}")
        
        return len(transcripts)
    
    def run_analysis(
        self,
        prompt_template: str = "default",
        batch_size: int = 10
    ) -> int:
        """
        執行分析階段
        
        Args:
            prompt_template: Prompt 模板名稱
            batch_size: 批次大小
            
        Returns:
            分析的檔案數量
        """
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Analysis Phase - 語意分析")
        self.logger.info("=" * 60)
        
        # 再次執行發現（取得待處理檔案）
        transcriber_output = Path(self.config.transcriber_output)
        transcripts = self.discovery.discover(
            root_dir=transcriber_output,
            min_word_count=100
        )
        
        if not transcripts:
            self.logger.info("沒有待處理的檔案")
            return 0
        
        self.logger.info(f"開始分析 {len(transcripts)} 個檔案")
        
        # 批次分析
        analyzed_count = 0
        
        def on_progress(current: int, total: int, status: str):
            self.logger.info(f"[{current}/{total}] {status}")
        
        try:
            results = self.analyzer.analyze_batch(
                transcripts=transcripts,
                prompt_template=prompt_template,
                output_dir=Path(self.config.intermediate) / "pending",
                progress_callback=on_progress,
                delay_between_calls=1.0
            )
            analyzed_count = len(results)
        except Exception as e:
            self.logger.error(f"分析過程發生錯誤: {e}")
        
        self.logger.info(f"分析完成: {analyzed_count}/{len(transcripts)}")
        return analyzed_count
    
    def run_upload(self, dry_run: bool = False) -> int:
        """
        執行上傳階段
        
        Args:
            dry_run: 僅模擬不上傳
            
        Returns:
            上傳的檔案數量
        """
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Upload Phase - 上傳至 Open Notebook")
        self.logger.info("=" * 60)
        
        if dry_run:
            self.logger.info("[DRY RUN] 模擬模式，不會實際上傳")
        
        # 健康檢查
        if not dry_run:
            if not self.on_client.health_check():
                self.logger.error("Open Notebook 服務不可用")
                return 0
            self.logger.info("Open Notebook 服務正常")
        
        # 讀取 pending 目錄中的檔案
        pending_dir = Path(self.config.intermediate) / "pending"
        if not pending_dir.exists():
            self.logger.info("沒有待上傳的檔案")
            return 0
        
        # 尋找所有待上傳的檔案
        from src.state import StatePersistence
        
        persistence = StatePersistence()
        pending_files = list(pending_dir.rglob("*_analyzed.md"))
        
        if not pending_files:
            self.logger.info("沒有待上傳的檔案")
            return 0
        
        self.logger.info(f"找到 {len(pending_files)} 個待上傳檔案")
        
        uploaded_count = 0
        
        for file_path in pending_files:
            try:
                # 載入分析結果
                analyzed = persistence.load_analyzed_transcript(file_path)
                
                # 決定 Notebook 名稱
                notebook_name = self._resolve_notebook(analyzed)
                
                if dry_run:
                    self.logger.info(f"[DRY RUN] 將上傳到 {notebook_name}: {analyzed.original.title}")
                    uploaded_count += 1
                    continue
                
                # 執行上傳
                source_id = self.uploader.upload(analyzed, notebook_name)
                
                # 更新檔案狀態
                intermediate_dir = Path(self.config.intermediate)
                self.state_manager.mark_as_uploaded(
                    filepath=file_path,
                    source_id=source_id,
                    intermediate_dir=intermediate_dir
                )
                
                self.logger.info(f"上傳成功: {source_id} -> {notebook_name}")
                uploaded_count += 1
                
            except Exception as e:
                self.logger.error(f"上傳失敗 {file_path}: {e}")
                # 標記為失敗
                try:
                    self.state_manager.mark_as_failed(
                        filepath=file_path,
                        error=str(e),
                        error_code="UPLOAD_ERROR"
                    )
                except Exception:
                    pass
        
        # 輸出統計
        stats = self.uploader.get_statistics()
        self.logger.info(f"上傳完成: {stats.successful}/{stats.total_uploaded}")
        
        return uploaded_count
    
    def run_full_pipeline(
        self,
        prompt_template: str = "default",
        dry_run: bool = False
    ) -> dict:
        """
        執行完整 Pipeline
        
        Args:
            prompt_template: Prompt 模板名稱
            dry_run: 僅模擬不上傳
            
        Returns:
            執行結果統計
        """
        results = {
            "discovered": 0,
            "analyzed": 0,
            "uploaded": 0
        }
        
        # Discovery
        results["discovered"] = self.run_discovery()
        
        if results["discovered"] == 0:
            self.logger.info("沒有待處理的檔案，結束流程")
            return results
        
        # Analysis
        results["analyzed"] = self.run_analysis(prompt_template)
        
        if results["analyzed"] == 0:
            self.logger.info("沒有分析成功的檔案，跳過上傳")
            return results
        
        # Upload
        results["uploaded"] = self.run_upload(dry_run)
        
        return results
    
    def _resolve_notebook(self, analyzed) -> str:
        """
        解析 Notebook 名稱
        
        邏輯：
        1. LLM 回答有效的 topic ID → 查表對應 Notebook
        2. LLM 回答 "unknown" → Unclassified Notebook
        3. LLM 無回答/無效值 → 頻道 fallback
        
        Args:
            analyzed: 分析結果
            
        Returns:
            Notebook 名稱
        """
        from src.config import TopicResolver, load_config
        
        # 載入配置
        _, topics_config, channels_config = load_config()
        resolver = TopicResolver()
        
        suggested = analyzed.analysis.suggested_topic
        channel = analyzed.original.channel
        
        # 情況 1：LLM 回答有效的 topic ID
        if suggested and suggested in topics_config and suggested != "unknown":
            return resolver.get_notebook_for_topic(suggested, topics_config)
        
        # 情況 2：LLM 回答 "unknown"
        if suggested == "unknown":
            return resolver.get_notebook_for_topic("unknown", topics_config)
        
        # 情況 3：LLM 無回答或無效值 → 頻道 fallback
        topic_id = resolver.resolve_topic(
            channel=channel,
            suggested_topic=None,  # 強制使用頻道預設
            topics_config=topics_config,
            channels_config=channels_config
        )
        return resolver.get_notebook_for_topic(topic_id, topics_config)


# ============================================================================
# CLI 命令處理
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """
    建立 CLI 參數解析器
    
    Returns:
        ArgumentParser 實例
    """
    parser = argparse.ArgumentParser(
        prog="knowledge-pipeline",
        description="Knowledge Pipeline - 自動化知識庫處理流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 執行完整流程
  %(prog)s run

  # 僅執行發現階段
  %(prog)s discover

  # 僅執行分析階段
  %(prog)s analyze --template crypto_tech

  # 測試模式（不上傳）
  %(prog)s run --dry-run
        """
    )
    
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/config.yaml",
        help="配置文件路徑 (預設: config/config.yaml)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="詳細輸出模式"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # run 命令
    run_parser = subparsers.add_parser(
        "run",
        help="執行完整 Pipeline"
    )
    run_parser.add_argument(
        "--template",
        "-t",
        type=str,
        default="default",
        help="Prompt 模板名稱 (預設: default)"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="測試模式，不上傳"
    )
    
    # discover 命令
    discover_parser = subparsers.add_parser(
        "discover",
        help="執行發現階段"
    )
    discover_parser.add_argument(
        "--min-words",
        type=int,
        default=100,
        help="最小字數限制 (預設: 100)"
    )
    
    # analyze 命令
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="執行分析階段"
    )
    analyze_parser.add_argument(
        "--template",
        "-t",
        type=str,
        default="default",
        help="Prompt 模板名稱 (預設: default)"
    )
    
    # upload 命令
    upload_parser = subparsers.add_parser(
        "upload",
        help="執行上傳階段"
    )
    upload_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="測試模式，不上傳"
    )
    
    return parser


def main(args: Sequence[str] | None = None) -> int:
    """
    主入口函數
    
    Args:
        args: 命令行參數
        
    Returns:
        退出碼 (0 表示成功)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command:
        parser.print_help()
        return 1
    
    # 設定日誌
    log_level = "DEBUG" if parsed_args.verbose else "INFO"
    logger = setup_logging(log_level)
    
    try:
        # 載入配置
        config_path = Path(parsed_args.config)
        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return 1
        
        logger.info(f"載入配置: {config_path}")
        
        config_loader = ConfigLoader()
        config = config_loader.load_pipeline_config(config_path)
        
        # 驗證配置
        validator = ConfigValidator()
        errors = validator.validate_pipeline_config(config)
        if errors:
            for error in errors:
                logger.error(f"配置錯誤: {error}")
            return 1
        
        # 初始化 Pipeline
        pipeline = KnowledgePipeline(config, logger)
        
        # 執行命令
        if parsed_args.command == "run":
            results = pipeline.run_full_pipeline(
                prompt_template=parsed_args.template,
                dry_run=parsed_args.dry_run
            )
            logger.info("")
            logger.info("=" * 60)
            logger.info("Pipeline 完成")
            logger.info(f"  發現: {results['discovered']}")
            logger.info(f"  分析: {results['analyzed']}")
            logger.info(f"  上傳: {results['uploaded']}")
            logger.info("=" * 60)
        
        elif parsed_args.command == "discover":
            count = pipeline.run_discovery(min_word_count=parsed_args.min_words)
            logger.info(f"發現 {count} 個待處理檔案")
        
        elif parsed_args.command == "analyze":
            count = pipeline.run_analysis(prompt_template=parsed_args.template)
            logger.info(f"分析 {count} 個檔案")
        
        elif parsed_args.command == "upload":
            count = pipeline.run_upload(dry_run=parsed_args.dry_run)
            logger.info(f"上傳 {count} 個檔案")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("使用者中斷")
        return 130
    except Exception as e:
        logger.error(f"執行錯誤: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
