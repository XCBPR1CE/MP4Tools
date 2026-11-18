# MP4Tools — a general-purpose MP4 toolkit

> Chinese version: [README_ZH.md](README_ZH.md)

MP4Tools is a small video-processing tool built on ffmpeg / ffprobe. It ships both a **command-line
interface** and an **interactive menu**. It gathers the everyday operations behind one entry point:
WebP → MP4, resizing, speed change, optical-flow frame interpolation, audio track extraction /
removal / muxing, and media inspection.

Every Chinese comment and prompt in the source code is **immediately followed by its English
translation**, and output is shaped like `中文 / English`, so Chinese and English users read the same
code and the same log lines.

---

## 1. Project layout

```
MP4Tools/
├── README_ZH.md               # Chinese documentation
├── README_EN.md               # English documentation (this file)
├── mp4tool.py                 # CLI entry point (forwards to the mp4tool package)
└── mp4tool/
    ├── __init__.py            # package info and version
    ├── __main__.py            # python -m mp4tool entry point
    ├── utils.py               # resolution parsing, mp4 file collection
    ├── core.py                # ffmpeg / ffprobe wrappers, filter assembly
    ├── webp.py                # WebP → MP4 (no ffmpeg required)
    ├── cli.py                 # argparse builder, dispatch, interactive entry
    ├── interact.py            # interactive menu and per-feature parameter wizards
    ├── validate.py            # input validation: syntax / bounds / dangerous operations
    └── ops/
        ├── __init__.py        # re-exports the cmd_* functions
        ├── ops_webp.py        # webp subcommand
        ├── ops_resize.py      # resize subcommand
        ├── ops_speed.py       # speed subcommand
        ├── ops_interpolate.py # interpolate subcommand
        ├── ops_audio.py       # audio subcommand (extract / remove / mux)
        ├── ops_info.py        # info subcommand
        └── ops_help.py        # help subcommand
```

> Note: the original tree in `README.md` listed the interpolation implementation as
> `ops_interact.py`; the real file is `ops_interpolate.py`. This revision also adds `validate.py`
> and the two documentation files.

Modules depend on each other in one direction only — there is no circular import:

```
mp4tool.py → cli.py → ops/* → core.py → utils.py → validate.py
                ↓
           interact.py（lazily imports cli.py inside functions only）
```

---

## 2. Requirements

| Item | Requirement |
| --- | --- |
| Python | 3.8 or newer (no 3.9+ syntax is used) |
| ffmpeg / ffprobe | Must be on `PATH`; not needed by the `webp` and `help` subcommands |
| Optional deps | `pillow`, `imageio`, `numpy` — only the `webp` subcommand needs them |

Install the optional dependencies:

```bash
pip install pillow imageio numpy
```

When a dependency is missing the `webp` subcommand prints a clear hint instead of a traceback:

```
缺少依赖: No module named 'imageio'
请安装: pip install pillow imageio numpy
```

---

## 3. Quick start

```bash
python mp4tool.py                  # open the interactive menu
python mp4tool.py --help           # list every subcommand
python -m mp4tool                  # equivalent form
python mp4tool.py help resize      # detailed help for one subcommand
```

`python mp4tool.py` works from any working directory: the script prepends its own directory to
`sys.path`.

---

## 4. Subcommands

### 4.1 `webp` — WebP to MP4

Converts a still or animated WebP into an H.264 MP4 **without ffmpeg** (through imageio).

```bash
python mp4tool.py webp msk.webp
python mp4tool.py webp msk.webp -o out.mp4 --fps 60
python mp4tool.py webp logo.webp --duration 5
```

| Argument | Description | Validation |
| --- | --- | --- |
| `input` | Input WebP file | Must exist; the extension must be `.webp` |
| `-o, --output` | Output MP4 path (defaults to the input stem + `.mp4`) | Must be `.mp4`; must differ from the input |
| `--fps` | Frame rate, default 30 | Integer, 1–240 |
| `--duration` | Length of the generated video for a still WebP, in seconds; default 3 | 0.1–600 |

