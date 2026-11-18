"""audio 子命令：音轨 extract / remove / mux。
audio subcommand: extract / remove / mux audio tracks.
"""
import os
import subprocess
import sys

from ..core import has_audio, run
from .. import validate as V


def _fail(message):
    print(f"错误 / error: {message}", file=sys.stderr)
    return 1


def cmd_audio(args):
    try:
        fp = V.check_input_file(args.input, V.VIDEO_SUFFIXES)
    except V.ValidationError as e:
        return _fail(e)

    if args.action == "extract":
        if not has_audio(fp):
            print("该文件没有音轨 / this file has no audio track", file=sys.stderr)
            return 1
        out = args.output or os.path.splitext(fp)[0] + ".mka"
        try:
            out = V.check_output_path(out, source=fp, suffixes=V.OUT_MKA_SUFFIXES,
                                      overwrite=True)
        except V.ValidationError as e:
            return _fail(e)
        run(["ffmpeg", "-y", "-i", fp, "-vn", "-c:a", "copy", out])
        print(f"✓ 音轨已提取 / audio extracted: {out}")

    elif args.action == "remove":
        out = args.output or os.path.splitext(fp)[0] + "_noaudio.mp4"
        try:
            out = V.check_output_path(out, source=fp, suffixes=V.OUT_MP4_SUFFIXES,
                                      overwrite=True)
        except V.ValidationError as e:
            return _fail(e)
        run(["ffmpeg", "-y", "-i", fp, "-an", "-c:v", "copy", out])
        print(f"✓ 已移除音轨 / audio removed: {out}")

    elif args.action == "mux":
        audio_file = getattr(args, "audio_file", None)
        if not audio_file:
            return _fail("必须指定外部音频文件 / an external audio file is required (-a/--audio-file)")
        try:
            audio_file = V.check_input_file(audio_file, V.AUDIO_SUFFIXES)
            bitrate = V.check_bitrate(args.audio_bitrate)
        except V.ValidationError as e:
            return _fail(e)
        out = args.output or os.path.splitext(fp)[0] + "_muxed.mp4"
        try:
            out = V.check_output_path(out, source=fp, suffixes=V.OUT_MP4_SUFFIXES,
                                      overwrite=True)
        except V.ValidationError as e:
            return _fail(e)
        try:
            # 先尝试流复制，失败再转 AAC / try stream copy first, fall back to AAC
            run(["ffmpeg", "-y", "-i", fp, "-i", audio_file,
                 "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-c:a", "copy", "-shortest", out])
        except subprocess.CalledProcessError:
            print("  ! 直接封装失败，改用 AAC 转码 / stream copy failed, "
                  "re-encoding to AAC instead...")
            run(["ffmpeg", "-y", "-i", fp, "-i", audio_file,
                 "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-c:a", "aac",
                 "-b:a", bitrate, "-shortest", out])
        print(f"✓ 已合并音视频 / audio muxed: {out}")
    return 0
