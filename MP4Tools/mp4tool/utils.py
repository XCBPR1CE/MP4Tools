"""通用工具：分辨率解析、文件收集。
Shared helpers: resolution parsing and mp4 file collection.
"""
import argparse
import os
import re

from .validate import ValidationError, parse_size

# 已被本工具处理过的文件名模式：<原名>_<宽>x<高>[_后缀].mp4
# Naming pattern of files already produced by this tool:
# <stem>_<width>x<height>[_suffix].mp4
OUT_PATTERN = re.compile(r"_\d+x\d+(?:_[a-zA-Z0-9.]+)?\.mp4$", re.IGNORECASE)


def parse_resolution(s):
    """argparse 用的分辨率解析器，错误统一转成 ArgumentTypeError。
    Resolution parser used by argparse; errors become ArgumentTypeError."""
    try:
        width, height, _adjusted = parse_size(s)
        return width, height
    except ValidationError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def gcd(a, b):
    """最大公约数，用于显示宽高比 / greatest common divisor, for aspect ratio."""
    while b:
        a, b = b, a % b
    return a


def collect_mp4(root, recursive=False, name_filter=None):
    """收集目录下的 mp4 文件（排除本工具产出的命名）。
    Collect the mp4 files under a directory, skipping this tool's own output names."""
    regex = re.compile(name_filter, re.IGNORECASE) if name_filter else None

    def ok(name):
        return (name.lower().endswith(".mp4")
                and not OUT_PATTERN.search(name)
                and (regex is None or regex.search(name)))

    result = []
    if recursive:
        for cur, _, names in os.walk(root):
            for n in names:
                if ok(n):
                    result.append(os.path.join(cur, n))
    else:
        for n in os.listdir(root):
            full = os.path.join(root, n)
            if os.path.isfile(full) and ok(n):
                result.append(full)
    return sorted(result)
