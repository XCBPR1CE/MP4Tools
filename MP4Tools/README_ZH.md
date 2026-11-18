# MP4Tools —— mp4 通用处理脚本

> English version: [README_EN.md](README_EN.md)

MP4Tools 是一个基于 ffmpeg / ffprobe 的视频处理小工具，提供**命令行**与**交互式菜单**两种用法。
它把常用的几类操作收进一个入口：WebP 转 MP4、调分辨率、变速、光流补帧、音轨提取 / 移除 / 合并、查看媒体信息。

源码中所有中文注释与提示都**紧邻英文译文**，输出形如 `中文 / English`，因此中英文用户读同一份代码、看同一种日志。

---

## 1. 目录结构

```
MP4Tools/
├── README_ZH.md               # 中文说明文档（本文件）
├── README_EN.md               # English documentation
├── mp4tool.py                 # 命令行入口（转发到 mp4tool 包）
└── mp4tool/
    ├── __init__.py            # 包信息与版本号
    ├── __main__.py            # python -m mp4tool 入口
    ├── utils.py               # 分辨率解析、mp4 文件收集
    ├── core.py                # ffmpeg / ffprobe 封装、滤镜拼装
    ├── webp.py                # WebP → MP4（不依赖 ffmpeg）
    ├── cli.py                 # argparse 构建、分发、交互入口
    ├── interact.py            # 交互式菜单与各功能参数向导
    ├── validate.py            # 输入校验：语法 / 越界 / 危险操作
    └── ops/
        ├── __init__.py        # 统一导出 cmd_* 函数
        ├── ops_webp.py        # webp 子命令
        ├── ops_resize.py      # resize 子命令
        ├── ops_speed.py       # speed 子命令
        ├── ops_interpolate.py # interpolate 子命令
        ├── ops_audio.py       # audio 子命令（extract / remove / mux）
        ├── ops_info.py        # info 子命令
        └── ops_help.py        # help 子命令
```

模块之间是单向依赖，不存在循环导入：

```
mp4tool.py → cli.py → ops/* → core.py → utils.py → validate.py
                ↓
           interact.py（仅在函数内部延迟导入 cli.py）
```

---

## 2. 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.8 及以上（未使用 3.9+ 语法） |
| ffmpeg / ffprobe | 需要加入 `PATH`；`webp` 与 `help` 子命令不需要 |
| 可选依赖 | `pillow`、`imageio`、`numpy` —— 仅 `webp` 子命令需要 |

安装可选依赖：

```bash
pip install pillow imageio numpy
```

缺失依赖时 `webp` 子命令会给出明确提示，而不是抛栈：

```
缺少依赖: No module named 'imageio'
请安装: pip install pillow imageio numpy
```

---

## 3. 快速开始

```bash
python mp4tool.py                  # 进入交互式菜单
python mp4tool.py --help           # 查看全部子命令
python -m mp4tool                  # 等价写法
python mp4tool.py help resize      # 查看某个子命令的详细帮助
```

`python mp4tool.py` 可以在任意工作目录下运行，脚本会自动把自身目录加入 `sys.path`。

---

## 4. 子命令详解

### 4.1 `webp` —— WebP 转 MP4

把静态或动画 WebP 转成 H.264 MP4，**不依赖 ffmpeg**（走 imageio）。

```bash
python mp4tool.py webp msk.webp
python mp4tool.py webp msk.webp -o out.mp4 --fps 60
python mp4tool.py webp logo.webp --duration 5
```

| 参数 | 说明 | 校验 |
| --- | --- | --- |
| `input` | 输入 WebP 文件 | 必须存在，扩展名必须是 `.webp` |
| `-o, --output` | 输出 MP4 路径（默认与输入同名 `.mp4`） | 必须是 `.mp4`，不能与输入相同 |
| `--fps` | 帧率，默认 30 | 整数，1~240 |
| `--duration` | 静态 WebP 生成视频的时长/秒，默认 3 | 0.1~600 |

**注意**：静态 WebP 会按 `--duration × --fps` 生成固定帧数的静态视频；动画 WebP 按原帧数转码，`--duration` 对它无效。
本子命令**没有** `--overwrite` 开关；交互模式下若目标已存在，会先询问是否覆盖。

### 4.2 `resize` —— 调整分辨率

