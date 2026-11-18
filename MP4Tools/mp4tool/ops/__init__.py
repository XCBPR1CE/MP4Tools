"""命令实现包：每个 ops_<cmd>.py 对应一个子命令。

Command implementation package: every ops_<cmd>.py maps to one subcommand.

统一从包名导出 cmd_* 函数，cli.py 只需 from .ops import ...
All cmd_* functions are re-exported here so cli.py only needs `from .ops import ...`
"""
from .ops_webp import cmd_webp
from .ops_resize import cmd_resize
from .ops_speed import cmd_speed
from .ops_audio import cmd_audio
from .ops_info import cmd_info
from .ops_help import cmd_help
from .ops_interpolate import cmd_interpolate

__all__ = [
    "cmd_webp",
    "cmd_resize",
    "cmd_speed",
    "cmd_audio",
    "cmd_info",
    "cmd_help",
    "cmd_interpolate",
]
