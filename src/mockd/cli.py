"""命令行入口。"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import ConfigError, load_config
from .server import MockServer


def _non_negative_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("必须是非负整数")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mockd",
        description="用 JSON 配置快速起一个 mock HTTP 服务。",
    )
    parser.add_argument("config", help="配置文件路径")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument(
        "--port", type=int, default=8080, help="监听端口（默认 8080，0 表示随机）"
    )
    parser.add_argument(
        "--max-requests",
        type=_non_negative_int,
        default=50,
        metavar="N",
        help="保留最近 N 条请求供 /__requests 查看（默认 50，0 表示关闭）",
    )
    parser.add_argument("--quiet", action="store_true", help="不打印每条请求")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        routes = load_config(args.config)
    except ConfigError as exc:
        print(f"mockd: {exc}", file=sys.stderr)
        return 2

    try:
        server = MockServer(routes, args.host, args.port, args.quiet, args.max_requests)
    except OSError as exc:
        print(f"mockd: 无法监听 {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2

    print(f"mockd 监听 {server.base_url}（{len(routes)} 条路由）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
