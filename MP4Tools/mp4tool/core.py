"""ffmpeg / ffprobe 封装与媒体处理核心。
Thin wrappers around ffmpeg / ffprobe plus the media-processing core.
"""
import json
import subprocess

from .utils import gcd


def check_tools(*tools):
    """检查外部命令是否存在，返回 (是否齐全, 第一个缺失的命令)。
    Check that external commands exist; return (all_found, first_missing)."""
    for tool in tools:
        try:
            subprocess.run([tool, "-version"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False, tool
    return True, None


def run(cmd, quiet=True):
    """执行命令，失败抛 CalledProcessError。
    Run a command; a failure raises CalledProcessError."""
    kwargs = {"check": True}
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    subprocess.run(cmd, **kwargs)


def get_video_info(filepath):
    """取第一条视频流的宽高、编码、帧率；没有视频流返回 None。
    Read size, codec and frame rate of the first video stream (None if absent)."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,codec_name,r_frame_rate",
           "-of", "json", filepath]
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace").stdout
    streams = json.loads(out).get("streams", [])
    if not streams:
        return None
    s = streams[0]
    return {"width": int(s.get("width", 0)),
            "height": int(s.get("height", 0)),
            "codec": s.get("codec_name"),
            "fps": s.get("r_frame_rate")}


def has_audio(filepath):
    """是否存在音频流 / whether the file contains an audio stream."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=index", "-of", "json", filepath]
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace").stdout
    return len(json.loads(out).get("streams", [])) > 0


def get_media_info(filepath):
    """完整的 format + stream 信息（json 解析后的 dict）。
    Full format + stream information (the parsed json dict)."""
    cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams",
           "-of", "json", filepath]
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace").stdout
    return json.loads(out)


def _build_scale_filter(tw, th, keep_ratio=False, crop=False):
    """拼缩放滤镜：强制拉伸 / 保持比例加黑边 / 保持比例裁剪填满。
    Build the scale filter: stretch, letterbox (keep ratio + pad) or crop-to-fill."""
    if crop:
        base = (f"scale={tw}:{th}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={tw}:{th}")
    elif keep_ratio:
        base = (f"scale={tw}:{th}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black")
    else:
        base = f"scale={tw}:{th}:flags=lanczos"
    # setsar=1 统一像素宽高比，避免播放器拉伸 / normalise SAR so players don't stretch
    return f"{base},setsar=1"


def _build_atempo_chain(speed):
    """atempo 每段必须在 [0.5, 2.0]，大倍速要拆成多段。
    Every atempo stage must stay within [0.5, 2.0], so extreme speeds are chained."""
    parts, remaining = [], speed
    if remaining > 1.0:
        while remaining > 2.0:
            parts.append("atempo=2.0")
            remaining /= 2.0
        parts.append(f"atempo={remaining:.4f}")
    elif remaining < 1.0:
        while remaining < 0.5:
            parts.append("atempo=0.5")
            remaining /= 0.5
        parts.append(f"atempo={remaining:.4f}")
    else:
        parts.append("atempo=1.0")
    return ",".join(parts)


def process_video(filepath, output_path, *,
                  size=None, keep_ratio=False, crop=False,
                  speed=None, audio_mode="keep",
                  crf=18, preset="medium", audio_bitrate="192k"):
    """组合处理：分辨率 + 变速 + 音频保留/移除。
    Combined processing: resize + speed change + keep/remove audio."""
    info = get_video_info(filepath)
    if info:
        g = gcd(info["width"], info["height"]) or 1
        print(f"  源分辨率 / source: {info['width']}x{info['height']} "
              f"({info['width'] // g}:{info['height'] // g})")
    if size:
        mode = "保持比例 / keep ratio" if keep_ratio else (
            "裁剪 / crop" if crop else "强制拉伸 / stretch")
        print(f"  目标 / target: {size[0]}x{size[1]} [{mode}]")
    if speed and abs(speed - 1.0) > 1e-9:
        print(f"  变速 / speed: {speed}x")

    vfilters, afilter = [], None
    if size:
        vfilters.append(_build_scale_filter(size[0], size[1],
                                            keep_ratio=keep_ratio, crop=crop))
    if speed and abs(speed - 1.0) > 1e-9:
        vfilters.append(f"setpts=PTS/{speed}")
        afilter = _build_atempo_chain(speed)

    audio_exist = has_audio(filepath)

    cmd = ["ffmpeg", "-y", "-i", filepath]
    if vfilters:
        cmd += ["-vf", ",".join(vfilters),
                "-c:v", "libx264", "-crf", str(crf),
                "-preset", preset, "-pix_fmt", "yuv420p",
                # 清掉旋转元数据，避免手机竖拍视频二次旋转
                # drop rotation metadata to avoid double rotation on phone videos
                "-metadata:s:v:0", "rotate=0"]
    else:
        cmd += ["-c:v", "copy"]

    if audio_mode == "remove" or not audio_exist:
        cmd += ["-an"]
    elif afilter:
        cmd += ["-c:a", "aac", "-b:a", audio_bitrate, "-af", afilter]
    else:
        cmd += ["-c:a", "copy"]

    cmd.append(output_path)
    run(cmd)
    return output_path
