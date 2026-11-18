"""info 子命令：查看媒体信息。
info subcommand: print media information.
"""
import os
import sys

from ..core import get_media_info
from ..utils import gcd
from .. import validate as V

# 常见的音视频媒体后缀（用于目录扫描过滤）
# Common audio/video suffixes, used to filter directory scans
MEDIA_EXTS = V.MEDIA_SUFFIXES


def _print_media_info(filepath):
    try:
        info = get_media_info(filepath)
    except Exception as e:
        print(f"[错误 / error] 无法解析 / cannot parse: {filepath} ({e})",
              file=sys.stderr)
        return

    fmt = info.get("format", {})
    print(f"文件 / file   : {filepath}")
    print(f"时长 / length : {float(fmt.get('duration', 0) or 0):.2f} s")
    print(f"大小 / size   : {int(fmt.get('size', 0) or 0) / 1024 / 1024:.2f} MB")
    print(f"码率 / bitrate: {int(fmt.get('bit_rate', 0) or 0) / 1000:.0f} kbps")
    for s in info.get("streams", []):
        t = s.get("codec_type")
        if t == "video":
            w, h = s.get("width") or 0, s.get("height") or 0
            g = gcd(w, h) if w and h else 1
            print(f"[视频 / video] {s.get('codec_name')} {w}x{h} "
                  f"({w // g}:{h // g}) fps={s.get('r_frame_rate')} "
                  f"pix_fmt={s.get('pix_fmt')}")
        elif t == "audio":
            print(f"[音频 / audio] {s.get('codec_name')} {s.get('channels')}ch "
                  f"sample_rate={s.get('sample_rate')}")


def cmd_info(args):
    inputs = args.inputs
    files_to_process = []
    dirs = []

    # 1. 分类路径（文件 vs 目录）/ classify the paths (file vs directory)
    for path in inputs:
        if os.path.isdir(path):
            dirs.append(path)
        elif os.path.isfile(path):
            files_to_process.append(path)
        else:
            print(f"警告 / warning: 路径不存在 / path does not exist: {path}",
                  file=sys.stderr)

    # 2. 拦截多个目录（根据需求，不支持多个目录）
    #    reject several directories at once: only one is supported by design
    if len(dirs) > 1:
        print("错误 / error: 不支持同时传入多个目录，请一次指定一个目录或多个文件 / "
              "several directories are not supported; pass one directory or several files",
              file=sys.stderr)
        return 1

    # 3. 如果是目录，递归扫描其中的媒体文件
    #    for a directory, scan it recursively for media files
    if dirs:
        target_dir = dirs[0]
        found = False
        for root, _, names in os.walk(target_dir):
            for n in names:
                ext = os.path.splitext(n)[1].lower()
                if ext in MEDIA_EXTS:
                    files_to_process.append(os.path.join(root, n))
                    found = True
        if not found:
            print(f"提示 / hint: 目录 / directory {target_dir} "
                  f"下未找到支持的媒体文件 / contains no supported media file",
                  file=sys.stderr)

    if not files_to_process:
        print("未找到任何可处理的媒体文件 / no processable media file was found")
        return 1

    # 4. 依次输出 / print one after another
    total = len(files_to_process)
    for i, f in enumerate(files_to_process):
        print(f"\n[{i+1}/{total}] ", end="")
        _print_media_info(f)
        print("-" * 50)

    return 0
