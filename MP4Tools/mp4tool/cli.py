"""命令行入口：argparse 构建 + 分发 + 交互入口。
Command-line entry point: argparse construction, dispatch and the interactive entry.

所有类型转换器都来自 validate 模块，所以参数语法错误与越界会在 argparse
阶段直接被拒绝，命令行与交互模式共用同一套规则。
All type converters come from the validate module, so syntax errors and
out-of-range values are rejected right inside argparse; the CLI and the
interactive mode therefore share exactly the same rules.
"""
import argparse
import subprocess
import sys

from . import __version__
from .utils import parse_resolution
from .core import check_tools
from . import validate as V
from .ops import (cmd_webp, cmd_resize, cmd_speed, cmd_audio, cmd_info, cmd_help, cmd_interpolate)


# x264 预设列表 / x264 preset list
PRESETS = list(V.PRESETS)

_RD = argparse.RawDescriptionHelpFormatter


def _crf(text):
    """--crf 转换器，越界直接报错 / --crf converter that rejects out-of-range values."""
    return V.parse_int(text, "CRF", "CRF", V.MIN_CRF, V.MAX_CRF)


def _bitrate(text):
    """--audio-bitrate 转换器 / --audio-bitrate converter (e.g. 192k)."""
    return V.check_bitrate(text)


def _regex(text):
    """--filter 转换器，编译失败即语法错误 / --filter converter; a broken regex is a syntax error."""
    return V.check_regex(text, "文件名正则", "filename regex")[1]


def _add_quality_opts(sp):
    sp.add_argument("--crf", type=_crf, default=18,
                    help="x264 质量 0-51，越小越好（默认 18）/ "
                         "x264 quality 0-51, lower is better (default: 18)")
    sp.add_argument("--preset", default="medium", choices=PRESETS,
                    help="x264 编码预设（默认 medium）/ x264 encoding preset (default: medium)")
    sp.add_argument("--audio-bitrate", type=_bitrate, default="192k",
                    help="音频转码时的码率（默认 192k）/ audio bitrate when re-encoding (default: 192k)")
    sp.add_argument("--overwrite", action="store_true",
                    help="覆盖已存在的输出（危险操作）/ overwrite an existing output (destructive)")


