"""基于标准库的 mock HTTP 服务器。"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .config import Route

_DEFAULT_HEADERS = {"Content-Type": "text/plain; charset=utf-8"}


def _make_handler(routes: list[Route], quiet: bool):
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

        def _handle(self, method: str) -> None:
            path = urlsplit(self.path).path
            route = next(
                (candidate for candidate in routes if candidate.matches(method, path)),
                None,
            )
            if route is None:
                body = json.dumps(
                    {"error": "no route", "method": method, "path": path},
                    ensure_ascii=False,
                )
                self._respond(
                    404,
                    {"Content-Type": "application/json; charset=utf-8"},
                    body,
                )
                if not quiet:
                    print(f"{method} {path} -> 404", flush=True)
                return

            if route.delay_ms:
                time.sleep(route.delay_ms / 1000)

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
    ) -> None:
        self.routes = list(routes)
        self.quiet = quiet
        self._httpd = ThreadingHTTPServer(
            (host, port), _make_handler(self.routes, quiet)
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
