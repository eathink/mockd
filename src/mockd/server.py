"""基于标准库的 mock HTTP 服务器。"""

from __future__ import annotations

import collections
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .config import Route

_DEFAULT_HEADERS = {"Content-Type": "text/plain; charset=utf-8"}
_MAX_BODY = 1024 * 1024  # 请求体最多读取 1 MiB
_RECORD_BODY_LIMIT = 4096  # 记录时每个请求体最多保留 4 KiB 字符
_REQUESTS_PATH = "/__requests"  # 保留路径，用于查看最近请求


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _make_handler(routes: list[Route], quiet: bool, max_requests: int):
    needs_body = any(route.body_contains is not None for route in routes)
    recording = max_requests > 0
    records: collections.deque[dict[str, object]] = (
        collections.deque(maxlen=max_requests) if recording else collections.deque()
    )
    records_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0 每个响应后关闭连接，避免未读取的请求体影响下一个请求。
        protocol_version = "HTTP/1.0"

        def _respond(self, status: int, headers: dict[str, str], body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            merged = dict(_DEFAULT_HEADERS)
            merged.update(headers)
            merged["Content-Length"] = str(len(payload))
            for name, value in merged.items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _read_body(self) -> str | None:
            """读取请求体；超限或长度非法时返回 None。"""
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return ""
            try:
                length = int(raw_length)
            except ValueError:
                return None
            if length <= 0:
                return ""
            if length > _MAX_BODY:
                return None
            return self.rfile.read(length).decode("utf-8", errors="replace")

        def _record(self, method: str, status: int, body: str | None) -> None:
            if not recording:
                return
            truncated = body is not None and len(body) > _RECORD_BODY_LIMIT
            entry = {
                "method": method,
                "path": self.path,
                "status": status,
                "body": None if body is None else body[:_RECORD_BODY_LIMIT],
                "body_truncated": truncated,
                "timestamp": _now(),
            }
            with records_lock:
                records.append(entry)

        def _send_requests(self) -> None:
            with records_lock:
                snapshot = list(records)
            payload = json.dumps(
                {
                    "count": len(snapshot),
                    "max": max_requests,
                    "requests": snapshot,
                },
                ensure_ascii=False,
            )
            self._respond(
                200,
                {"Content-Type": "application/json; charset=utf-8"},
                payload,
            )

        def _handle(self, method: str) -> None:
            path = urlsplit(self.path).path

            # 保留路径优先于用户路由，且自身不记入请求列表。
            if path == _REQUESTS_PATH and method in ("GET", "HEAD"):
                self._send_requests()
                if not quiet:
                    print(f"{method} {path} -> 200", flush=True)
                return

            body = self._read_body() if (needs_body or recording) else ""
            route = next(
                (
                    candidate
                    for candidate in routes
                    if candidate.matches(method, path, body)
                ),
                None,
            )
            if route is None:
                self._record(method, 404, body)
                error_body = json.dumps(
                    {"error": "no route", "method": method, "path": path},
                    ensure_ascii=False,
                )
                self._respond(
                    404,
                    {"Content-Type": "application/json; charset=utf-8"},
                    error_body,
                )
                if not quiet:
                    print(f"{method} {path} -> 404", flush=True)
                return

            if route.delay_ms:
                time.sleep(route.delay_ms / 1000)

            # 先记录再响应，避免客户端紧接着查 /__requests 时看漏这一条。
            self._record(method, route.status, body)
            self._respond(route.status, route.headers, route.body)
            if not quiet:
                print(f"{method} {path} -> {route.status}", flush=True)

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._handle("PUT")

        def do_PATCH(self) -> None:  # noqa: N802
            self._handle("PATCH")

        def do_DELETE(self) -> None:  # noqa: N802
            self._handle("DELETE")

        def do_HEAD(self) -> None:  # noqa: N802
            self._handle("HEAD")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._handle("OPTIONS")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    return Handler


class MockServer:
    """持有监听 socket，便于 CLI 与测试共用。"""

    def __init__(
        self,
        routes: list[Route],
        host: str = "127.0.0.1",
        port: int = 8080,
        quiet: bool = False,
        max_requests: int = 50,
    ) -> None:
        if max_requests < 0:
            raise ValueError("max_requests 必须是非负整数")
        self.routes = list(routes)
        self.quiet = quiet
        self.max_requests = max_requests
        self._httpd = ThreadingHTTPServer(
            (host, port), _make_handler(self.routes, quiet, max_requests)
        )
        self._httpd.daemon_threads = True

    @property
    def host(self) -> str:
        return self._httpd.server_address[0]

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
