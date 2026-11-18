"""interpolate 子命令：光流法补帧（minterpolate）。
interpolate subcommand: frame interpolation with motion compensation (minterpolate).
"""
import os
import sys

from ..core import has_audio, run
from .. import validate as V


def _build_minterpolate_filter(target_fps, quality="balanced"):
    """按质量档位拼 minterpolate 滤镜。
    Build the minterpolate filter for the requested quality tier.

    quality:
      fast     -> 快速/低质量（适合预览）/ fast, low quality (good for previews)
      balanced -> 默认 / default
      quality  -> 慢，但边缘更干净 / slow but cleaner edges
    """
    base = f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc"
    base += ":me_mode=bilat:scd=fdiff"
    if quality == "fast":
        base += ":me=epzs:vsbmc=0:search_param=16"
    elif quality == "quality":
        base += ":me=umh:vsbmc=1:search_param=32"
    else:  # balanced
        base += ":me=epzs:vsbmc=1:search_param=32"
    base += ",setsar=1"
    return base


def cmd_interpolate(args):
    try:
        src = V.check_input_file(args.path, V.VIDEO_SUFFIXES)
        fps = V.parse_float(str(args.fps), "帧率", "frame rate", V.MIN_FPS, V.MAX_FPS)
    except V.ValidationError as e:
        print(f"错误 / error: {e}", file=sys.stderr)
        return 1
    if fps <= 0:
        print("错误 / error: 目标帧率必须 > 0 / the target frame rate must be > 0",
              file=sys.stderr)
        return 1
    if args.quality not in ("fast", "balanced", "quality"):
        print(f"错误 / error: 未知质量档位 / unknown quality tier: {args.quality}",
              file=sys.stderr)
        return 1

    base = os.path.splitext(src)[0]
    out = args.output or f"{base}_{fps:g}fps.mp4"
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

    vf = _build_minterpolate_filter(f"{fps:g}", args.quality)
    print(f"[补帧 / interpolate] {src} -> {fps:g} fps  [{args.quality}]")

    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-crf", str(args.crf),
           "-preset", args.preset, "-pix_fmt", "yuv420p",
           "-metadata:s:v:0", "rotate=0"]

    if getattr(args, "no_audio", False) or not has_audio(src):
        cmd += ["-an"]
    else:
        # 补帧不改变时长，音频直接复制 / duration is unchanged, so copy audio as-is
        cmd += ["-c:a", "copy"]

    cmd.append(out)
    run(cmd)
    print(f"✓ 输出 / output: {out}")
    return 0
