"""加载并校验 mockd 配置。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VALID_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "*"}
)
_ALLOWED_KEYS = frozenset({"method", "path", "status", "headers", "body", "delay_ms"})


class ConfigError(ValueError):
    """配置无法解析或校验失败。"""


@dataclass(frozen=True)
class Route:
    path: str
    method: str = "GET"
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    delay_ms: int = 0

    def matches(self, method: str, path: str) -> bool:
        """方法匹配（`*` 通配）且路径匹配（结尾 `*` 表示前缀）。"""
        if self.method != "*" and self.method != method:
            return False
        if self.path.endswith("*"):
            return path.startswith(self.path[:-1])
        return self.path == path


def _parse_route(item: object, index: int, source: str) -> Route:
    where = f"{source}: routes[{index}]"
    if not isinstance(item, dict):
        raise ConfigError(f"{where}: 必须是对象")

    unknown = set(item) - _ALLOWED_KEYS
    if unknown:
        raise ConfigError(f"{where}: 未知字段 {', '.join(sorted(unknown))}")

    path = item.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ConfigError(f"{where}: path 必须是 / 开头的字符串")
    if "?" in path:
        raise ConfigError(f"{where}: path 不要包含查询串，匹配时会忽略查询串")

    method = item.get("method", "GET")
    if not isinstance(method, str) or method.upper() not in VALID_METHODS:
        allowed = ", ".join(sorted(VALID_METHODS))
        raise ConfigError(f"{where}: method 必须是 {allowed} 之一")
    method = method.upper()

    status = item.get("status", 200)
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        raise ConfigError(f"{where}: status 必须是 100-599 的整数")

    headers = item.get("headers", {})
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in headers.items()
    ):
        raise ConfigError(f"{where}: headers 必须是字符串到字符串的对象")

    body = item.get("body", "")
    if not isinstance(body, str):
        raise ConfigError(f"{where}: body 必须是字符串")

    delay_ms = item.get("delay_ms", 0)
    if isinstance(delay_ms, bool) or not isinstance(delay_ms, int) or delay_ms < 0:
        raise ConfigError(f"{where}: delay_ms 必须是非负整数")

    return Route(path, method, status, dict(headers), body, delay_ms)


def load_config(path: str | Path) -> list[Route]:
    """读取 JSON 配置，返回按声明顺序排列的路由。"""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"无法读取 {path}: {exc.strerror or exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{p}:{exc.lineno}: JSON 解析失败：{exc.msg}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{p}: 顶层必须是对象")
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ConfigError(f"{p}: routes 必须是非空数组")

    return [_parse_route(item, index, str(p)) for index, item in enumerate(routes)]
