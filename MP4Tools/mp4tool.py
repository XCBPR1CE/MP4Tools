#!/usr/bin/env python3
"""mp4tool.py —— 命令行入口（转发到 mp4tool 包）。
mp4tool.py —— command-line entry point that forwards to the mp4tool package.

推荐用法 / recommended usage:
    python mp4tool.py                    # 交互模式 / interactive mode
    python mp4tool.py --help             # 命令行帮助 / command-line help
    python -m mp4tool                    # 等价写法 / equivalent invocation
"""
import os
import sys

# 保证从任意目录直接 python mp4tool.py 都能找到包
# Make `python mp4tool.py` work no matter what the current directory is
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from mp4tool.cli import main

if __name__ == "__main__":
    sys.exit(main())
