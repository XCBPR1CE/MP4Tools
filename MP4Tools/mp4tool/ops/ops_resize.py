"""resize 子命令：调整分辨率（单文件或目录批量）。
resize subcommand: change the resolution of one file or a whole directory.
"""
import os
import subprocess
import sys

from ..core import process_video
from ..utils import collect_mp4
from .. import validate as V


def _prompt_size():
    """缺少 -s 时的交互输入，带语法与越界校验。
    Interactive fallback when -s is missing, with syntax and bound validation."""
    while True:
        raw = V.strip_quotes(input(
            "请输入目标分辨率 (格式 WxH，例如 1920x1080) / "
            "target resolution WxH (e.g. 1920x1080): "))
        try:
            width, height, adjusted = V.parse_size(raw)
        except V.ValidationError as e:
            print(f"  ✗ {e}", file=sys.stderr)
            continue
        if adjusted:
            print(f"  提示 / note: 奇数边长已向下取偶 / odd sides floored to even "
                  f"→ {width}x{height}")
        return width, height


def _resize_one(src, tw, th, args, out=None):
    if out is None:
        base = os.path.splitext(src)[0]
        out = f"{base}_{tw}x{th}.mp4"
    if os.path.exists(out) and not args.overwrite:
        print(f"  - 跳过(已存在) / skipped (exists): {out}")
        return "skip"
    process_video(src, out, size=(tw, th),
                  keep_ratio=args.keep_ratio, crop=args.crop,
                  crf=args.crf, preset=args.preset,
                  audio_bitrate=args.audio_bitrate)
    print(f"  ✓ 输出 / output: {out}")
    return "ok"


def cmd_resize(args):
    if args.size is None:
        args.size = _prompt_size()
    tw, th = args.size

    # 目录模式 / directory mode
    if os.path.isdir(args.path):
        if args.filter:
            try:
                V.check_regex(args.filter, "文件名正则", "filename regex")
            except V.ValidationError as e:
                print(f"错误 / error: {e}", file=sys.stderr)
                return 1
        files = collect_mp4(args.path, args.recursive, args.filter)
        if not files:
            print(f"目录 / directory {args.path!r} 下没有 mp4 文件 / contains no mp4 file")
            return 0
        print(f"找到 / found {len(files)} 个 mp4，目标 / target {tw}x{th}")
        stats = {"ok": 0, "skip": 0, "fail": 0}
        for f in files:
            print(f"[处理 / processing] {f}")
            try:
                stats[_resize_one(f, tw, th, args)] += 1
            except subprocess.CalledProcessError as e:
                print(f"  ✗ 失败 / failed: {e}")
                stats["fail"] += 1
        print(f"\n完成 / done: 成功 / ok {stats['ok']}, "
              f"跳过 / skipped {stats['skip']}, 失败 / failed {stats['fail']}")
        return 0 if stats["fail"] == 0 else 1

    # 单文件模式 / single-file mode
    try:
        src = V.check_input_file(args.path, V.VIDEO_SUFFIXES)
    except V.ValidationError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1
    out = args.output
    if out:
        # 危险操作校验：拒绝覆盖源文件、写入系统目录、非法后缀
        # danger check: refuse overwriting the source, protected dirs, bad suffixes
        try:
            out = V.check_output_path(out, source=src,
                                      suffixes=V.OUT_MP4_SUFFIXES, overwrite=True)
        except V.ValidationError as e:
            print(f"错误 / error: {e}", file=sys.stderr)
            return 1
    print(f"[处理 / processing] {src}")
    try:
        _resize_one(src, tw, th, args, out=out)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ 失败 / failed: {e}", file=sys.stderr)
        return 1
    return 0
