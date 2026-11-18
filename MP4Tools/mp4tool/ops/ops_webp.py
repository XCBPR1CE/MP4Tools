"""webp 子命令：WebP（静态/动画）转 MP4。
webp subcommand: convert a static or animated WebP into an MP4.
"""
import os
import sys

from .. import validate as V
from ..webp import webp_to_mp4


def cmd_webp(args):
    # 再校验一次输入输出：命令行模式也享受交互模式同样的规则
    # Re-validate input and output so the CLI path follows the very same rules
    try:
        source = V.check_input_file(args.input, V.WEBP_SUFFIXES)
        output = args.output or os.path.splitext(source)[0] + ".mp4"
        output = V.check_output_path(output, source=source,
                                     suffixes=V.OUT_MP4_SUFFIXES, overwrite=True)
    except V.ValidationError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1

    webp_to_mp4(source, output, fps=args.fps, static_duration=args.duration)
    return 0
