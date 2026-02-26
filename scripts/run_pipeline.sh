#!/bin/bash
#
# Knowledge Pipeline Wrapper Script
# 用途：包裝 pipeline 執行，提供健康檢查與統一日誌
#

set -euo pipefail

# ============================================
# 設定區
# ============================================
PROJECT_DIR="/home/openclaw/Projects/knowledge-pipeline"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
RUN_SCRIPT="$PROJECT_DIR/run.py"
OPEN_NOTEBOOK_URL="http://localhost:5055"
LOG_DIR="$PROJECT_DIR/logs"

# 時間戳記
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/pipeline-$TIMESTAMP.log"

# 頻道列表（可依需求調整）
# 若設為空字串，則處理全部頻道
TARGET_CHANNEL="${1:-}"

# ============================================
# 函數定義
# ============================================

log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

check_open_notebook() {
    log "INFO" "檢查 Open Notebook 服務狀態..."
    
    if ! curl -sf "$OPEN_NOTEBOOK_URL" > /dev/null 2>&1; then
        log "ERROR" "Open Notebook 無法連線 (URL: $OPEN_NOTEBOOK_URL)"
        log "ERROR" "請確認容器是否運行: docker ps | grep open-notebook"
        return 1
    fi
    
    log "INFO" "Open Notebook 服務正常"
    return 0
}

check_environment() {
    log "INFO" "檢查執行環境..."
    
    # 檢查虛擬環境
    if [[ ! -f "$VENV_PYTHON" ]]; then
        log "ERROR" "虛擬環境不存在: $VENV_PYTHON"
        return 1
    fi
    
    # 檢查 run.py
    if [[ ! -f "$RUN_SCRIPT" ]]; then
        log "ERROR" "執行檔不存在: $RUN_SCRIPT"
        return 1
    fi
    
    # 確保 log 目錄存在
    mkdir -p "$LOG_DIR"
    
    log "INFO" "環境檢查通過"
    return 0
}

run_pipeline() {
    log "INFO" "開始執行 Knowledge Pipeline..."
    
    cd "$PROJECT_DIR"
    
    # 組合指令
    local cmd=("$VENV_PYTHON" "$RUN_SCRIPT" "run")
    
    # 若指定頻道，加入參數
    if [[ -n "$TARGET_CHANNEL" ]]; then
        cmd+=("--channel" "$TARGET_CHANNEL")
        log "INFO" "指定頻道: $TARGET_CHANNEL"
    else
        log "INFO" "處理全部頻道"
    fi
    
    log "INFO" "執行指令: ${cmd[*]}"
    
    # 執行並擷取輸出
    if "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO" "Pipeline 執行成功"
        return 0
    else
        log "ERROR" "Pipeline 執行失敗"
        return 1
    fi
}

cleanup_old_logs() {
    # 保留最近 30 天的 log
    log "INFO" "清理舊日誌（保留 30 天）..."
    find "$LOG_DIR" -name "pipeline-*.log" -type f -mtime +30 -delete 2>/dev/null || true
    log "INFO" "日誌清理完成"
}

# ============================================
# 主程式
# ============================================

main() {
    echo "========================================"
    echo "Knowledge Pipeline Automation"
    echo "開始時間: $(date)"
    echo "========================================"
    
    # 步驟 1: 環境檢查
    if ! check_environment; then
        exit 1
    fi
    
    # 步驟 2: 服務健康檢查
    if ! check_open_notebook; then
        exit 1
    fi
    
    # 步驟 3: 執行 Pipeline
    if ! run_pipeline; then
        log "ERROR" "執行失敗，詳見日誌: $LOG_FILE"
        exit 1
    fi
    
    # 步驟 4: 清理舊日誌
    cleanup_old_logs
    
    echo ""
    echo "========================================"
    echo "執行完成: $(date)"
    echo "日誌檔案: $LOG_FILE"
    echo "========================================"
    
    exit 0
}

# 執行主程式
main "$@"
