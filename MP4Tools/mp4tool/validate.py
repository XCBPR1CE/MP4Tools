"""输入校验模块 / Input-validation module.

所有交互式输入都会经过本模块校验，覆盖三类问题：
Every interactive input is validated here, covering three classes of problems:

1. 语法错误 / syntax errors
   空值、非数字、非整数、非法文件名字符、错误的正则、会被当成命令行选项的路径。
   blank values, non-numeric or non-integer text, illegal filename characters,
   broken regular expressions, paths that ffmpeg would parse as an option.

2. 越界输出 / out-of-range values
   分辨率、帧率、CRF、变速倍数、时长、音频码率超出允许区间。
   resolution, frame rate, CRF, speed factor, duration and audio bitrate.

3. 危险操作 / dangerous operations
   覆盖源文件、批量覆盖已有产物、写入系统受保护目录。
   overwriting the source file, overwriting existing outputs, writing into
   protected system directories.

除交互模式外，cli 的 argparse 类型转换（如 --size）也复用这里的解析器，
所以命令行与交互式得到的是同一套校验规则。
Besides the interactive mode, the argparse type converters (e.g. --size) reuse
the parsers below, so the CLI and the wizard share the exact same rules.
"""
import os
import re

# ---------------- 允许区间 / allowed ranges ----------------
MIN_SIZE = 16              # 最小边长（像素）/ smallest side, px
MAX_SIZE = 16384           # 最大边长（像素）/ largest side, px
MIN_FPS = 1.0              # 最小帧率 / lowest frame rate
MAX_FPS = 240.0            # 最大帧率 / highest frame rate
MIN_CRF = 0                # x264 CRF 下限 / CRF lower bound
MAX_CRF = 51               # x264 CRF 上限 / CRF upper bound
MIN_SPEED = 0.01           # 最小变速倍数 / slowest speed factor
MAX_SPEED = 100.0          # 最大变速倍数 / fastest speed factor
MIN_DURATION = 0.1         # 静态 WebP 最短时长/秒 / shortest static WebP duration
MAX_DURATION = 600.0       # 静态 WebP 最长时长/秒 / longest static WebP duration
MIN_BITRATE_KBPS = 8       # 音频码率下限 / audio bitrate lower bound
MAX_BITRATE_KBPS = 1024    # 音频码率上限 / audio bitrate upper bound
MAX_PATH_LEN = 240         # 路径长度上限 / maximum path length

# x264 预设 / x264 encoding presets
PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast",
           "medium", "slow", "slower", "veryslow")

# 后缀集合 / suffix sets
VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm",
                  ".m4v", ".wmv", ".ts", ".mpg", ".mpeg"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".mka",
                  ".ogg", ".wma", ".opus", ".ac3"}
WEBP_SUFFIXES = {".webp"}
MEDIA_SUFFIXES = VIDEO_SUFFIXES | AUDIO_SUFFIXES
OUT_MP4_SUFFIXES = {".mp4"}
OUT_MKA_SUFFIXES = {".mka"}

_UNSIGNED_INT = re.compile(r"[0-9]+")
_SIGNED_INT = re.compile(r"[+-]?[0-9]+")
_FLOAT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_SPLIT_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')


# ---------------- 异常 / exceptions ----------------

class ValidationError(ValueError):
    """校验失败 / validation failure."""


class OutputExists(ValidationError):
    """目标文件已存在（覆盖属于危险操作）/ target already exists (overwriting is destructive)."""

    def __init__(self, message, path=""):
        super().__init__(message)
        self.path = path


def msg(zh, en):
    """拼接中英双语提示 / join a bilingual (Chinese + English) message."""
    return f"{zh} / {en}"


# ---------------- 基础语法 / basic syntax ----------------