def build_parser():
    p = argparse.ArgumentParser(
        prog="mp4tool.py",
        description=("通用 MP4 处理工具：WebP 转换 / 分辨率 / 变速 / 音轨操作 "
                     "/ general-purpose MP4 toolkit: WebP conversion, resize, "
                     "speed change, frame interpolation, audio-track operations"),
        epilog=(
            "示例 / examples:\n"
            "  python mp4tool.py                              # 交互模式 / interactive mode\n"
            "  python mp4tool.py webp msk.webp -o msk.mp4 --fps 30\n"
            "  python mp4tool.py resize ./videos -s 1920x1080 --keep-ratio -r\n"
            "  python mp4tool.py resize input.mp4 -s 1280x720 --crop\n"
            "  python mp4tool.py speed input.mp4 -f 2.0\n"
            "  python mp4tool.py audio extract input.mp4 -o audio.mka\n"
            "  python mp4tool.py audio remove input.mp4\n"
            "  python mp4tool.py audio mux silent.mp4 -a audio.mka -o final.mp4\n"
            "  python mp4tool.py info input.mp4\n"
            "  python mp4tool.py help audio extract\n"
        ),
        formatter_class=_RD,
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(
        dest="command", required=True,
        metavar="{webp,resize,speed,interpolate,audio,info,help}")
    subs = {}

    # ---------------- webp ----------------
    sp = sub.add_parser(
        "webp", help="WebP（静态/动画）转 MP4（无需 ffmpeg）/ convert static or animated WebP to MP4 (no ffmpeg needed)",
        description=("把静态或动画 WebP 转为 H.264 MP4。静态 WebP 会生成固定时长的静态视频。"
                     " / Convert a static or animated WebP into an H.264 MP4. "
                     "A static WebP becomes a fixed-duration still video."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py webp msk.webp\n"
                "  python mp4tool.py webp msk.webp -o out.mp4 --fps 60\n"
                "  python mp4tool.py webp logo.webp --duration 5\n"),
        formatter_class=_RD,
    )
    sp.add_argument("input", help="输入 WebP 文件 / input WebP file")
    sp.add_argument("-o", "--output",
                    help="输出 MP4 路径（默认与输入同名）/ output MP4 path (default: same stem)")
    sp.add_argument("--fps", type=lambda t: V.parse_int(t, "帧率", "frame rate", 1, int(V.MAX_FPS)),
                    default=30, help="帧率（默认 30）/ frame rate (default: 30)")
    sp.add_argument("--duration", type=lambda t: V.parse_float(
                        t, "静态时长", "static duration", V.MIN_DURATION, V.MAX_DURATION),
                    default=3.0,
                    help="静态 WebP 生成视频时长/秒（默认 3）/ clip length in seconds for a static WebP (default: 3)")
    sp.set_defaults(func=cmd_webp)
    subs["webp"] = sp

    # ---------------- resize ----------------
    sp = sub.add_parser(
        "resize", help="调整分辨率（单文件或目录批量）/ resize a single file or a whole directory",
        description=("把视频调整到目标分辨率。\n"
                     "  English: resize a video to the target resolution.\n"
                     "  默认          强制拉伸 / default: stretch\n"
                     "  --keep-ratio  保持比例 + 黑边 / keep ratio + black bars\n"
                     "  --crop        保持比例 + 裁剪填满 / keep ratio + crop to fill\n"
                     "路径是目录时批量处理其中所有 mp4（可 -r 递归）。\n"
                     "A directory path processes every mp4 inside it (-r to recurse)."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py resize input.mp4 -s 1920x1080\n"
                "  python mp4tool.py resize ./videos -s 1280x720 --keep-ratio -r\n"
                "  python mp4tool.py resize input.mp4 -s 1920x1080 --crop --crf 20\n"),
        formatter_class=_RD,
    )
    sp.add_argument("path", nargs="?", default=".",
                    help="输入文件或目录（默认: 当前目录）/ input file or directory (default: current directory)")
    sp.add_argument("-s", "--size", type=parse_resolution,
                    help="目标分辨率 WxH（省略则交互输入）/ target resolution WxH (asked interactively when omitted)")
    sp.add_argument("-o", "--output", help="单文件模式的输出路径 / output path in single-file mode")
    sp.add_argument("-r", "--recursive", action="store_true",
                    help="递归处理子目录 / recurse into subdirectories")
    sp.add_argument("--filter", metavar="REGEX", type=_regex,
                    help="仅处理文件名匹配该正则的 mp4 / only process mp4 whose name matches this regex")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--keep-ratio", action="store_true",
                   help="保持比例并加黑边 / keep the aspect ratio and add black bars")
    g.add_argument("--crop", action="store_true",
                   help="保持比例并裁剪填满 / keep the aspect ratio and crop to fill")
    _add_quality_opts(sp)
    sp.set_defaults(func=cmd_resize)
    subs["resize"] = sp

    # ---------------- speed ----------------
    sp = sub.add_parser(
        "speed", help="变速（视频 + 音频同步）/ change speed with video and audio in sync",
        description=("改变播放速度，视频用 setpts、音频用 atempo 同步处理。>1 加速，<1 减速。"
                     " / Change the playback speed: video via setpts, audio via atempo, "
                     "kept in sync. >1 speeds up, <1 slows down."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py speed input.mp4 -f 2.0\n"
                "  python mp4tool.py speed input.mp4 -f 0.5 -o slow.mp4\n"),
        formatter_class=_RD,
    )
    sp.add_argument("path", help="输入视频文件 / input video file")
    sp.add_argument("-f", "--factor", type=lambda t: V.parse_float(
                        t, "速度倍数", "speed factor", V.MIN_SPEED, V.MAX_SPEED),
                    help="速度倍数（>0；省略则交互输入）/ speed factor (>0; asked interactively when omitted)")
    sp.add_argument("-o", "--output", help="输出路径 / output path")
    _add_quality_opts(sp)
    sp.set_defaults(func=cmd_speed)
    subs["speed"] = sp

    # ---------------- interpolate ----------------
    sp = sub.add_parser(
        "interpolate", help="光流法补帧（minterpolate）/ frame interpolation with optical flow (minterpolate)",
        description=("用运动补偿插值（光流法）把视频提升到指定帧率。\n"
                     "补帧不改变视频时长，音频默认原样复制。\n"
                     "CPU 开销很大，短片段建议先用 --quality fast 试效果。\n"
                     "English: raise the frame rate with motion-compensated "
                     "interpolation. Duration is unchanged and audio is copied "
                     "as-is by default. It is CPU-heavy, so try --quality fast "
                     "on a short clip first."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py interpolate input.mp4 --fps 60\n"
                "  python mp4tool.py interpolate input.mp4 --fps 60 --quality fast\n"
                "  python mp4tool.py interpolate input.mp4 --fps 120 --quality quality\n"),
        formatter_class=_RD,
    )
    sp.add_argument("path", help="输入视频文件 / input video file")
    sp.add_argument("--fps", type=V.parse_fps, required=True,
                    help="目标帧率（如 60、120，或分数 60000/1001）/ target frame rate (e.g. 60, 120 or 60000/1001)")
    sp.add_argument("-o", "--output",
                    help="输出路径（默认 <原名>_<fps>fps.mp4）/ output path (default: <stem>_<fps>fps.mp4)")
    sp.add_argument("--quality", choices=["fast", "balanced", "quality"],
                    default="balanced",
                    help="补帧质量档位（默认 balanced）/ interpolation quality (default: balanced)")
    sp.add_argument("--no-audio", action="store_true", help="移除音轨 / drop the audio track")
    _add_quality_opts(sp)
    sp.set_defaults(func=cmd_interpolate)
    subs["interpolate"] = sp

    # ---------------- audio ----------------
    asp = sub.add_parser(
        "audio", help="音轨操作（extract / remove / mux）/ audio-track operations",
        description=("音轨相关操作，需指定子动作：extract / remove / mux。"
                     " / Audio-track operations; pick one action: extract / remove / mux."),
        formatter_class=_RD,
    )
    asub = asp.add_subparsers(dest="action", required=True,
                              metavar="{extract,remove,mux}")
    subs["audio"] = asp

    ep = asub.add_parser(
        "extract", help="提取音轨（不重编码，无损）/ extract the audio track (lossless, no re-encode)",
        description="把视频里的音轨原样提取成 .mka，不重编码。 / Copy the audio track into .mka without re-encoding.",
        epilog=("示例 / examples:\n"
                "  python mp4tool.py audio extract input.mp4\n"
                "  python mp4tool.py audio extract input.mp4 -o audio.mka\n"),
        formatter_class=_RD,
    )
    ep.add_argument("input", help="输入视频 / input video")
    ep.add_argument("-o", "--output",
                    help="输出音频（默认 <原名>.mka）/ output audio (default: <stem>.mka)")
    ep.set_defaults(func=cmd_audio, audio_bitrate="192k")
    subs["audio extract"] = ep

    rp = asub.add_parser(
        "remove", help="移除音轨（不重编码）/ remove the audio track (no re-encode)",
        description="丢弃所有音轨，视频流原样复制。 / Drop every audio track and copy the video stream as-is.",
        epilog=("示例 / examples:\n"
                "  python mp4tool.py audio remove input.mp4\n"
                "  python mp4tool.py audio remove input.mp4 -o silent.mp4\n"),
        formatter_class=_RD,
    )
    rp.add_argument("input", help="输入视频 / input video")
    rp.add_argument("-o", "--output",
                    help="输出（默认 <原名>_noaudio.mp4）/ output (default: <stem>_noaudio.mp4)")
    rp.set_defaults(func=cmd_audio, audio_bitrate="192k")
    subs["audio remove"] = rp

    mp = asub.add_parser(
        "mux", help="合并视频与外部音轨（替换原音轨）/ mux an external audio track (replaces the original)",
        description=("把外部音频合到视频上；使用 -map 只保留目标视频轨和输入音轨，\n"
                     "所以原音轨会被替换而不是叠加。\n"
                     "English: mux an external audio file onto the video. -map keeps "
                     "only the target video track and the new audio, so the original "
                     "audio is replaced rather than mixed."),
        epilog="示例 / example:\n  python mp4tool.py audio mux silent.mp4 -a audio.mka -o final.mp4\n",
        formatter_class=_RD,
    )
    mp.add_argument("input", help="输入视频 / input video")
    mp.add_argument("-a", "--audio-file", required=True, help="外部音频文件 / external audio file")
    mp.add_argument("-o", "--output",
                    help="输出路径（默认 <原名>_muxed.mp4）/ output path (default: <stem>_muxed.mp4)")
    mp.add_argument("--audio-bitrate", type=_bitrate, default="192k")
    mp.set_defaults(func=cmd_audio)
    subs["audio mux"] = mp

    # ---------------- info ----------------
    sp = sub.add_parser(
        "info", help="查看媒体信息 / show media information",
        description=("打印视频/音频流、时长、码率等信息（ffprobe）。\n"
                     "支持传入单个文件、多个文件，或单个目录（自动扫描目录下的媒体文件）。\n"
                     "English: print stream, duration and bitrate details via ffprobe. "
                     "Accepts one file, several files, or a single directory that is "
                     "scanned for media files."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py info input.mp4\n"
                "  python mp4tool.py info a.mp4 b.mkv c.mp3\n"
                "  python mp4tool.py info ./videos\n"),
        formatter_class=_RD,
    )
    sp.add_argument("inputs", nargs="+", help="输入文件或单个目录路径 / input files or one directory")
    sp.set_defaults(func=cmd_info)
    subs["info"] = sp

    # ---------------- help ----------------
    hp = sub.add_parser(
        "help", help="显示帮助；可指定子命令（如 help resize / help audio extract）/ show help for a subcommand path",
        description=("打印帮助信息。不带参数等价于 --help；\n"
                     "带参数显示指定子命令的详细帮助。\n"
                     "English: print help. Without arguments it equals --help; with "
                     "a subcommand path it prints that subcommand's detailed help."),
        epilog=("示例 / examples:\n"
                "  python mp4tool.py help\n"
                "  python mp4tool.py help resize\n"
                "  python mp4tool.py help audio extract\n"),
        formatter_class=_RD,
    )
    hp.add_argument("topic", nargs="*", help="子命令路径（空格分隔）/ subcommand path (space separated)")
    hp.set_defaults(func=cmd_help)
    subs["help"] = hp

    # 注入 parser 和子命令表，供 cmd_help 使用
    # inject the parser and the subcommand table so cmd_help can use them
    p.set_defaults(_parser=p, _subs=subs)
    return p


def main(argv=None):
    # 强制终端使用 UTF-8 编解码，解决 Windows 下的中文乱码和报错
    # Force UTF-8 on the terminal to avoid mojibake / UnicodeEncodeError on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
            sys.stdin.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    if argv is None:
        argv = sys.argv[1:]

    # 无任何参数 → 交互模式 / no arguments at all → interactive mode
    if not argv:
        from .interact import interactive_loop
        return interactive_loop()

    parser = build_parser()
    args = parser.parse_args(argv)

    # webp / help 不需要 ffmpeg / webp and help do not need ffmpeg
    if args.command not in ("webp", "help"):
        ok, missing = check_tools("ffprobe", "ffmpeg")
        if not ok:
            print(f"错误 / error: 未找到 / not found: {missing}，请先安装并加入 PATH / "
                  f"please install it and add it to PATH",
                  file=sys.stderr)
            return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已取消 / cancelled", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg 失败 / ffmpeg failed: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1
