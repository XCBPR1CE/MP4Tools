"""交互式 CLI 菜单（无参数运行或显式选择时进入）。
Interactive CLI menu (entered when the tool is run without arguments).

每一步输入都会经过 validate 模块校验：
Every input step is validated through the validate module:

* 语法 / syntax  —— 数字、整数、分辨率、帧率分数、正则、路径字面量
                    numbers, integers, resolution, fps fractions, regex, path literals
* 越界 / bounds  —— 帧率、CRF、变速倍数、时长、码率、分辨率
                    frame rate, CRF, speed factor, duration, bitrate, resolution
* 危险 / danger  —— 覆盖源文件、覆盖已有产物、写入系统受保护目录
                    overwriting the source, clobbering outputs, protected directories

另外 _preflight() 在执行前再跑一遍 argparse 语法校验与范围校验，
并对批量覆盖这类危险操作要求二次确认。
In addition, _preflight() re-runs argparse syntax validation and bound checks
before execution, and asks for a second confirmation on dangerous operations
such as overwriting existing outputs in bulk.
"""
import os
import re

from . import validate as V

MENU = """
============================================================
  mp4tool - 通用 MP4 处理工具 / general-purpose MP4 toolkit
============================================================
  1. WebP 转 MP4 / convert WebP to MP4
  2. 调整分辨率（单文件 / 目录批量）/ resize (single file / directory)
  3. 变速（音视频同步）/ change speed (video + audio in sync)
  4. 补帧（光流法）/ frame interpolation (optical flow)
  5. 提取音轨 / extract the audio track
  6. 移除音轨 / remove the audio track
  7. 合并 / 替换音轨 / mux or replace the audio track
  8. 查看媒体信息 / show media information
  9. 显示帮助 / show help
  0. 退出 / quit
============================================================"""


class Cancelled(Exception):
    """用户放弃了当前向导 / the user abandoned the current wizard."""


# ---------------- 输入小工具 / input helpers ----------------

def _read(prompt):
    """读一行，去掉空白、包裹引号与拖拽路径前缀。
    Read one line, stripping blanks, wrapping quotes and drag-and-drop prefixes."""
    return V.strip_quotes(input(prompt))


def _ask_path(prompt, kind="file", suffixes=None):
    """校验输入路径；回车返回空串表示取消。
    Validate an input path; an empty line returns "" meaning cancel."""
    while True:
        raw = _read(prompt)
        if not raw:
            return ""
        try:
            if kind == "dir":
                return V.check_input_dir(raw)
            if kind == "any":
                return V.check_input_path(raw, suffixes)
            return V.check_input_file(raw, suffixes)
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_output(prompt, source=None, suffixes=None, supports_overwrite=True):
    """校验输出路径，返回 (路径, 是否附加 --overwrite)。
    Validate an output path and return (path, add_overwrite_flag).
    Empty input returns (None, False) to keep the tool's default name."""
    while True:
        raw = _read(prompt)
        if not raw:
            return None, False
        try:
            return V.check_output_path(raw, source=source, suffixes=suffixes), False
        except V.OutputExists as e:
            if _ask_yes(f"  覆盖已有文件? / overwrite the existing file? ({os.path.basename(e.path)})",
                        False):
                return e.path, supports_overwrite
            raise Cancelled() from e
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_float(prompt, default, lo, hi):
    while True:
        raw = _read(f"{prompt} [默认 / default {default:g}]: ")
        if not raw:
            return float(default)
        try:
            return V.parse_float(raw, lo=lo, hi=hi)
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_int(prompt, default, lo, hi):
    while True:
        raw = _read(f"{prompt} [默认 / default {default}]: ")
        if not raw:
            return int(default)
        try:
            return V.parse_int(raw, lo=lo, hi=hi)
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_fps(prompt, default):
    """帧率输入，接受 60 / 59.94 / 60000/1001。
    Frame-rate input; accepts 60, 59.94 and 60000/1001."""
    while True:
        raw = _read(f"{prompt} [默认 / default {default:g}]: ")
        if not raw:
            return float(default)
        try:
            return V.parse_fps(raw)
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_resolution(prompt="目标分辨率 WxH / target resolution WxH: "):
    while True:
        raw = _read(prompt)
        try:
            width, height, adjusted = V.parse_size(raw)
        except V.ValidationError as e:
            print(f"  ✗ {e}")
            continue
        if adjusted:
            print(f"  提示 / note: 奇数边长已向下取偶 / odd sides floored to even "
                  f"→ {width}x{height}")
        return width, height


def _ask_choice(prompt, choices):
    keys = "/".join(choices)
    while True:
        raw = input(f"{prompt} [{keys}]: ").strip().lower()
        if not raw:
            print(f"  请输入其中之一 / please pick one: {keys}")
            continue
        if raw in choices:
            return raw
        print(f"  无效选项 / invalid option，可选 / allowed: {keys}")


def _ask_yes(prompt, default=False):
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "是", "1", "true", "t"):
            return True
        if raw in ("n", "no", "否", "0", "false", "f"):
            return False
        print("  请回答 y 或 n / please answer y or n")