def strip_quotes(text):
    """去掉首尾空白、包裹引号，以及 Windows"复制为路径"带出的 "& " 前缀。
    Strip surrounding blanks, wrapping quotes, and the "& " prefix that
    Windows' "Copy as path" adds for drag-and-dropped paths."""
    value = (text or "").strip()
    if value.startswith("& "):
        value = value[2:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def split_quoted(text):
    """按空白拆分，但保留引号内的空格（用于一次输入多个路径）。
    Split on blanks while keeping blanks inside quotes (for multi-path input)."""
    return [strip_quotes(part) for part in _SPLIT_QUOTED.findall(text or "")]


def check_not_blank(value, field_zh="输入", field_en="input"):
    text = strip_quotes(value)
    if not text:
        raise ValidationError(msg(f"{field_zh}不能为空", f"{field_en} must not be empty"))
    return text


def check_no_control_chars(text):
    if any(ord(ch) < 32 for ch in text):
        raise ValidationError(msg("内容包含控制字符", "content contains control characters"))
    return text


def check_path_syntax(path):
    """只校验路径字面量，不访问文件系统。
    Validate the path literal only, without touching the file system."""
    text = check_not_blank(path, "路径", "path")
    check_no_control_chars(text)
    if text.startswith("-"):
        raise ValidationError(msg(
            "路径不能以 '-' 开头（会被 ffmpeg 当成命令行选项）",
            "path must not start with '-' (ffmpeg would treat it as an option)"))
    illegal = '<>"|?*' if os.name == "nt" else "\0"
    bad = "".join(sorted({ch for ch in text if ch in illegal}))
    if bad:
        raise ValidationError(msg(
            f"路径包含非法字符 {bad!r}",
            f"path contains illegal characters {bad!r}"))
    if len(text) > MAX_PATH_LEN:
        raise ValidationError(msg(
            f"路径过长（{len(text)} 字符 > 上限 {MAX_PATH_LEN}）",
            f"path too long ({len(text)} chars > limit {MAX_PATH_LEN})"))
    return text


def _check_range(value, field_zh, field_en, lo=None, hi=None):
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        if lo is not None and hi is not None:
            span = f"{lo}~{hi}"
        elif lo is not None:
            span = f">={lo}"
        else:
            span = f"<={hi}"
        raise ValidationError(msg(
            f"{field_zh}越界: {value:g}（允许 {span}）",
            f"{field_en} out of range: {value:g} (allowed {span})"))
    return value


def parse_int(text, field_zh="数值", field_en="number", lo=None, hi=None):
    raw = check_not_blank(text, field_zh, field_en)
    if not _SIGNED_INT.fullmatch(raw):
        raise ValidationError(msg(
            f"{field_zh}必须是整数: {raw!r}",
            f"{field_en} must be an integer: {raw!r}"))
    value = int(raw)
    return _check_range(value, field_zh, field_en, lo, hi)


def parse_float(text, field_zh="数值", field_en="number", lo=None, hi=None):
    raw = check_not_blank(text, field_zh, field_en)
    if not _FLOAT.fullmatch(raw):
        raise ValidationError(msg(
            f"{field_zh}必须是数字: {raw!r}",
            f"{field_en} must be a number: {raw!r}"))
    value = float(raw)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError(msg(
            f"{field_zh}必须是有限数字: {raw!r}",
            f"{field_en} must be a finite number: {raw!r}"))
    return _check_range(value, field_zh, field_en, lo, hi)


def parse_fps(text, lo=MIN_FPS, hi=MAX_FPS):
    """接受 60、59.94、60000/1001 三种写法。
    Accept 60, 59.94 and 60000/1001 alike."""
    raw = check_not_blank(text, "帧率", "frame rate")
    if "/" in raw:
        numerator_text, _, denominator_text = raw.partition("/")
        numerator = parse_int(numerator_text, "帧率分子", "fps numerator", lo=1)
        denominator = parse_int(denominator_text, "帧率分母", "fps denominator", lo=1)
        value = numerator / denominator
    else:
        value = parse_float(raw, "帧率", "frame rate")
    return _check_range(value, "帧率", "frame rate", lo, hi)


def parse_size(text, field_zh="分辨率", field_en="resolution"):
    """解析 WxH，返回 (宽, 高, 是否取整)。奇数边长向下取偶并标记。
    Parse WxH and return (width, height, was_adjusted); odd sides are floored
    to even (yuv420p requires it) and the adjustment is flagged."""
    raw = check_not_blank(text, field_zh, field_en)
    cleaned = raw.lower().replace("*", "x").replace("×", "x").replace(" ", "")
    parts = cleaned.split("x")
    if len(parts) != 2 or not all(_UNSIGNED_INT.fullmatch(p or "") for p in parts):
        raise ValidationError(msg(
            f"{field_zh}格式错误: {raw!r}（应为 WxH，如 1920x1080）",
            f"invalid {field_en} format: {raw!r} (expected WxH, e.g. 1920x1080)"))
    width, height = int(parts[0]), int(parts[1])
    adjusted = bool(width % 2 or height % 2)
    width -= width % 2
    height -= height % 2
    for value, name_zh, name_en in ((width, "宽度", "width"),
                                    (height, "高度", "height")):
        _check_range(value, name_zh, name_en, MIN_SIZE, MAX_SIZE)
    return width, height, adjusted


def check_regex(pattern, field_zh="正则表达式", field_en="regular expression"):
    """编译正则并返回 (编译结果, 原文)，语法错误直接报错。
    Compile a regex and return (compiled, source); syntax errors are raised."""
    raw = check_not_blank(pattern, field_zh, field_en)
    try:
        return re.compile(raw, re.IGNORECASE), raw
    except re.error as exc:
        raise ValidationError(msg(
            f"{field_zh}语法错误: {raw!r}（{exc}）",
            f"{field_en} syntax error: {raw!r} ({exc})")) from exc


def check_bitrate(text):
    """音频码率，只接受 <数字>k 形式，如 192k。
    Audio bitrate; only the <number>k form (e.g. 192k) is accepted."""
    raw = check_not_blank(text, "音频码率", "audio bitrate").lower()
    match = re.fullmatch(r"([0-9]{1,5})k", raw)
    if not match:
        raise ValidationError(msg(
            f"音频码率格式错误: {text!r}（应形如 192k）",
            f"invalid audio bitrate: {text!r} (expected e.g. 192k)"))
    kbps = int(match.group(1))
    _check_range(kbps, "音频码率", "audio bitrate", MIN_BITRATE_KBPS, MAX_BITRATE_KBPS)
    return f"{kbps}k"


def check_suffix(path, suffixes, field_zh="文件", field_en="file"):
    ext = os.path.splitext(path)[1].lower()
    if ext not in suffixes:
        allowed = "/".join(sorted(suffixes))
        raise ValidationError(msg(
            f"{field_zh}扩展名 {ext or '(无)'} 不受支持，只允许 {allowed}",
            f"{field_en} extension {ext or '(none)'} is not supported, allowed: {allowed}"))
    return path


# ---------------- 文件系统 / file system ----------------

def _norm(path):
    """规范化路径用于比较 / normalise a path for comparisons."""
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(path)))
    except OSError:
        return os.path.normcase(os.path.abspath(path))