```bash
python mp4tool.py resize input.mp4 -s 1920x1080
python mp4tool.py resize ./videos -s 1280x720 --keep-ratio -r
python mp4tool.py resize input.mp4 -s 1920x1080 --crop --crf 20
python mp4tool.py resize ./videos -s 1280x720 --filter "^IMG_" -r
```

三种缩放模式（互斥）：

| 模式 | 效果 |
| --- | --- |
| 默认 | 强制拉伸到目标尺寸 |
| `--keep-ratio` | 保持比例缩小/放大，不足处补黑边 |
| `--crop` | 保持比例放大到覆盖目标尺寸，再居中裁剪 |

| 参数 | 说明 | 校验 |
| --- | --- | --- |
| `path` | 输入文件或目录（默认当前目录） | 必须存在；文件模式要求是视频后缀 |
| `-s, --size` | 目标分辨率 `WxH`，省略则交互输入 | 每边 16~16384，奇数自动向下取偶 |
| `-o, --output` | 仅单文件模式生效 | 必须是 `.mp4`，不能与输入相同 |
| `-r, --recursive` | 递归子目录 | — |
| `--filter` | 只处理文件名匹配该正则的 mp4 | 正则在解析阶段就被编译，写错立即报语法错误 |
| `--crf` / `--preset` / `--audio-bitrate` | 编码质量 | CRF 0~51，码率形如 `192k`（8~1024） |
| `--overwrite` | 覆盖已存在的输出 | 批量覆盖时会二次确认 |

目录模式会**跳过**本工具自己产出的文件（形如 `名字_1280x720.mp4`），避免重复处理。

### 4.3 `speed` —— 变速（音视频同步）

```bash
python mp4tool.py speed input.mp4 -f 2.0
python mp4tool.py speed input.mp4 -f 0.5 -o slow.mp4
```

视频用 `setpts=PTS/factor`，音频用 `atempo` 链同步变速。`atempo` 单段只支持 0.5~2.0，
因此 4 倍速这类极端值会被自动拆成多段（如 `atempo=2.0,atempo=2.0`）。

| 参数 | 说明 | 校验 |
| --- | --- | --- |
| `path` | 输入视频 | 必须存在，视频后缀 |
| `-f, --factor` | 速度倍数，省略则交互输入 | 0.01~100 |
| `-o, --output` | 输出路径（默认 `<原名>_x<倍数>.mp4`） | 不能与输入相同 |

### 4.4 `interpolate` —— 光流法补帧

```bash
python mp4tool.py interpolate input.mp4 --fps 60
python mp4tool.py interpolate input.mp4 --fps 60 --quality fast
python mp4tool.py interpolate input.mp4 --fps 120 --quality quality
```

| 参数 | 说明 | 校验 |
| --- | --- | --- |
| `path` | 输入视频 | 必须存在，视频后缀 |
| `--fps` | 目标帧率，必填，支持 `60`、`59.94`、`60000/1001` | 1~240 |
| `-o, --output` | 输出路径（默认 `<原名>_<fps>fps.mp4`） | 不能与输入相同 |
| `--quality` | `fast` / `balanced`（默认）/ `quality` | 只能是这三档 |
| `--no-audio` | 丢弃音轨 | — |

补帧不改变时长，音频默认原样复制。CPU 开销很大，建议先用短片段 + `--quality fast` 试效果。

### 4.5 `audio` —— 音轨操作

```bash
python mp4tool.py audio extract input.mp4              # 无损提取为 .mka
python mp4tool.py audio extract input.mp4 -o audio.mka
python mp4tool.py audio remove input.mp4               # 丢掉音轨，视频流复制
python mp4tool.py audio mux silent.mp4 -a audio.mka -o final.mp4
```

| 动作 | 输出默认名 | 说明 |
| --- | --- | --- |
| `extract` | `<原名>.mka` | `-vn -c:a copy`，不重编码 |
| `remove` | `<原名>_noaudio.mp4` | `-an -c:v copy`，不重编码 |
| `mux` | `<原名>_muxed.mp4` | `-map 0:v:0 -map 1:a:0`，**替换**原音轨；先尝试 `-c:a copy`，失败自动回退 AAC |

`mux` 的 `-a/--audio-file` 必填，扩展名必须是常见音频格式。
三个动作都通过 `ffmpeg -y` 执行，交互模式会先确认覆盖。

### 4.6 `info` —— 查看媒体信息