def _ask_regex(prompt):
    """可选正则输入，回车跳过 / optional regex input, empty line skips it."""
    while True:
        raw = _read(prompt)
        if not raw:
            return ""
        try:
            return V.check_regex(raw, "文件名正则", "filename regex")[1]
        except V.ValidationError as e:
            print(f"  ✗ {e}")


def _ask_many_paths(prompt):
    """一次输入多个路径（空格分隔，含空格请用引号），逐个校验。
    Read several paths at once (blank separated, quote paths with blanks) and
    validate each one."""
    while True:
        raw = _read(prompt)
        if not raw:
            return []
        parts = V.split_quoted(raw)
        found, errors, dirs = [], [], []
        for part in parts:
            try:
                if os.path.isdir(part):
                    V.check_input_dir(part)
                    dirs.append(part)
                else:
                    V.check_input_file(part, V.MEDIA_SUFFIXES)
                found.append(part)
            except V.ValidationError as e:
                errors.append(str(e))
        for error in errors:
            print(f"  ✗ {error}")
        if errors:
            continue
        if len(dirs) > 1:
            print("  ✗ 一次只能指定一个目录 / only one directory may be given at a time")
            continue
        return found


# ---------------- 各功能参数向导 / per-command wizards ----------------
# 每个 _wiz_* 只负责拼 argv 列表，最终仍走 cli.main(argv) → argparse。
# Each _wiz_* only builds an argv list; execution still goes through
# cli.main(argv) → argparse, so CLI rules apply unchanged.

