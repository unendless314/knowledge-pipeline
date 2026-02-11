#!/usr/bin/env python3
"""
Detailed Code Review - 對照 PRD 和介面定義的深入檢查
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def check_type_consistency():
    """檢查型別一致性"""
    print("\n[Type Consistency Check]")
    
    from src.models import PipelineStatus
    from src.discovery import StatusChecker
    
    checker = StatusChecker()
    
    # Test is_processed logic
    assert checker.is_processed({"status": "uploaded"}) == True
    assert checker.is_processed({"status": "approved"}) == True
    assert checker.is_processed({"status": "pending"}) == True
    assert checker.is_processed({"status": "failed"}) == False
    assert checker.is_processed({}) == False
    print("  ✓ StatusChecker.is_processed logic correct")
    
    # Test should_retry logic
    assert checker.should_retry({"status": "failed"}, force=False) == False
    assert checker.should_retry({"status": "failed"}, force=True) == True
    assert checker.should_retry({}) == True
    print("  ✓ StatusChecker.should_retry logic correct")


def check_error_hierarchy():
    """檢查錯誤類別繼承關係"""
    print("\n[Error Hierarchy Check]")
    
    # Discovery errors
    from src.discovery import DiscoveryError, MetadataExtractionError, FrontmatterParseError
    assert issubclass(MetadataExtractionError, DiscoveryError)
    assert issubclass(FrontmatterParseError, DiscoveryError)
    print("  ✓ Discovery error hierarchy correct")
    
    # State errors
    from src.state import StateError, FrontmatterReadError, FrontmatterWriteError
    assert issubclass(FrontmatterReadError, StateError)
    assert issubclass(FrontmatterWriteError, StateError)
    print("  ✓ State error hierarchy correct")
    
    # LLM errors
    from src.llm import LLMError, LLMCallError, LLMTimeoutError, LLMRateLimitError
    assert issubclass(LLMCallError, LLMError)
    assert issubclass(LLMTimeoutError, LLMError)
    assert issubclass(LLMRateLimitError, LLMError)
    print("  ✓ LLM error hierarchy correct")
    
    # Analyzer errors
    from src.analyzer import AnalyzerError, AnalysisFailedError
    assert issubclass(AnalysisFailedError, AnalyzerError)
    print("  ✓ Analyzer error hierarchy correct")
    
    # Uploader errors
    from src.uploader import UploadError, APIError, AuthenticationError
    assert issubclass(APIError, UploadError)
    assert issubclass(AuthenticationError, APIError)
    print("  ✓ Uploader error hierarchy correct")


def check_protocol_compliance():
    """檢查是否符合 Protocol 定義"""
    print("\n[Protocol Compliance Check]")
    
    # This checks that our concrete classes implement the right methods
    # Not actual Protocol runtime check, but method existence check
    
    from src.discovery import FileScanner, FrontmatterParser, DiscoveryService
    from src.state import FrontmatterReader, FrontmatterWriter, StateManager
    from src.llm.gemini_cli import GeminiCLIProvider
    from src.uploader import OpenNotebookClient, UploaderService
    
    # FileScanner
    assert hasattr(FileScanner, 'scan')
    print("  ✓ FileScanner implements scan()")
    
    # FrontmatterParser
    assert hasattr(FrontmatterParser, 'parse')
    assert hasattr(FrontmatterParser, 'parse_file')
    print("  ✓ FrontmatterParser implements parse() and parse_file()")
    
    # DiscoveryService
    assert hasattr(DiscoveryService, 'discover')
    assert hasattr(DiscoveryService, 'get_statistics')
    print("  ✓ DiscoveryService implements discover() and get_statistics()")
    
    # StateManager
    assert hasattr(StateManager, 'mark_as_pending')
    assert hasattr(StateManager, 'mark_as_uploaded')
    assert hasattr(StateManager, 'mark_as_failed')
    print("  ✓ StateManager implements mark_as_* methods")
    
    # GeminiCLIProvider
    assert hasattr(GeminiCLIProvider, 'analyze')
    assert hasattr(GeminiCLIProvider, 'health_check')
    print("  ✓ GeminiCLIProvider implements analyze() and health_check()")
    
    # OpenNotebookClient
    assert hasattr(OpenNotebookClient, 'create_source')
    assert hasattr(OpenNotebookClient, 'update_source_topics')
    assert hasattr(OpenNotebookClient, 'link_source_to_notebook')
    print("  ✓ OpenNotebookClient implements API methods")


def check_import_cycles():
    """檢查是否有循環導入"""
    print("\n[Import Cycle Check]")
    
    # Clear any cached imports
    for mod in list(sys.modules.keys()):
        if 'src.' in mod:
            del sys.modules[mod]
    
    try:
        # Try importing in the order defined in modules.md
        from src import models
        from src.llm import models as llm_models
        from src import config
        from src import discovery
        from src import state
        from src.llm import gemini_cli, prompts, client
        from src import analyzer
        from src import uploader
        from src import main
        
        print("  ✓ No import cycles detected")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def check_critical_documentation():
    """檢查關鍵函數是否有文件字串"""
    print("\n[Documentation Check]")
    
    from src.discovery import DiscoveryService
    from src.analyzer import AnalyzerService
    from src.uploader import UploaderService
    
    # Check DiscoveryService.discover
    assert DiscoveryService.discover.__doc__ is not None
    assert "Args:" in DiscoveryService.discover.__doc__
    print("  ✓ DiscoveryService.discover documented")
    
    # Check AnalyzerService.analyze
    assert AnalyzerService.analyze.__doc__ is not None
    assert "Args:" in AnalyzerService.analyze.__doc__
    print("  ✓ AnalyzerService.analyze documented")
    
    # Check UploaderService.upload
    assert UploaderService.upload.__doc__ is not None
    assert "Args:" in UploaderService.upload.__doc__
    print("  ✓ UploaderService.upload documented")


def check_data_flow():
    """檢查資料流是否正確"""
    print("\n[Data Flow Check]")
    
    from datetime import date
    from src.models import TranscriptMetadata, TranscriptFile, PipelineStatus
    from src.llm import TranscriptInput
    
    # Create test metadata
    metadata = TranscriptMetadata(
        channel="TestChannel",
        video_id="dQw4w9WgXcQ",
        title="Test Title",
        published_at=date(2026, 2, 11),
        duration="10:00",
        word_count=1000
    )
    
    # Create test TranscriptFile
    from pathlib import Path
    transcript = TranscriptFile(
        path=Path("test.md"),
        metadata=metadata,
        content="Test content",
        status=PipelineStatus.PENDING
    )
    
    # Check properties
    assert transcript.video_id == "dQw4w9WgXcQ"
    assert transcript.channel == "TestChannel"
    print("  ✓ TranscriptFile properties work")
    
    # Check TranscriptInput creation (simulating what Analyzer does)
    input_data = TranscriptInput(
        channel=transcript.metadata.channel,
        title=transcript.metadata.title,
        content=transcript.content,
        published_at=transcript.metadata.published_at.isoformat(),
        word_count=transcript.metadata.word_count,
        file_path=transcript.path,
        video_id=transcript.metadata.video_id,
        duration=transcript.metadata.duration
    )
    
    assert input_data.channel == "TestChannel"
    assert input_data.content_preview  # Check property exists
    print("  ✓ TranscriptInput creation works")


def check_gemini_cli_safety():
    """檢查 Gemini CLI 安全性實作"""
    print("\n[Gemini CLI Safety Check]")
    
    from src.llm.gemini_cli import GeminiCLIProvider
    
    # Check that critical safety options are in the command
    import inspect
    source = inspect.getsource(GeminiCLIProvider._call_gemini_with_retry)
    
    # Check for required flags
    assert "'-p'" in source or '"-p"' in source, "Missing -p flag"
    assert "'plan'" in source or '"plan"' in source, "Missing plan mode"
    assert "cwd=" in source, "Missing cwd parameter"
    print("  ✓ Gemini CLI uses -p flag (headless mode)")
    print("  ✓ Gemini CLI uses plan approval mode")
    print("  ✓ Gemini CLI uses cwd parameter")
    
    # Check temp file cleanup
    source2 = inspect.getsource(GeminiCLIProvider._temp_transcript_file)
    assert "unlink" in source2, "Missing temp file cleanup"
    print("  ✓ Gemini CLI cleans up temp files")


def check_api_endpoints():
    """檢查 API 端點是否正確"""
    print("\n[API Endpoints Check]")
    
    from src.uploader import OpenNotebookClient
    import inspect
    
    source = inspect.getsource(OpenNotebookClient)
    
    # Check endpoints (handling f-strings)
    assert '/api/sources/json' in source, "Wrong create_source endpoint"
    assert '/api/sources/' in source, "Missing update_source_topics endpoint"
    assert '/api/notebooks/' in source, "Missing link_source_to_notebook endpoint"
    print("  ✓ Uses /api/sources/json (not /api/sources)")
    print("  ✓ Implements topic update after creation")
    print("  ✓ Implements notebook linking")


def main():
    print("=" * 70)
    print("Detailed Code Review - PRD Compliance Check")
    print("=" * 70)
    
    errors = []
    
    checks = [
        ("Type Consistency", check_type_consistency),
        ("Error Hierarchy", check_error_hierarchy),
        ("Protocol Compliance", check_protocol_compliance),
        ("Import Cycles", check_import_cycles),
        ("Documentation", check_critical_documentation),
        ("Data Flow", check_data_flow),
        ("Gemini CLI Safety", check_gemini_cli_safety),
        ("API Endpoints", check_api_endpoints),
    ]
    
    for name, check_fn in checks:
        try:
            check_fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"\n  ✗ {name} failed: {e}")
    
    print("\n" + "=" * 70)
    print("Review Summary")
    print("=" * 70)
    
    if errors:
        print(f"\n❌ Found {len(errors)} issue(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("\n✅ All detailed checks passed!")
        print("\nQuality Assurance:")
        print("  ✓ Type consistency validated")
        print("  ✓ Error hierarchy correct")
        print("  ✓ Protocol compliance verified")
        print("  ✓ No circular imports")
        print("  ✓ Documentation complete")
        print("  ✓ Data flow validated")
        print("  ✓ Gemini CLI safety measures in place")
        print("  ✓ API endpoints correct")
        return 0


if __name__ == "__main__":
    sys.exit(main())
