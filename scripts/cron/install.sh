#!/bin/bash
#
# Knowledge Pipeline Cron Job 安裝腳本
# 用途：一鍵安裝/移除 cron job
#

set -euo pipefail

PROJECT_DIR="/home/openclaw/Projects/knowledge-pipeline"
CRON_FILE="$PROJECT_DIR/scripts/cron/crontab.txt"
TEMP_CRON="/tmp/knowledge_pipeline_cron.tmp"

# ============================================
# 函數定義
# ============================================

show_help() {
    cat << EOF
Knowledge Pipeline Cron 管理工具

用法:
    $0 [command]

指令:
    install     安裝 cron job（預設每天凌晨 3:00）
    remove      移除所有 knowledge-pipeline 相關的 cron job
    status      顯示目前的 cron 設定
    test        測試執行 wrapper script（不影響 cron）
    help        顯示此說明

範例:
    $0 install    # 安裝 cron job
    $0 test       # 先測試執行看看
    $0 status     # 查看目前的 cron 設定
    $0 remove     # 移除 cron job

注意:
    - 安裝前建議先執行 "$0 test" 確認腳本正常
    - 安裝後可使用 "crontab -l" 查看結果
EOF
}

install_cron() {
    echo "📦 安裝 Knowledge Pipeline Cron Job..."
    
    # 檢查 wrapper script 是否存在且可執行
    if [[ ! -x "$PROJECT_DIR/scripts/run_pipeline.sh" ]]; then
        echo "❌ 錯誤: wrapper script 不存在或無執行權限"
        echo "   請先執行: chmod +x $PROJECT_DIR/scripts/run_pipeline.sh"
        exit 1
    fi
    
    # 備份現有的 crontab
    if crontab -l > /dev/null 2>&1; then
        crontab -l > "$TEMP_CRON.backup.$(date +%Y%m%d_%H%M%S)"
        echo "✅ 已備份現有 crontab"
    fi
    
    # 取得現有 crontab（排除 knowledge-pipeline 相關項目）
    crontab -l 2>/dev/null | grep -v "knowledge-pipeline" | grep -v "run_pipeline.sh" > "$TEMP_CRON" || true
    
    # 加入新的 cron job
    echo "" >> "$TEMP_CRON"
    echo "# ========== Knowledge Pipeline (Auto-generated) ==========" >> "$TEMP_CRON"
    cat "$CRON_FILE" >> "$TEMP_CRON"
    echo "# ========== End of Knowledge Pipeline ==========" >> "$TEMP_CRON"
    
    # 安裝新的 crontab
    crontab "$TEMP_CRON"
    rm -f "$TEMP_CRON"
    
    echo "✅ Cron job 安裝成功！"
    echo ""
    echo "📋 目前的設定:"
    echo "   執行時間: 每天凌晨 3:00"
    echo "   執行指令: $PROJECT_DIR/scripts/run_pipeline.sh"
    echo ""
    echo "🔍 可使用以下指令查看:"
    echo "   crontab -l"
    echo "   tail -f $PROJECT_DIR/logs/cron.log"
}

remove_cron() {
    echo "🗑️  移除 Knowledge Pipeline Cron Job..."
    
    # 備份
    if crontab -l > /dev/null 2>&1; then
        crontab -l > "$TEMP_CRON.backup.remove.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # 移除 knowledge-pipeline 相關項目
    crontab -l 2>/dev/null | grep -v "knowledge-pipeline" | grep -v "run_pipeline.sh" > "$TEMP_CRON" || true
    crontab "$TEMP_CRON"
    rm -f "$TEMP_CRON"
    
    echo "✅ Cron job 已移除"
}

show_status() {
    echo "📊 Knowledge Pipeline Cron 狀態"
    echo "================================"
    echo ""
    
    # 檢查 crontab 中是否有 knowledge-pipeline
    if crontab -l 2>/dev/null | grep -q "knowledge-pipeline"; then
        echo "✅ Cron job 已安裝"
        echo ""
        echo "📋 相關設定:"
        crontab -l | grep -A1 -B1 "knowledge-pipeline\|run_pipeline"
    else
        echo "❌ Cron job 未安裝"
    fi
    
    echo ""
    echo "📁 相關檔案:"
    echo "   Wrapper: $PROJECT_DIR/scripts/run_pipeline.sh"
    echo "   Cron設定: $CRON_FILE"
    echo "   Log目錄: $PROJECT_DIR/logs/"
    
    # 檢查 wrapper script
    if [[ -x "$PROJECT_DIR/scripts/run_pipeline.sh" ]]; then
        echo ""
        echo "✅ Wrapper script 可執行"
    else
        echo ""
        echo "⚠️  Wrapper script 尚未設定執行權限"
        echo "   請執行: chmod +x $PROJECT_DIR/scripts/run_pipeline.sh"
    fi
}

test_run() {
    echo "🧪 測試執行 Knowledge Pipeline..."
    echo "================================"
    echo ""
    echo "這會實際執行一次 pipeline，但只處理已設定的頻道。"
    echo "建議先確認 Open Notebook 容器是否運行。"
    echo ""
    read -p "確定要繼續嗎？ (y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo ""
        "$PROJECT_DIR/scripts/run_pipeline.sh"
    else
        echo "已取消"
    fi
}

# ============================================
# 主程式
# ============================================

case "${1:-help}" in
    install)
        install_cron
        ;;
    remove)
        read -p "確定要移除 cron job 嗎？ (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            remove_cron
        else
            echo "已取消"
        fi
        ;;
    status)
        show_status
        ;;
    test)
        test_run
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "未知指令: $1"
        show_help
        exit 1
        ;;
esac