def _wiz_webp():
    path = _ask_path("WebP 文件路径 / WebP file path: ", suffixes=V.WEBP_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    argv = ["webp", path]
    try:
        out, overwrite = _ask_output(
            "输出 MP4（回车用默认）/ output MP4 [Enter = default]: ",
            source=path, suffixes=V.OUT_MP4_SUFFIXES, supports_overwrite=False)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    del overwrite          # webp 子命令没有 --overwrite 开关 / webp has no --overwrite flag
    argv += ["--fps", str(_ask_int("帧率 fps / frame rate", 30, 1, int(V.MAX_FPS)))]
    argv += ["--duration",
             f"{_ask_float('静态 WebP 时长/秒 / static duration (s)', 3.0, V.MIN_DURATION, V.MAX_DURATION):g}"]
    return argv


def _wiz_resize():
    path = _ask_path("输入文件或目录 / input file or directory: ", kind="any")
    if not path:
        print("  已取消 / cancelled")
        return None
    argv = ["resize", path]
    width, height = _ask_resolution()
    argv += ["-s", f"{width}x{height}"]

    mode = _ask_choice("模式 (stretch=拉伸 / keep=保持比例加黑边 / crop=裁剪) / mode",
                       ["stretch", "keep", "crop"])
    if mode == "keep":
        argv.append("--keep-ratio")
    elif mode == "crop":
        argv.append("--crop")

    if os.path.isdir(path):
        if _ask_yes("递归子目录 / recurse into subdirectories", False):
            argv.append("-r")
        pattern = _ask_regex("文件名正则（回车跳过）/ filename regex (Enter = skip): ")
        if pattern:
            argv += ["--filter", pattern]
    else:
        try:
            out, overwrite = _ask_output(
                "输出路径（回车用默认）/ output path [Enter = default]: ",
                source=path, suffixes=V.OUT_MP4_SUFFIXES)
        except Cancelled:
            print("  已取消 / cancelled")
            return None
        if out:
            argv += ["-o", out]
        if overwrite:
            argv.append("--overwrite")
    return argv


def _wiz_speed():
    path = _ask_path("输入视频文件 / input video file: ", suffixes=V.VIDEO_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    factor = _ask_float("速度倍数（>1 加速 / <1 减速）/ speed factor", 2.0,
                        V.MIN_SPEED, V.MAX_SPEED)
    argv = ["speed", path, "-f", f"{factor:g}"]
    try:
        out, overwrite = _ask_output(
            "输出路径（回车用默认）/ output path [Enter = default]: ",
            source=path, suffixes=V.OUT_MP4_SUFFIXES)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    if overwrite:
        argv.append("--overwrite")
    return argv


def _wiz_interpolate():
    path = _ask_path("输入视频文件 / input video file: ", suffixes=V.VIDEO_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    fps = _ask_fps("目标帧率（如 60 / 120 / 60000/1001）/ target frame rate", 60.0)
    argv = ["interpolate", path, "--fps", f"{fps:g}"]
    quality = _ask_choice("质量档位 (fast=快 / balanced=默认 / quality=慢但更干净) / quality",
                          ["fast", "balanced", "quality"])
    if quality != "balanced":
        argv += ["--quality", quality]
    try:
        out, overwrite = _ask_output(
            "输出路径（回车用默认）/ output path [Enter = default]: ",
            source=path, suffixes=V.OUT_MP4_SUFFIXES)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    if overwrite:
        argv.append("--overwrite")
    return argv


def _wiz_audio_extract():
    path = _ask_path("输入视频文件 / input video file: ", suffixes=V.VIDEO_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    argv = ["audio", "extract", path]
    try:
        out, overwrite = _ask_output(
            "输出音频（回车用默认 .mka）/ output audio [Enter = default .mka]: ",
            source=path, suffixes=V.OUT_MKA_SUFFIXES, supports_overwrite=False)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    del overwrite          # audio 子命令没有 --overwrite 开关 / audio has no --overwrite flag
    return argv


def _wiz_audio_remove():
    path = _ask_path("输入视频文件 / input video file: ", suffixes=V.VIDEO_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    argv = ["audio", "remove", path]
    try:
        out, overwrite = _ask_output(
            "输出视频（回车用默认）/ output video [Enter = default]: ",
            source=path, suffixes=V.OUT_MP4_SUFFIXES, supports_overwrite=False)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    del overwrite
    return argv


def _wiz_audio_mux():
    path = _ask_path("输入视频文件 / input video file: ", suffixes=V.VIDEO_SUFFIXES)
    if not path:
        print("  已取消 / cancelled")
        return None
    audio = _ask_path("外部音频文件 / external audio file: ", suffixes=V.AUDIO_SUFFIXES)
    if not audio:
        print("  已取消 / cancelled")
        return None
    argv = ["audio", "mux", path, "-a", audio]
    try:
        out, overwrite = _ask_output(
            "输出视频（回车用默认）/ output video [Enter = default]: ",
            source=path, suffixes=V.OUT_MP4_SUFFIXES, supports_overwrite=False)
    except Cancelled:
        print("  已取消 / cancelled")
        return None
    if out:
        argv += ["-o", out]
    del overwrite
    return argv


def _wiz_info():
    paths = _ask_many_paths(
        "输入文件或目录（可多个，空格分隔；含空格请用引号）/ "
        "input file(s) or directory (several, blank separated; quote paths with blanks): ")
    if not paths:
        print("  已取消 / cancelled")
        return None
    return ["info"] + paths


WIZARDS = {
    "1": _wiz_webp,
    "2": _wiz_resize,
    "3": _wiz_speed,
    "4": _wiz_interpolate,
    "5": _wiz_audio_extract,
    "6": _wiz_audio_remove,
    "7": _wiz_audio_mux,
    "8": _wiz_info,
}


# ---------------- 执行前校验 / pre-execution gate ----------------

def _preflight(argv):
    """语法校验 → 范围校验 → 危险操作确认；任一失败返回 False。
    Syntax check → bound check → danger confirmation; False means abort."""
    from .cli import build_parser

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        print("  ✗ 参数语法错误，已取消 / argument syntax error, cancelled")
        return False

    problems = V.check_args_bounds(args)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}")
        print("  参数越界，已取消 / argument out of range, cancelled")
        return False

    reasons = V.danger_reasons(args)
    if reasons:
        print("  ⚠ 检测到危险操作 / dangerous operation detected:")
        for reason in reasons:
            print(f"    - {reason}")
        if not _ask_yes("  确认继续 / continue anyway", False):
            print("  已取消 / cancelled")
            return False
    return True


# ---------------- 主循环 / main loop ----------------

def interactive_loop():
    # 延迟导入避免与 cli 循环依赖 / lazy import to avoid a circular import with cli
    from .cli import main as cli_main, build_parser

    while True:
        print(MENU)
        try:
            choice = input("请选择 / select [0-9]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice.lower() in ("0", "q", "quit", "exit", "退出"):
            return 0

        if choice == "9":
            build_parser().print_help()
            print("\n提示 / hint: 查看某子命令详细帮助 / detailed help for one subcommand:"
                  " python mp4tool.py help <子命令 / subcommand>")
            continue

        if not re.fullmatch(r"[0-9]", choice):
            print("  ✗ 无效选择：请输入 0-9 的数字 / invalid choice: enter a digit 0-9\n")
            continue

        wiz = WIZARDS.get(choice)
        if wiz is None:
            print("  ✗ 无效选择 / invalid choice\n")
            continue

        try:
            argv = wiz()
        except (EOFError, KeyboardInterrupt):
            print("\n  已取消 / cancelled")
            continue
        except Cancelled:
            print("  已取消 / cancelled")
            continue
        except Exception as e:                      # 向导内的意外错误不拖垮主循环
            print(f"  ✗ 输入处理失败 / input handling failed: {e}")
            continue

        if not argv:
            print()
            continue

        if not _preflight(argv):
            try:
                input("\n按回车返回菜单 / press Enter to return to the menu...")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            print()
            continue

        print(f"\n  >>> 执行 / run: mp4tool.py {' '.join(argv)}\n")
        try:
            code = cli_main(argv)
        except KeyboardInterrupt:
            print("\n  已中断 / interrupted")
            code = 130
        except SystemExit as e:
            code = 0 if e.code is None else e.code
        except Exception as e:
            print(f"  处理失败 / failed: {e}")
            code = 1
        print(f"  (返回码 / exit code {code})")

        try:
            input("\n按回车返回菜单 / press Enter to return to the menu...")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        print()
