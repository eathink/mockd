"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config import ConfigError, Route, load_config, parse_route
from .server import MockServer


def parse_cli_routes(specs: list[str]) -> list[Route]:
    """把 --route 的 JSON 字符串解析成路由，报错时指出序号。"""
    routes: list[Route] = []
    for index, spec in enumerate(specs, 1):
        try:
            data = json.loads(spec)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"--route #{index}: JSON 解析失败：{exc.msg}"
            ) from exc
        routes.append(parse_route(data, f"--route #{index}"))
    return routes


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
    parser.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="JSON",
        help='临时追加路由（JSON 对象，可重复）；优先于配置文件，例如 \'{"path":"/debug","body":"ok"}\'',
    )
    parser.add_argument("--quiet", action="store_true", help="不打印每条请求")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        routes = parse_cli_routes(args.route) + load_config(args.config)
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
