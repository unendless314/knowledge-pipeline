#!/usr/bin/env python3
"""
Knowledge Pipeline - 入口腳本

使用方式:
    python run.py [command] [options]
"""

import sys
from pathlib import Path

# 添加 src 到路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
