#!/usr/bin/env python3
"""
Implementation Verification Script
對照介面定義檢查實作完整性
"""

import ast
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def check_class_attributes(cls, required_attrs):
    """檢查類別是否有必需的屬性（支援 dataclass）"""
    missing = []
    for attr in required_attrs:
        # For dataclasses, check __dataclass_fields__
        if hasattr(cls, '__dataclass_fields__'):
            if attr not in cls.__dataclass_fields__:
                missing.append(attr)
        elif not hasattr(cls, attr):
            missing.append(attr)
    return missing


def check_methods(cls, required_methods):
    """檢查類別是否有必需的方法"""
    missing = []
    for method in required_methods:
        if not hasattr(cls, method) or not callable(getattr(cls, method)):
            missing.append(method)
    return missing


def main():
    errors = []
    warnings = []
    
    print("=" * 70)
    print("Knowledge Pipeline - Implementation Verification")
    print("=" * 70)
    
    # ========================================================================
    # 1. Check Models
    # ========================================================================
    print("\n[1] Checking Models...")
    try:
        from src.models import (
            PipelineStatus, TranscriptMetadata, TranscriptFile, AnalyzedTranscript,
            SourceCreateRequest, SourceUpdateRequest, NotebookLinkRequest
        )
        
        # Check Enums
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.APPROVED.value == "approved"
        assert PipelineStatus.UPLOADED.value == "uploaded"
        assert PipelineStatus.FAILED.value == "failed"
        print("  ✓ PipelineStatus Enum")
        
        # Check dataclass fields
        from src.llm import AnalysisResult
        ar_fields = ['semantic_summary', 'key_topics', 'suggested_topic']
        missing = check_class_attributes(AnalysisResult, ar_fields)
        if missing:
            errors.append(f"AnalysisResult missing fields: {missing}")
        else:
            print("  ✓ AnalysisResult fields")
        
        assert hasattr(AnalysisResult, 'to_dict')
        print("  ✓ AnalysisResult.to_dict()")
        
        # TranscriptFile - check properties
        tf_fields = ['path', 'metadata', 'content', 'status', 'source_id']
        missing = check_class_attributes(TranscriptFile, tf_fields)
        if missing:
            errors.append(f"TranscriptFile missing fields: {missing}")
        else:
            print("  ✓ TranscriptFile fields")
        
        assert hasattr(TranscriptFile, 'video_id')  # property
        assert hasattr(TranscriptFile, 'channel')   # property
        print("  ✓ TranscriptFile properties (video_id, channel)")
        
        # Check API Request models
        scr_fields = ['type', 'title', 'content', 'embed']
        missing = check_class_attributes(SourceCreateRequest, scr_fields)
        if missing:
            errors.append(f"SourceCreateRequest missing fields: {missing}")
        else:
            print("  ✓ SourceCreateRequest")
        
        sur_fields = ['topics']
        missing = check_class_attributes(SourceUpdateRequest, sur_fields)
        if missing:
            errors.append(f"SourceUpdateRequest missing fields: {missing}")
        else:
            print("  ✓ SourceUpdateRequest")
        
        assert NotebookLinkRequest is not None
        print("  ✓ NotebookLinkRequest")
        
    except Exception as e:
        errors.append(f"Models: {e}")
        import traceback
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
    
    # ========================================================================
    # 2. Check Config
    # ========================================================================
    print("\n[2] Checking Config...")
    try:
        from src.config import (
            ConfigLoader, ConfigValidator, TopicResolver, PromptLoader,
            ConfigError, ConfigNotFoundError, ConfigValidationError
        )
        
        # ConfigLoader methods
        loader_methods = ['load_pipeline_config', 'load_topics_config', 'load_channels_config']
        missing = check_methods(ConfigLoader, loader_methods)
        if missing:
            errors.append(f"ConfigLoader missing: {missing}")
        else:
            print("  ✓ ConfigLoader")
        
        # ConfigValidator methods
        validator_methods = ['validate_pipeline_config', 'validate_topics_config']
        missing = check_methods(ConfigValidator, validator_methods)
        if missing:
            errors.append(f"ConfigValidator missing: {missing}")
        else:
            print("  ✓ ConfigValidator")
        
        # TopicResolver methods
        resolver_methods = ['resolve_topic']
        missing = check_methods(TopicResolver, resolver_methods)
        if missing:
            errors.append(f"TopicResolver missing: {missing}")
        else:
            print("  ✓ TopicResolver")
        
        # PromptLoader (config version has load_analysis_prompt)
        prompt_methods = ['load_analysis_prompt']
        missing = check_methods(PromptLoader, prompt_methods)
        if missing:
            errors.append(f"Config PromptLoader missing: {missing}")
        else:
            print("  ✓ PromptLoader (config)")
            
    except Exception as e:
        errors.append(f"Config: {e}")
        import traceback
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
    
    # ========================================================================
    # 3. Check Discovery
    # ========================================================================
    print("\n[3] Checking Discovery...")
    try:
        from src.discovery import (
            FileScanner, FrontmatterParser, TranscriptMetadataExtractor,
            StatusChecker, FileFilter, DiscoveryService,
            DiscoveryError, MetadataExtractionError, FrontmatterParseError
        )
        
        # FileScanner
        scanner_methods = ['scan']
        missing = check_methods(FileScanner, scanner_methods)
        if missing:
            errors.append(f"FileScanner missing: {missing}")
        else:
            print("  ✓ FileScanner")
        
        # FrontmatterParser
        parser_methods = ['parse', 'parse_file']
        missing = check_methods(FrontmatterParser, parser_methods)
        if missing:
            errors.append(f"FrontmatterParser missing: {missing}")
        else:
            print("  ✓ FrontmatterParser")
        
        # TranscriptMetadataExtractor
        extractor_methods = ['extract', 'extract_video_id']
        missing = check_methods(TranscriptMetadataExtractor, extractor_methods)
        if missing:
            errors.append(f"TranscriptMetadataExtractor missing: {missing}")
        else:
            print("  ✓ TranscriptMetadataExtractor")
        
        # StatusChecker
        status_methods = ['get_status', 'is_processed', 'should_retry']
        missing = check_methods(StatusChecker, status_methods)
        if missing:
            errors.append(f"StatusChecker missing: {missing}")
        else:
            print("  ✓ StatusChecker")
        
        # FileFilter
        filter_methods = ['should_process']
        missing = check_methods(FileFilter, filter_methods)
        if missing:
            errors.append(f"FileFilter missing: {missing}")
        else:
            print("  ✓ FileFilter")
        
        # DiscoveryService
        service_methods = ['discover', 'get_statistics', 'cleanup_temp_files']
        missing = check_methods(DiscoveryService, service_methods)
        if missing:
            errors.append(f"DiscoveryService missing: {missing}")
        else:
            print("  ✓ DiscoveryService")
            
    except Exception as e:
        errors.append(f"Discovery: {e}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # 4. Check State
    # ========================================================================
    print("\n[4] Checking State...")
    try:
        from src.state import (
            FrontmatterReader, FrontmatterWriter, IdempotencyChecker,
            FileMover, StateManager, StatePersistence, FileState,
            StateError, FrontmatterReadError, FrontmatterWriteError
        )
        
        # FrontmatterReader
        reader_methods = ['read', 'read_status', 'read_source_id']
        missing = check_methods(FrontmatterReader, reader_methods)
        if missing:
            errors.append(f"FrontmatterReader missing: {missing}")
        else:
            print("  ✓ FrontmatterReader")
        
        # FrontmatterWriter
        writer_methods = ['write', 'write_status', 'write_source_id', 'write_error']
        missing = check_methods(FrontmatterWriter, writer_methods)
        if missing:
            errors.append(f"FrontmatterWriter missing: {missing}")
        else:
            print("  ✓ FrontmatterWriter")
        
        # IdempotencyChecker
        checker_methods = ['is_processed', 'is_pending', 'is_approved', 'is_failed', 'should_retry']
        missing = check_methods(IdempotencyChecker, checker_methods)
        if missing:
            errors.append(f"IdempotencyChecker missing: {missing}")
        else:
            print("  ✓ IdempotencyChecker")
        
        # FileMover
        mover_methods = ['move_to_pending', 'move_to_approved', 'ensure_directory']
        missing = check_methods(FileMover, mover_methods)
        if missing:
            errors.append(f"FileMover missing: {missing}")
        else:
            print("  ✓ FileMover")
        
        # StateManager
        manager_methods = ['mark_as_pending', 'mark_as_approved', 'mark_as_uploaded', 'mark_as_failed', 'get_file_status']
        missing = check_methods(StateManager, manager_methods)
        if missing:
            errors.append(f"StateManager missing: {missing}")
        else:
            print("  ✓ StateManager")
        
        # StatePersistence
        persistence_methods = ['save_analyzed_transcript', 'load_analyzed_transcript']
        missing = check_methods(StatePersistence, persistence_methods)
        if missing:
            errors.append(f"StatePersistence missing: {missing}")
        else:
            print("  ✓ StatePersistence")
            
    except Exception as e:
        errors.append(f"State: {e}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # 5. Check LLM
    # ========================================================================
    print("\n[5] Checking LLM...")
    try:
        from src.llm import (
            ProviderType, TranscriptInput, Segment, AnalysisResult,
            LLMClient, PromptLoader, OutputParser,
            LLMError, LLMCallError, LLMTimeoutError, LLMRateLimitError
        )
        from src.llm.gemini_cli import GeminiCLIProvider
        
        # Check Enums
        assert ProviderType.GEMINI_CLI.value == "gemini_cli"
        assert ProviderType.OPENAI_API.value == "openai_api"
        print("  ✓ ProviderType Enum")
        
        # TranscriptInput
        assert hasattr(TranscriptInput, 'content_preview')
        print("  ✓ TranscriptInput")
        
        # Segment
        seg_fields = ['section_type', 'title', 'start_quote']
        missing = check_class_attributes(Segment, seg_fields)
        if missing:
            errors.append(f"Segment missing fields: {missing}")
        else:
            print("  ✓ Segment")
        
        # AnalysisResult
        assert hasattr(AnalysisResult, 'to_dict')
        print("  ✓ AnalysisResult")
        
        # LLMClient
        client_methods = ['analyze', 'health_check', 'get_provider_name', 'get_model_info']
        missing = check_methods(LLMClient, client_methods)
        if missing:
            errors.append(f"LLMClient missing: {missing}")
        else:
            print("  ✓ LLMClient")
        
        # Check from_config factory method
        assert hasattr(LLMClient, 'from_config')
        print("  ✓ LLMClient.from_config factory")
        
        # GeminiCLIProvider
        gemini_methods = ['analyze', 'health_check', 'get_model_info']
        missing = check_methods(GeminiCLIProvider, gemini_methods)
        if missing:
            errors.append(f"GeminiCLIProvider missing: {missing}")
        else:
            print("  ✓ GeminiCLIProvider")
        
        # PromptLoader (LLM version has load and format)
        prompt_methods = ['load', 'format']
        missing = check_methods(PromptLoader, prompt_methods)
        if missing:
            errors.append(f"LLM PromptLoader missing: {missing}")
        else:
            print("  ✓ PromptLoader (llm)")
        
        # OutputParser
        parser_methods = ['extract_response', 'parse_analysis_result']
        missing = check_methods(OutputParser, parser_methods)
        if missing:
            errors.append(f"OutputParser missing: {missing}")
        else:
            print("  ✓ OutputParser")
            
    except Exception as e:
        errors.append(f"LLM: {e}")
        import traceback
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
    
    # ========================================================================
    # 6. Check Analyzer
    # ========================================================================
    print("\n[6] Checking Analyzer...")
    try:
        from src.analyzer import (
            AnalyzerService, StructuredSegmentation,
            AnalyzerError, AnalysisFailedError
        )
        
        # AnalyzerService
        analyzer_methods = ['analyze', 'analyze_batch']
        missing = check_methods(AnalyzerService, analyzer_methods)
        if missing:
            errors.append(f"AnalyzerService missing: {missing}")
        else:
            print("  ✓ AnalyzerService")
        
        # Check __init__ accepts llm_client
        import inspect
        sig = inspect.signature(AnalyzerService.__init__)
        params = list(sig.parameters.keys())
        assert 'llm_client' in params
        print("  ✓ AnalyzerService accepts llm_client")
        
        # StructuredSegmentation
        seg_methods = ['inject_headers', 'find_quote_position']
        missing = check_methods(StructuredSegmentation, seg_methods)
        if missing:
            errors.append(f"StructuredSegmentation missing: {missing}")
        else:
            print("  ✓ StructuredSegmentation")
            
    except Exception as e:
        errors.append(f"Analyzer: {e}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # 7. Check Uploader
    # ========================================================================
    print("\n[7] Checking Uploader...")
    try:
        from src.uploader import (
            OpenNotebookClient, SourceBuilder, UploaderService,
            UploadResult, UploadStatistics,
            UploadError, APIError, AuthenticationError
        )
        
        # OpenNotebookClient
        client_methods = [
            'health_check', 'create_source', 'update_source_topics',
            'link_source_to_notebook', 'ensure_notebook_exists', 'trigger_embedding'
        ]
        missing = check_methods(OpenNotebookClient, client_methods)
        if missing:
            errors.append(f"OpenNotebookClient missing: {missing}")
        else:
            print("  ✓ OpenNotebookClient")
        
        # SourceBuilder
        builder_methods = ['build_create_request', 'build_update_request', 'build_title', 'build_content']
        missing = check_methods(SourceBuilder, builder_methods)
        if missing:
            errors.append(f"SourceBuilder missing: {missing}")
        else:
            print("  ✓ SourceBuilder")
        
        # UploaderService
        uploader_methods = ['upload', 'upload_batch', 'get_statistics']
        missing = check_methods(UploaderService, uploader_methods)
        if missing:
            errors.append(f"UploaderService missing: {missing}")
        else:
            print("  ✓ UploaderService")
            
    except Exception as e:
        errors.append(f"Uploader: {e}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # 8. Check Main/CLI
    # ========================================================================
    print("\n[8] Checking Main/CLI...")
    try:
        from src.main import KnowledgePipeline, main, create_parser
        
        # KnowledgePipeline
        pipeline_methods = [
            'run_discovery', 'run_analysis', 'run_upload', 'run_full_pipeline'
        ]
        missing = check_methods(KnowledgePipeline, pipeline_methods)
        if missing:
            errors.append(f"KnowledgePipeline missing: {missing}")
        else:
            print("  ✓ KnowledgePipeline")
        
        # Check CLI parser
        parser = create_parser()
        assert parser is not None
        print("  ✓ CLI argument parser")
        
        # Check main function
        assert callable(main)
        print("  ✓ main() entry point")
        
    except Exception as e:
        errors.append(f"Main: {e}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if errors:
        print(f"\n❌ Found {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("\n✅ All checks passed!")
        print("\nImplementation completeness:")
        print("  ✓ Models: All dataclasses and Enums")
        print("  ✓ Config: Loader, Validator, Resolver")
        print("  ✓ Discovery: Scanner, Parser, Extractor, Filter, Service")
        print("  ✓ State: Reader/Writer, Checker, Mover, Manager, Persistence")
        print("  ✓ LLM: Client, GeminiCLI Provider, Prompts, OutputParser")
        print("  ✓ Analyzer: Service with batch processing, Segmentation")
        print("  ✓ Uploader: API Client, Builder, Service with retry")
        print("  ✓ CLI: KnowledgePipeline orchestration with argparse")
        return 0


if __name__ == "__main__":
    sys.exit(main())