**Note**: a still WebP produces a fixed-frame-count video of `--duration × --fps` frames; an animated
WebP is transcoded frame by frame and `--duration` does not affect it.
This subcommand has **no** `--overwrite` switch; in interactive mode an existing target triggers an
overwrite question first.

### 4.2 `resize` — change the resolution

```bash
python mp4tool.py resize input.mp4 -s 1920x1080
python mp4tool.py resize ./videos -s 1280x720 --keep-ratio -r
python mp4tool.py resize input.mp4 -s 1920x1080 --crop --crf 20
python mp4tool.py resize ./videos -s 1280x720 --filter "^IMG_" -r
```

Three mutually exclusive scaling modes:

| Mode | Effect |
| --- | --- |
| default | stretch to the target size |
| `--keep-ratio` | scale while preserving the aspect ratio, pad the remainder with black bars |
| `--crop` | scale to cover the target size while preserving the ratio, then center-crop |

| Argument | Description | Validation |
| --- | --- | --- |
| `path` | Input file or directory (default: current directory) | Must exist; file mode requires a video extension |
| `-s, --size` | Target resolution `WxH`; prompted for when omitted | Each side 16–16384; odd sides are floored to even |
| `-o, --output` | Used only in single-file mode | Must be `.mp4`; must differ from the input |
| `-r, --recursive` | Recurse into subdirectories | — |
| `--filter` | Only process mp4 files whose name matches the regex | The regex is compiled during parsing, so a syntax error fails immediately |
| `--crf` / `--preset` / `--audio-bitrate` | Encoding quality | CRF 0–51; bitrate looks like `192k` (8–1024) |
| `--overwrite` | Overwrite existing outputs | A batch overwrite asks for confirmation |

Directory mode **skips** files this tool produced itself (named `name_1280x720.mp4`), so nothing is
processed twice.

### 4.3 `speed` — change playback speed (video and audio in sync)

```bash
python mp4tool.py speed input.mp4 -f 2.0
python mp4tool.py speed input.mp4 -f 0.5 -o slow.mp4
```

Video uses `setpts=PTS/factor`; audio is changed in sync through a chain of `atempo` filters. A single
`atempo` stage only supports 0.5–2.0, so extreme values such as 4× are split into several stages
(e.g. `atempo=2.0,atempo=2.0`).

| Argument | Description | Validation |
| --- | --- | --- |
| `path` | Input video | Must exist and have a video extension |
| `-f, --factor` | Speed multiplier; prompted for when omitted | 0.01–100 |
| `-o, --output` | Output path (default `<stem>_x<factor>.mp4`) | Must differ from the input |

### 4.4 `interpolate` — optical-flow frame interpolation

```bash
python mp4tool.py interpolate input.mp4 --fps 60
python mp4tool.py interpolate input.mp4 --fps 60 --quality fast
python mp4tool.py interpolate input.mp4 --fps 120 --quality quality
```

| Argument | Description | Validation |
| --- | --- | --- |
| `path` | Input video | Must exist and have a video extension |
| `--fps` | Target frame rate, required; accepts `60`, `59.94`, `60000/1001` | 1–240 |
| `-o, --output` | Output path (default `<stem>_<fps>fps.mp4`) | Must differ from the input |
| `--quality` | `fast` / `balanced` (default) / `quality` | Only these three values |
| `--no-audio` | Drop the audio track | — |

Interpolation does not change the duration; the audio stream is copied as is. It is CPU intensive —
try a short clip with `--quality fast` first.

### 4.5 `audio` — audio-track operations

```bash
python mp4tool.py audio extract input.mp4              # lossless extraction to .mka
python mp4tool.py audio extract input.mp4 -o audio.mka
python mp4tool.py audio remove input.mp4               # drop audio, copy the video stream
python mp4tool.py audio mux silent.mp4 -a audio.mka -o final.mp4
```

| Action | Default output name | Description |
| --- | --- | --- |
| `extract` | `<stem>.mka` | `-vn -c:a copy`, no re-encoding |
| `remove` | `<stem>_noaudio.mp4` | `-an -c:v copy`, no re-encoding |
| `mux` | `<stem>_muxed.mp4` | `-map 0:v:0 -map 1:a:0`, **replaces** the original audio; tries `-c:a copy` first and falls back to AAC |

