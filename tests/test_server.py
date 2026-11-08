import threading
import time
import unittest
import urllib.error
import urllib.request

from mockd.config import Route
from mockd.server import MockServer


class ServerTests(unittest.TestCase):
    def start(self, routes):
        server = MockServer(routes, port=0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._shutdown, server, thread)
        return server

    @staticmethod
    def _shutdown(server, thread):
        server.stop()
        thread.join(timeout=5)

    def request(self, url, method="GET", data=None):
        request = urllib.request.Request(url, data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers), response.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read().decode()

    def test_get_with_custom_headers(self):
        server = self.start(
            [
                Route(
                    "/health",
                    body='{"ok": true}',
                    headers={"Content-Type": "application/json"},
                )
            ]
        )

        status, headers, body = self.request(server.base_url + "/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, '{"ok": true}')
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_unknown_route_returns_404_json(self):
        server = self.start([Route("/known")])

        status, headers, body = self.request(server.base_url + "/missing")

        self.assertEqual(status, 404)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertIn("no route", body)

    def test_post_with_custom_status(self):
        server = self.start([Route("/echo", method="POST", status=201, body="created")])

        status, _, body = self.request(server.base_url + "/echo", method="POST")

        self.assertEqual(status, 201)
        self.assertEqual(body, "created")

    def test_wildcard_route_ignores_query(self):
        server = self.start([Route("/api/*", body="hit")])

        status, _, body = self.request(server.base_url + "/api/users?page=2")

        self.assertEqual(status, 200)
        self.assertEqual(body, "hit")

    def test_first_matching_route_wins(self):
        server = self.start(
            [Route("/same", body="first"), Route("/same", body="second")]
        )

        _, _, body = self.request(server.base_url + "/same")

        self.assertEqual(body, "first")

    def test_delay(self):
        server = self.start([Route("/slow", body="ok", delay_ms=80)])

        started = time.monotonic()
        status, _, _ = self.request(server.base_url + "/slow")
        elapsed = time.monotonic() - started

        self.assertEqual(status, 200)
        self.assertGreaterEqual(elapsed, 0.07)

    def test_body_contains_routes_by_payload(self):
        server = self.start(
            [
                Route(
                    "/hook",
                    method="POST",
                    body_contains='"event":"push"',
                    body="push",
                ),
                Route(
                    "/hook",
                    method="POST",
                    body_contains='"event":"pull"',
                    body="pull",
                ),
            ]
        )

        _, _, push_body = self.request(
            server.base_url + "/hook", method="POST", data=b'{"event":"push"}'
        )
        _, _, pull_body = self.request(
            server.base_url + "/hook", method="POST", data=b'{"event":"pull"}'
        )

        self.assertEqual(push_body, "push")
        self.assertEqual(pull_body, "pull")

    def test_body_not_matching_returns_404(self):
        server = self.start(
            [Route("/hook", method="POST", body_contains="push", body="ok")]
        )

        status, _, _ = self.request(
            server.base_url + "/hook", method="POST", data=b'{"event":"other"}'
        )

        self.assertEqual(status, 404)

    def test_head_has_length_but_no_body(self):
        server = self.start([Route("/h", method="HEAD", body="abc")])

        status, headers, body = self.request(server.base_url + "/h", method="HEAD")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Length"], "3")
        self.assertEqual(body, "")


if __name__ == "__main__":
    unittest.main()
