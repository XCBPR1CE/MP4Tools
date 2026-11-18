"""help 子命令：按路径查询子命令帮助。
help subcommand: look a subcommand up by its path and print its help.
"""
import sys


def cmd_help(args):
    parser = getattr(args, "_parser", None)
    subs = getattr(args, "_subs", None)
    if parser is None:
        print("帮助信息不可用 / help is unavailable", file=sys.stderr)
        return 1
    if not args.topic:
        parser.print_help()
        return 0
    key = " ".join(args.topic)
    if key in subs:
        subs[key].print_help()
        return 0
    print(f"未知子命令 / unknown subcommand: {key}", file=sys.stderr)
    print("可用子命令 / available subcommands: " + ", ".join(sorted(subs)),
          file=sys.stderr)
    return 1
