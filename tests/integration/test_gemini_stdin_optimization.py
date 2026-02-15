#!/usr/bin/env python3
"""
Integration Test: Gemini CLI stdin Optimization

此整合測試驗證 stdin 優化後的 Gemini CLI Provider 是否正常運作：
1. 透過 stdin 傳遞 prompt + transcript（1 次 API 呼叫，而非 3-4 次）
2. 記錄除錯輸入到 temp/debug/（便於觀測實際傳遞內容）
3. 解析結果並儲存到 intermediate/pending/

執行方式:
    cd /home/openclaw/Projects/knowledge-pipeline
    source venv/bin/activate
    python tests/integration/test_gemini_stdin_optimization.py

注意:
    - 此測試會實際呼叫 Gemini API，請確認額度充足
    - 測試會使用 config/config.yaml 的設定
    - 輸出檔案會保存在 temp/debug/ 和 intermediate/pending/
"""

import sys
from pathlib import Path

# 確保能找到 src 模組（從 tests/integration/ 回到專案根目錄）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import ConfigLoader
from src.discovery import DiscoveryService
from src.llm import LLMClient
from src.analyzer import AnalyzerService


def main():
    print("=" * 60)
    print("測試 stdin 優化後的 Gemini CLI Provider")
    print("=" * 60)
    
    # 載入設定
    config_loader = ConfigLoader()
    config = config_loader.load_pipeline_config()
    print(f"\n✅ 設定載入完成")
    print(f"   - Provider: {config.llm.provider}")
    print(f"   - Project Dir: {config.llm.project_dir}")
    print(f"   - Timeout: {config.llm.timeout}s")
    print(f"   - Max Retries: {config.llm.max_retries}")
    
    # 初始化 Discovery Service
    discovery = DiscoveryService()
    
    # 掃描一個檔案來測試
    print(f"\n📁 掃描轉錄檔案...")
    print(f"   - 輸入目錄: {config.transcriber_output}")
    
    transcripts = discovery.discover(
        root_dir=config.transcriber_output,
        min_word_count=100
    )
    
    if not transcripts:
        print("❌ 沒有找到任何轉錄檔案")
        return 1
    
    # 只取第一個檔案測試
    transcripts = transcripts[:1]
    
    transcript = transcripts[0]
    print(f"✅ 找到測試檔案:")
    print(f"   - Channel: {transcript.metadata.channel}")
    print(f"   - Title: {transcript.metadata.title[:50]}...")
    print(f"   - Word Count: {transcript.metadata.word_count}")
    print(f"   - Path: {transcript.path}")
    
    # 初始化 LLM Client
    print(f"\n🤖 初始化 LLM Client...")
    llm_config = {
        "provider": config.llm.provider,
        "project_dir": str(config.llm.project_dir),
        "timeout": config.llm.timeout,
        "max_retries": config.llm.max_retries,
        "debug_input": True  # 開啟除錢模式
    }
    
    client = LLMClient.from_config(llm_config)
    print(f"✅ LLM Client 初始化完成")
    print(f"   - Provider: {client.get_provider_name()}")
    
    # 初始化 Analyzer
    analyzer = AnalyzerService(
        llm_client=client,
        enable_segmentation=True,
        default_template="default"
    )
    
    # 確定輸出目錄
    output_dir = config.intermediate / "pending"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 執行分析
    print(f"\n📝 開始分析（透過 stdin 傳遞內容）...")
    print(f"   - Template: default")
    print(f"   - Output: {output_dir}")
    print(f"   - 預期 API 呼叫次數: 1 次（優化後）")
    print(f"   - 注意：這會實際呼叫 Gemini API，請確認額度足夠")
    print()
    
    try:
        result = analyzer.analyze(
            transcript=transcript,
            prompt_template="default",
            output_dir=output_dir
        )
        
        print(f"\n✅ 分析完成！")
        print(f"   - Semantic Summary: {result.analysis.semantic_summary[:100]}...")
        print(f"   - Key Topics: {result.analysis.key_topics}")
        print(f"   - Content Type: {result.analysis.content_type}")
        print(f"   - Content Density: {result.analysis.content_density}")
        print(f"   - Temporal Relevance: {result.analysis.temporal_relevance}")
        
        # 檢查除錯檔案
        debug_dir = Path("temp/debug")
        if debug_dir.exists():
            debug_files = list(debug_dir.glob("debug_*.md"))
            if debug_files:
                # 找最新的檔案
                latest = max(debug_files, key=lambda p: p.stat().st_mtime)
                print(f"\n📄 除錢檔案已生成:")
                print(f"   - {latest}")
                print(f"   - 大小: {latest.stat().st_size} bytes")
                print(f"\n   可以使用以下指令手動測試:")
                print(f"   cat '{latest}' | gemini -p \"Analyze and output JSON\"")
        
        print(f"\n💾 輸出檔案位置:")
        expected_path = output_dir / transcript.metadata.channel / transcript.metadata.published_at.strftime("%Y-%m")
        print(f"   - {expected_path}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 分析失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
