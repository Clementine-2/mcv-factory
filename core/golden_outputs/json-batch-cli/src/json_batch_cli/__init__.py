from __future__ import annotations

import argparse

__version__ = "0.1.0"
PURPOSE = '做一个 Python 命令行工具，批量读取一个目录里的 JSON 并转换格式。不能覆盖原始文件。'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='json-batch-cli', description=PURPOSE)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    print("Project scaffold ready. Implement domain behavior through the coding-agent workflow.")