def _is_drive_root(path):
    """判断是否是根目录（C:\\ 或 /）/ whether the path is a drive root."""
    stripped = path.rstrip("\\/")
    if os.name == "nt":
        return len(stripped) == 2 and stripped[1] == ":"
    return stripped == ""


def _protected_roots():
    if os.name == "nt":
        drive = (os.environ.get("SystemDrive") or "C:") + os.sep
        candidates = [
            os.environ.get("SystemRoot") or os.environ.get("WINDIR"),
            os.path.join(drive, "Program Files"),
            os.path.join(drive, "Program Files (x86)"),
            os.path.join(drive, "ProgramData"),
            drive,
        ]
    else:
        candidates = ["/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
                      "/boot", "/dev", "/proc", "/sys", "/var", "/System", "/"]
    return tuple(_norm(c) for c in candidates if c)


PROTECTED_ROOTS = _protected_roots()


def protected_dir(path):
    """返回命中的受保护目录，未命中返回 None。
    Return the protected root that covers the path, or None."""
    target = _norm(path)
    for root in PROTECTED_ROOTS:
        if target == root:
            return root
        if _is_drive_root(root):
            continue           # 盘符根目录只做精确匹配 / drive roots match exactly
        if target.startswith(root + os.sep):
            return root
    return None