`mux` requires `-a/--audio-file`, whose extension must be a common audio format.
All three actions run through `ffmpeg -y`; interactive mode confirms the overwrite first.

### 4.6 `info` — show media information

```bash
python mp4tool.py info input.mp4
python mp4tool.py info a.mp4 b.mkv c.mp3
python mp4tool.py info ./videos
```

Prints the container, duration, size, bitrate and the codec details of every stream. A directory is
scanned recursively for media files, but **only one directory** is accepted at a time (more than one
is rejected with a hint).

### 4.7 `help` — help

```bash
python mp4tool.py help                  # same as --help
python mp4tool.py help resize
python mp4tool.py help audio extract
```

---

## 5. Interactive mode

Run `python mp4tool.py` with no arguments:

```
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
============================================================
```

Flow: **choose a menu entry → answer each question → pre-execution validation → run → press Enter to
return to the menu**. Each wizard only assembles the equivalent command line (for example
`["speed", "a.mp4", "-f", "2"]`); execution still goes through `cli.main(argv) → argparse`, so the
interactive and command-line modes share exactly the same rules.

When a wizard asks for a path:

* you can drag a file from Explorer into the terminal — surrounding quotes and the `& ` prefix that
  Windows adds to "Copy as path" are stripped automatically;
* Enter accepts the default value (output path, frame rate, duration, …); for a path question Enter
  cancels the current wizard;
* `Ctrl+C` / `Ctrl+D` while a wizard runs only cancels that round, it does not quit; from the main
  menu, `0` / `q` / `quit` / `exit` quits.

---

## 6. Input validation (the important part)

**Every single input** in interactive mode is validated by `mp4tool/validate.py`; the same rules are
reused by the argparse type converters in `cli.py`, so the command-line mode cannot bypass them.

### 6.1 Syntax errors

| Situation | Input | Message |
| --- | --- | --- |
| empty value | Enter on a required field | `路径不能为空 / path must not be empty` |
| not a number | `abc` for a frame rate | `帧率必须是数字: 'abc' / frame rate must be a number: 'abc'` |
| not an integer | `30.5` for the webp frame rate | `帧率必须是整数: '30.5' / frame rate must be an integer: '30.5'` |
| malformed resolution | `1920*1080p` | `分辨率格式错误: '1920*1080p'（应为 WxH，如 1920x1080） / invalid resolution format ...` |
| malformed regex | `[a-z` for `--filter` | `文件名正则语法错误: '[a-z'（unterminated character set at position 0） / filename regex syntax error ...` |
| malformed bitrate | `192` | `音频码率格式错误: '192'（应形如 192k） / invalid audio bitrate: '192' (expected e.g. 192k)` |
| illegal path character | `D:\a<b.mp4` | `路径包含非法字符 '<' / path contains illegal characters '<'` |
| option-looking path | `-rf` | `路径不能以 '-' 开头（会被 ffmpeg 当成命令行选项） / path must not start with '-' ...` |
| over-long path | more than 240 characters | `路径过长（... 字符 > 上限 240） / path too long ...` |
| missing file | `nope.mp4` | `文件不存在: nope.mp4 / file does not exist: nope.mp4` |
| wrong extension | `.png` given to `webp` | `输入文件扩展名 .png 不受支持，只允许 .webp / input file extension .png is not supported ...` |

Number parsing is strict: `1_000`, full-width digits and hexadecimal notations that merely *look*
numeric are rejected.

### 6.2 Out-of-range values

| Field | Allowed range | Example out-of-range message |
| --- | --- | --- |
| resolution width / height | 16–16384 (even) | `宽度越界: 32768（允许 16~16384） / width out of range ...` |
| frame rate | 1–240 | `帧率越界: 1000（允许 1~240） / frame rate out of range ...` |
| CRF | 0–51 | `CRF 越界: 60（允许 0~51） / CRF out of range ...` |
| speed factor | 0.01–100 | `速度倍数越界: 0（允许 0.01~100） / speed factor out of range ...` |
| still-image duration | 0.1–600 s | `静态时长越界: 1000（允许 0.1~600） ...` |
| audio bitrate | 8–1024 kbps | `音频码率越界: 4096（允许 8~1024） ...` |

