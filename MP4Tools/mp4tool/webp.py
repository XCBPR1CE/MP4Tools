"""WebP → MP4 转换（不依赖 ffmpeg）。
WebP → MP4 conversion (does not require ffmpeg).
"""
import os


def webp_to_mp4(input_path, output_path, fps=30, static_duration=3.0):
    """静态 WebP 生成固定时长视频，动画 WebP 按帧数转视频。
    A static WebP becomes a fixed-duration clip; an animated WebP is converted
    frame by frame."""
    try:
        from PIL import Image
        import numpy as np
        import imageio
    except ImportError as e:
        raise RuntimeError(
            f"缺少依赖: {e}\n请安装: pip install pillow imageio numpy\n"
            f"missing dependency: {e}\ninstall with: pip install pillow imageio numpy") from e

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"找不到文件 / file not found: {input_path}")

    with Image.open(input_path) as img:
        if getattr(img, "is_animated", False):
            frames = []
            for i in range(img.n_frames):
                img.seek(i)
                frame = img.convert("RGB")
                w, h = frame.size
                if w % 2 or h % 2:  # yuv420p 需要偶数尺寸 / yuv420p needs even sizes
                    frame = frame.crop((0, 0, w - (w % 2), h - (h % 2)))
                frames.append(np.array(frame))
            print(f"  动画 WebP / animated WebP: {len(frames)} 帧 / frames → {fps}fps")
        else:
            frame = img.convert("RGB")
            w, h = frame.size
            if w % 2 or h % 2:
                frame = frame.crop((0, 0, w - (w % 2), h - (h % 2)))
            arr = np.array(frame)
            frames = [arr] * int(static_duration * fps)
            print(f"  静态 WebP / static WebP → {static_duration}s @ {fps}fps")

    writer = imageio.get_writer(
        output_path, fps=fps, codec="libx264",
        pixelformat="yuv420p", macro_block_size=1)
    try:
        for f in frames:
            writer.append_data(f)
    finally:
        writer.close()
    print(f"  ✓ 输出 / output: {output_path}")