def check_input_file(path, suffixes=None):
    text = check_path_syntax(path)
    if not os.path.exists(text):
        raise ValidationError(msg(f"文件不存在: {text}", f"file does not exist: {text}"))
    if not os.path.isfile(text):
        raise ValidationError(msg(f"不是普通文件: {text}", f"not a regular file: {text}"))
    if suffixes:
        check_suffix(text, suffixes, "输入文件", "input file")
    if not os.access(text, os.R_OK):
        raise ValidationError(msg(f"文件不可读: {text}", f"file is not readable: {text}"))
    return text


def check_input_dir(path):
    text = check_path_syntax(path)
    if not os.path.exists(text):
        raise ValidationError(msg(f"目录不存在: {text}", f"directory does not exist: {text}"))
    if not os.path.isdir(text):
        raise ValidationError(msg(f"不是目录: {text}", f"not a directory: {text}"))
    if not os.access(text, os.R_OK | os.X_OK):
        raise ValidationError(msg(f"目录不可读: {text}", f"directory is not readable: {text}"))
    return text


def check_input_path(path, suffixes=None):
    """文件或目录都接受（resize / info 用）。
    Accept either a file or a directory (used by resize and info)."""
    text = check_path_syntax(path)
    if os.path.isdir(text):
        return check_input_dir(text)
    return check_input_file(text, suffixes)


def check_output_path(path, source=None, suffixes=None, overwrite=False):
    """校验输出路径并返回绝对路径；已存在且未声明覆盖时抛 OutputExists。
    Validate an output path and return its absolute form; raise OutputExists
    when the target exists and overwriting was not acknowledged."""
    text = check_path_syntax(path)
    if suffixes:
        check_suffix(text, suffixes, "输出文件", "output file")
    full = os.path.abspath(text)

    if os.path.isdir(full):
        raise ValidationError(msg(
            f"输出路径是一个目录: {full}",
            f"output path is a directory: {full}"))
    if source is not None and _norm(full) == _norm(source):
        raise ValidationError(msg(
            f"输出路径与输入相同，会覆盖源文件: {full}",
            f"output path equals the input; the source file would be destroyed: {full}"))

    parent = os.path.dirname(full) or os.curdir
    protected = protected_dir(parent)
    if protected:
        raise ValidationError(msg(
            f"拒绝写入受保护的系统目录 {protected}（危险操作）",
            f"refusing to write into the protected system directory {protected} (dangerous)"))
    if not os.path.isdir(parent):
        raise ValidationError(msg(
            f"输出目录不存在: {parent}",
            f"output directory does not exist: {parent}"))
    if not os.access(parent, os.W_OK):
        raise ValidationError(msg(
            f"输出目录不可写: {parent}",
            f"output directory is not writable: {parent}"))

    if os.path.exists(full) and not overwrite:
        raise OutputExists(msg(
            f"输出已存在（覆盖属于危险操作）: {full}",
            f"output already exists (overwriting is destructive): {full}"), full)
    return full


# ---------------- 参数整体校验 / whole-argv validation ----------------

def _iter_mp4(root, recursive=False, name_filter=None):
    """收集目录下的 mp4，排除本工具命名，供危险操作预估使用。
    Collect mp4 files (skipping this tool's own naming) to predict targets."""
    out_pattern = re.compile(r"_\d+x\d+(?:_[a-zA-Z0-9.]+)?\.mp4$", re.IGNORECASE)
    regex = None
    if name_filter:
        try:
            regex = re.compile(name_filter, re.IGNORECASE)
        except re.error:
            return []

    def ok(name):
        return (name.lower().endswith(".mp4")
                and not out_pattern.search(name)
                and (regex is None or regex.search(name)))

    result = []
    if recursive:
        for cur, _dirs, names in os.walk(root):
            for name in names:
                if ok(name):
                    result.append(os.path.join(cur, name))
    else:
        try:
            names = os.listdir(root)
        except OSError:
            return []
        for name in names:
            full = os.path.join(root, name)
            if os.path.isfile(full) and ok(name):
                result.append(full)
    return sorted(result)


