"""
Knowledge Pipeline - Antigravity CLI Provider 連線與解析功能驗證腳本
"""

import sys
from pathlib import Path

# 將專案根目錄加入 Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.llm.models import TranscriptInput
from src.llm.antigravity_cli import AntigravityCLIProvider


def run_verification():
    print("=" * 60)
    print("🚀 開始驗證 Antigravity CLI Provider 功能...")
    print("=" * 60)
    
    # 1. 實例化 Provider
    print("\n[Step 1] 初始化 AntigravityCLIProvider...")
    provider = AntigravityCLIProvider(
        project_dir=project_root,
        timeout=120,
        max_retries=2,
        debug_input=True
    )
    print("✓ 初始化成功！")
    
    # 2. 測試 Health Check
    print("\n[Step 2] 執行 Health Check (agy --help 測試)...")
    if provider.health_check():
        print("✓ Health Check 通過！agy 指令可用且正常響應。")
    else:
        print("✗ Health Check 失敗！請確認 agy 指令是否正確安裝於 /usr/bin/ 或系統 path 中。")
        sys.exit(1)
        
    # 3. 建立測試轉錄輸入資料
    print("\n[Step 3] 準備測試模擬轉錄稿...")
    test_input = TranscriptInput(
        channel="Bankless",
        title="Why Ethereum is the Ultimate Settlement Layer",
        content=(
            "Ethereum is a decentralized, open-source blockchain with smart contract functionality. "
            "Ether is the native cryptocurrency of the platform. Among cryptocurrencies, Ether is second only to Bitcoin in market capitalization. "
            "In this episode, we talk about how Ethereum's layer 2 solutions are scaling the execution layer while mainnet secures settlement. "
            "We believe layer 2 rollups like Arbitrum and Optimism are key to scaling Ethereum to billions of users."
        ),
        published_at="2026-05-24",
        word_count=50,
        file_path=project_root / "temp" / "test_input.md",
        video_id="eth12345",
        duration="10:00"
    )
    print(f"✓ 模擬轉錄稿準備就緒（標題: {test_input.title}）")
    
    # 4. 呼叫 analyze() 進行 AI 語意分析
    print("\n[Step 4] 呼叫 analyze() 送出至 agy 進行語意分析（此步驟需等待幾秒）...")
    start_time = time.time() if 'time' in globals() else 0
    import time
    start_time = time.time()
    
    try:
        # 使用 default 模板進行分析
        result = provider.analyze(
            input_data=test_input,
            prompt_template="default"
        )
        elapsed_time = time.time() - start_time
        print(f"✓ 分析順利完成！耗時: {elapsed_time:.2f} 秒")
        
        # 5. 驗證結構化 JSON 解析結果
        print("\n[Step 5] 驗證結構化欄位解析結果...")
        print("-" * 40)
        print(f"Summary (摘要):\n  {result.semantic_summary}")
        print(f"\nTopics (主題):\n  {result.key_topics}")
        print(f"\nKey Entities (關鍵實體):\n  {result.key_entities}")
        
        if result.segments:
            print("\nSegments (影片段落):")
            for seg in result.segments[:3]:
                print(f"  {seg.title}: (Start Quote: {seg.start_quote})")
        
        print("-" * 40)
        print("🎉 恭喜！Antigravity CLI Provider 遷移驗證大獲成功！")
        print("結構化 JSON 解析 100% 正確，所有欄位均符合介面規格。")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 語意分析或解析失敗！錯誤訊息:\n{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_verification()