```bash
python mp4tool.py info input.mp4
python mp4tool.py info a.mp4 b.mkv c.mp3
python mp4tool.py info ./videos
```

打印格式、时长、大小、码率以及每条流的编码细节。传入目录时会递归扫描其中的媒体文件，
但**一次只允许一个目录**（多个目录会被拒绝并提示）。

### 4.7 `help` —— 帮助

```bash
python mp4tool.py help                  # 等价于 --help
python mp4tool.py help resize
python mp4tool.py help audio extract
```

---

## 5. 交互模式

不带任何参数运行 `python mp4tool.py` 即进入：

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

流程：**选菜单 → 逐项回答问题 → 执行前校验 → 执行 → 回车回到菜单**。
每个向导只负责拼出等价命令行（例如 `["speed", "a.mp4", "-f", "2"]`），真正的执行仍然走
`cli.main(argv) → argparse`，所以交互模式和命令行模式的规则完全一致。

交互模式下输入路径时：

* 可以直接把文件从资源管理器拖进终端，首尾引号与 Windows「复制为路径」带来的 `& ` 前缀会被自动去掉；
* 回车 = 使用默认值（输出路径、帧率、时长等），路径类问题回车 = 取消当前向导；
* `Ctrl+C` / `Ctrl+D` 中断向导只取消当前这一轮，不会退出程序；在主菜单按 `0` / `q` / `quit` / `exit` 退出。

---

## 6. 输入校验（重点）

交互模式的**每一步输入**都会经过 `mp4tool/validate.py` 校验一次；同一套校验规则也被
`cli.py` 的 argparse 类型转换器复用，因此命令行模式并不会绕过它。

### 6.1 语法错误

| 场景 | 输入 | 提示 |
| --- | --- | --- |
| 空值 | 直接回车（必填项） | `路径不能为空 / path must not be empty` |
| 非数字 | `abc` 填帧率 | `帧率必须是数字: 'abc' / frame rate must be a number: 'abc'` |
| 非整数 | `30.5` 填 webp 帧率 | `帧率必须是整数: '30.5' / frame rate must be an integer: '30.5'` |
| 分辨率写错 | `1920*1080p` | `分辨率格式错误: '1920*1080p'（应为 WxH，如 1920x1080） / invalid resolution format ...` |
| 正则写错 | `[a-z` 填 `--filter` | `文件名正则语法错误: '[a-z'（unterminated character set at position 0） / filename regex syntax error ...` |
| 码率写错 | `192` | `音频码率格式错误: '192'（应形如 192k） / invalid audio bitrate: '192' (expected e.g. 192k)` |
| 路径非法字符 | `D:\a<b.mp4` | `路径包含非法字符 '&lt;' / path contains illegal characters '<'` |
| 路径像选项 | `-rf` | `路径不能以 '-' 开头（会被 ffmpeg 当成命令行选项） / path must not start with '-' ...` |
| 路径过长 | 超过 240 字符 | `路径过长（... 字符 > 上限 240） / path too long ...` |
| 文件不存在 | `nope.mp4` | `文件不存在: nope.mp4 / file does not exist: nope.mp4` |
| 扩展名不符 | 用 `.png` 走 `webp` | `输入文件扩展名 .png 不受支持，只允许 .webp / input file extension .png is not supported ...` |

非数字/非整数用严格正则匹配，`1_000`、全角数字、十六进制这类“看着像数字”的写法都会被拒绝。

### 6.2 越界（数值范围）

| 字段 | 允许范围 | 越界提示示例 |
| --- | --- | --- |
| 分辨率宽 / 高 | 16 ~ 16384（偶数） | `宽度越界: 32768（允许 16~16384） / width out of range ...` |
| 帧率 | 1 ~ 240 | `帧率越界: 1000（允许 1~240） / frame rate out of range ...` |
| CRF | 0 ~ 51 | `CRF 越界: 60（允许 0~51） / CRF out of range ...` |
| 变速倍数 | 0.01 ~ 100 | `速度倍数越界: 0（允许 0.01~100） / speed factor out of range ...` |
| 静态时长 | 0.1 ~ 600 秒 | `静态时长越界: 1000（允许 0.1~600） ...` |
| 音频码率 | 8 ~ 1024 kbps | `音频码率越界: 4096（允许 8~1024） ...` |

