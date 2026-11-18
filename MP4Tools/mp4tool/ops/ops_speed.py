"""speed 子命令：变速（音视频同步）。
speed subcommand: change the playback speed, keeping video and audio in sync.
"""
import os
import sys

from ..core import process_video
from .. import validate as V


def _prompt_factor():
    """缺少 -f 时的交互输入，带语法与越界校验。
    Interactive fallback when -f is missing, with syntax and bound validation."""
    while True:
        raw = V.strip_quotes(input(
            "请输入速度倍数 (如 2.0 加速, 0.5 半速) / "
            "speed factor (e.g. 2.0 faster, 0.5 half speed): "))
        try:
            return V.parse_float(raw, "速度倍数", "speed factor",
                                 V.MIN_SPEED, V.MAX_SPEED)
        except V.ValidationError as e:
            print(f"  ✗ {e}", file=sys.stderr)


def cmd_speed(args):
    if args.factor is None:
        args.factor = _prompt_factor()
    try:
        factor = V.parse_float(str(args.factor), "速度倍数", "speed factor",
                               V.MIN_SPEED, V.MAX_SPEED)
        src = V.check_input_file(args.path, V.VIDEO_SUFFIXES)
    except V.ValidationError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1

    base = os.path.splitext(src)[0]
    out = args.output or f"{base}_x{factor:g}.mp4"
    try:
        # 危险操作校验 / danger check (same file, protected dir, bad suffix)
        out = V.check_output_path(out, source=src,
                                  suffixes=V.OUT_MP4_SUFFIXES, overwrite=True)
    except V.ValidationError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1
    if os.path.exists(out) and not args.overwrite:
        print(f"输出已存在，跳过 / output exists, skipped: {out} "
              f"(用 / use --overwrite 覆盖 / to overwrite)")
        return 0
    print(f"[处理 / processing] {src}")
    process_video(src, out, speed=factor,
                  crf=args.crf, preset=args.preset,
                  audio_bitrate=args.audio_bitrate)
    print(f"✓ 输出 / output: {out}")
    return 0