An odd resolution side is floored to even with a note (`yuv420p` requires even sides):

```
提示 / note: 奇数边长已向下取偶 / odd sides floored to even → 1920x1080
```

### 6.3 Dangerous operations

| Dangerous behaviour | Handling |
| --- | --- |
| output path == input path | **rejected outright**: `输出路径与输入相同，会覆盖源文件 / output path equals the input ...` |
| writing into a protected system directory (`C:\Windows`, `Program Files`, `/etc`, `/usr`, `/bin`, …) | **rejected outright**: `拒绝写入受保护的系统目录 ...（危险操作）` |
| output directory missing or not writable | **rejected outright**, naming the directory |
| output path is a directory | **rejected outright** |
| output file already exists | interactive mode asks `覆盖已有文件? / overwrite the existing file? [y/N]`, default `N` |
| `--overwrite` would overwrite a batch of existing outputs | prints the count and a sample before asking for a second confirmation (default `N`) |
| ffmpeg argument injection (a path starting with `-`) | **rejected outright**, see 6.1 |

All danger checks compare absolute paths normalised through `os.path.realpath`, so a spelling such as
`a/../a` cannot slip through.

### 6.4 The final gate before execution

Immediately before invoking ffmpeg, interactive mode runs `_preflight(argv)`:

1. **syntax gate** — parse the assembled argv with `build_parser()`; a malformed option is caught in
   place and never reaches execution;
2. **bounds gate** — `check_args_bounds()` re-checks CRF, frame rate, duration, factor, bitrate,
   resolution and regex;
3. **danger gate** — `danger_reasons()` detects batch overwrites and asks for confirmation.

If any gate fails the flow returns to the menu without leaving half-written files behind.

---

## 7. Output naming

| Subcommand | Default output | Example |
| --- | --- | --- |
| `webp` | `<stem>.mp4` | `msk.webp → msk.mp4` |
| `resize` | `<stem>_<w>x<h>.mp4` | `a.mp4 → a_1920x1080.mp4` |
| `speed` | `<stem>_x<factor>.mp4` | `a.mp4 → a_x2.mp4` |
| `interpolate` | `<stem>_<fps>fps.mp4` | `a.mp4 → a_60fps.mp4` |
| `audio extract` | `<stem>.mka` | `a.mp4 → a.mka` |
| `audio remove` | `<stem>_noaudio.mp4` | `a.mp4 → a_noaudio.mp4` |
| `audio mux` | `<stem>_muxed.mp4` | `a.mp4 → a_muxed.mp4` |

Files shaped like `_<w>x<h>` are skipped automatically by `resize` directory mode, so an already
processed file is not processed again.

---

## 8. Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | success (a batch may still contain skipped files) |
| `1` | processing failure / validation failure / ffmpeg missing / a batch item failed |
| `2` | argparse syntax error (unknown subcommand, missing required argument, type conversion failure) |
| `130` | cancelled with `Ctrl+C` |

---

## 9. FAQ

**Q: It says ffprobe / ffmpeg was not found.**
Add ffmpeg's `bin` directory to `PATH` and reopen the terminal. The `webp` and `help` subcommands do
not need ffmpeg.

**Q: Chinese characters turn into question marks on Windows.**
`cli.main()` forces stdin/stdout/stderr to UTF-8 on Windows. If problems remain, run `chcp 65001`
first.

**Q: Still failing after `+ 请安装 pillow imageio numpy`.**
Make sure the packages are installed for the interpreter you run: `python -m pip install pillow imageio numpy`.

**Q: Interpolation is extremely slow.**
`minterpolate` performs pure-CPU motion estimation between frames; 1080p at 60 fps and above takes a
long time. Validate the result on a short clip with `--quality fast` first.

**Q: `resize` directory mode processed nothing.**
Only files this tool named itself (`xxx_1280x720.mp4`) are deliberately skipped; add `-r` to recurse,
or pass a different `--filter`.

**Q: Can it overwrite the source file in place?**
No. Both interactive mode and `check_output_path()` reject "output == input" outright; write to a new
file name and replace the source yourself.