def predict_outputs(args):
    """按各子命令的命名规则预估输出文件，用于危险操作检查。
    Predict the output files each subcommand will write, for the danger check."""
    command = getattr(args, "command", "")
    targets = []

    if command == "webp":
        source = getattr(args, "input", "")
        targets.append(args.output or os.path.splitext(source)[0] + ".mp4")
    elif command == "resize":
        source = getattr(args, "path", "")
        size = getattr(args, "size", None)
        if size:
            width, height = size
            if os.path.isdir(source):
                for found in _iter_mp4(source, getattr(args, "recursive", False),
                                       getattr(args, "filter", None)):
                    targets.append(f"{os.path.splitext(found)[0]}_{width}x{height}.mp4")
            else:
                targets.append(args.output or
                               f"{os.path.splitext(source)[0]}_{width}x{height}.mp4")
    elif command == "speed":
        source = getattr(args, "path", "")
        factor = getattr(args, "factor", None)
        if factor is not None:
            targets.append(args.output or
                           f"{os.path.splitext(source)[0]}_x{factor:g}.mp4")
    elif command == "interpolate":
        source = getattr(args, "path", "")
        fps = getattr(args, "fps", None)
        if fps is not None:
            targets.append(args.output or f"{os.path.splitext(source)[0]}_{fps:g}fps.mp4")
    elif command == "audio":
        source = getattr(args, "input", "")
        stem = os.path.splitext(source)[0]
        action = getattr(args, "action", "")
        if action == "extract":
            targets.append(args.output or stem + ".mka")
        elif action == "remove":
            targets.append(args.output or stem + "_noaudio.mp4")
        elif action == "mux":
            targets.append(args.output or stem + "_muxed.mp4")
    return [os.path.abspath(t) for t in targets if t]


def check_args_bounds(args):
    """范围校验已解析的参数，返回双语问题列表（空列表表示通过）。
    Bound-check a parsed namespace and return a bilingual list of problems."""
    problems = []

    def collect(func, *fargs, **fkwargs):
        try:
            func(*fargs, **fkwargs)
        except ValidationError as exc:
            problems.append(str(exc))
        except (TypeError, ValueError) as exc:
            problems.append(str(exc))

    size = getattr(args, "size", None)
    if size:
        collect(_check_range, size[0], "宽度", "width", MIN_SIZE, MAX_SIZE)
        collect(_check_range, size[1], "高度", "height", MIN_SIZE, MAX_SIZE)

    crf = getattr(args, "crf", None)
    if crf is not None:
        collect(_check_range, int(crf), "CRF", "CRF", MIN_CRF, MAX_CRF)

    command = getattr(args, "command", "")
    fps = getattr(args, "fps", None)
    if fps is not None:
        if command == "webp":
            collect(_check_range, int(fps), "帧率", "frame rate", 1, int(MAX_FPS))
        else:
            collect(_check_range, float(fps), "帧率", "frame rate", MIN_FPS, MAX_FPS)

    duration = getattr(args, "duration", None)
    if duration is not None:
        collect(_check_range, float(duration), "静态时长", "static duration",
                MIN_DURATION, MAX_DURATION)

    factor = getattr(args, "factor", None)
    if factor is not None:
        collect(_check_range, float(factor), "速度倍数", "speed factor",
                MIN_SPEED, MAX_SPEED)

    bitrate = getattr(args, "audio_bitrate", None)
    if bitrate:
        collect(check_bitrate, bitrate)

    name_filter = getattr(args, "filter", None)
    if name_filter:
        collect(check_regex, name_filter, "文件名正则", "filename regex")

    candidates = []
    for attr in ("path", "input"):
        candidates.append(getattr(args, attr, None))
    candidates.extend(getattr(args, "inputs", None) or [])
    for value in candidates:
        if isinstance(value, str) and value:
            collect(check_path_syntax, value)
    return problems


def danger_reasons(args):
    """返回危险操作的中英双语说明列表（空列表表示安全）。
    Return bilingual reasons for dangerous operations (empty list = safe)."""
    reasons = []
    if not getattr(args, "overwrite", False):
        return reasons
    existing = [path for path in predict_outputs(args) if os.path.exists(path)]
    if existing:
        sample = ", ".join(os.path.basename(p) for p in existing[:3])
        more = f" (+{len(existing) - 3})" if len(existing) > 3 else ""
        reasons.append(msg(
            f"--overwrite 将覆盖 {len(existing)} 个已存在的输出: {sample}{more}",
            f"--overwrite will replace {len(existing)} existing output file(s): {sample}{more}"))
    return reasons