分辨率输入奇数时会自动向下取偶并提示（`yuv420p` 要求偶数边长）：

```
提示 / note: 奇数边长已向下取偶 / odd sides floored to even → 1920x1080
```

### 6.3 危险操作

| 危险行为 | 处理方式 |
| --- | --- |
| 输出路径 = 输入路径 | **直接拒绝**：`输出路径与输入相同，会覆盖源文件 / output path equals the input ...` |
| 写入系统受保护目录（`C:\Windows`、`Program Files`、`/etc`、`/usr`、`/bin` 等） | **直接拒绝**：`拒绝写入受保护的系统目录 ...（危险操作）` |
| 输出目录不存在 / 不可写 | **直接拒绝**并给出具体目录 |
| 输出路径是个目录 | **直接拒绝** |
| 输出文件已存在 | 交互模式先问 `覆盖已有文件? / overwrite the existing file? [y/N]`，默认 `N` |
| `--overwrite` 会批量覆盖已有产物 | 执行前打印将覆盖的文件数量与样例，再要求二次确认（默认 `N`） |
| ffmpeg 参数注入（路径以 `-` 开头） | **直接拒绝**，见 6.1 |

所有危险判定都基于 `os.path.realpath` 规范化后的绝对路径比较，`a/../a` 这类写法逃不掉。

### 6.4 执行前的最后一道闸门

交互模式在真正调用 ffmpeg 前还会跑一次 `_preflight(argv)`：

1. **语法闸**：用 `build_parser()` 解析一遍拼好的 argv，参数写错就地拦下，不进入执行；
2. **范围闸**：`check_args_bounds()` 再核一遍 CRF、帧率、时长、倍数、码率、分辨率、正则；
3. **危险闸**：`danger_reasons()` 检测批量覆盖，需要二次确认。

任一闸门不通过都会回到菜单，不会留下半成品文件。

---

## 7. 输出命名规则

| 子命令 | 默认输出 | 示例 |
| --- | --- | --- |
| `webp` | `<原名>.mp4` | `msk.webp → msk.mp4` |
| `resize` | `<原名>_<宽>x<高>.mp4` | `a.mp4 → a_1920x1080.mp4` |
| `speed` | `<原名>_x<倍数>.mp4` | `a.mp4 → a_x2.mp4` |
| `interpolate` | `<原名>_<fps>fps.mp4` | `a.mp4 → a_60fps.mp4` |
| `audio extract` | `<原名>.mka` | `a.mp4 → a.mka` |
| `audio remove` | `<原名>_noaudio.mp4` | `a.mp4 → a_noaudio.mp4` |
| `audio mux` | `<原名>_muxed.mp4` | `a.mp4 → a_muxed.mp4` |

带 `_<宽>x<高>` 形态的文件会被 `resize` 的目录模式自动跳过，避免“处理过的文件再被处理一次”。

---

## 8. 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（批量处理中允许存在被跳过的文件） |
| `1` | 处理失败 / 校验失败 / 找不到 ffmpeg / 批量处理有失败项 |
| `2` | argparse 参数语法错误（未知子命令、缺少必填参数、类型转换失败） |
| `130` | 用户按下 `Ctrl+C` 取消 |

---

## 9. 常见问题

**Q：提示“未找到 ffprobe / ffmpeg”？**
把 ffmpeg 的 `bin` 目录加入 `PATH`，重开终端。`webp` 与 `help` 子命令不需要 ffmpeg。

**Q：Windows 下中文显示成问号？**
`cli.main()` 在 Windows 上会把标准输入/输出/错误强制重配为 UTF-8。若仍有问题，可先执行 `chcp 65001`。

**Q：`+ 请安装 pillow imageio numpy` 之后还是失败？**
确认安装到了当前解释器：`python -m pip install pillow imageio numpy`。

**Q：补帧特别慢？**
`minterpolate` 是纯 CPU 的帧间运动估计，1080p 60fps 以上会非常吃时间。先用 `--quality fast` 和短片段验证效果。

**Q：`resize` 目录模式什么都没处理？**
目录里只有本工具命名的产物（`xxx_1280x720.mp4`）会被刻意跳过；用 `-r` 递归，或换一个 `--filter`。

**Q：能否原地覆盖源文件？**
不能。交互模式与 `check_output_path()` 都会直接拒绝“输出 == 输入”，请输出到新文件名后自行替换。
