import json
import tempfile
import unittest
from pathlib import Path

from mockd.config import ConfigError, Route, load_config


class RouteMatchTests(unittest.TestCase):
    def test_exact_path(self):
        route = Route("/health")

        self.assertTrue(route.matches("GET", "/health"))
        self.assertFalse(route.matches("GET", "/healthz"))
        self.assertFalse(route.matches("POST", "/health"))

    def test_wildcard_method(self):
        route = Route("/anything", method="*")

        self.assertTrue(route.matches("DELETE", "/anything"))
        self.assertTrue(route.matches("GET", "/anything"))

    def test_prefix_wildcard(self):
        route = Route("/api/*")

        self.assertTrue(route.matches("GET", "/api/users"))
        self.assertTrue(route.matches("GET", "/api/"))
        self.assertFalse(route.matches("GET", "/apis"))

    def test_prefix_wildcard_without_slash(self):
        route = Route("/api/users*")

        self.assertTrue(route.matches("GET", "/api/users"))
        self.assertTrue(route.matches("GET", "/api/users/1"))
        self.assertFalse(route.matches("GET", "/api/user"))


class LoadConfigTests(unittest.TestCase):
    def load(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_config(path)

    def load_text(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(text, encoding="utf-8")
            return load_config(path)

    def test_full_route(self):
        routes = self.load(
            {
                "routes": [
                    {
                        "method": "post",
                        "path": "/echo",
                        "status": 201,
                        "headers": {"X-Mock": "1"},
                        "body": "created",
                        "delay_ms": 10,
                    }
                ]
            }
        )

        self.assertEqual(
            routes,
            [Route("/echo", "POST", 201, {"X-Mock": "1"}, "created", 10)],
        )

    def test_defaults(self):
        routes = self.load({"routes": [{"path": "/health"}]})

        self.assertEqual(routes, [Route("/health")])

    def test_unknown_field_rejected(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/", "boddy": "typo"}]})

    def test_invalid_path_rejected(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "relative"}]})

    def test_query_in_path_rejected(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/x?a=1"}]})

    def test_invalid_method_rejected(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/", "method": "FETCH"}]})

    def test_status_range(self):
        for status in (99, 600, "200", True):
            with self.subTest(status=status):
                with self.assertRaises(ConfigError):
                    self.load({"routes": [{"path": "/", "status": status}]})

    def test_headers_must_be_string_map(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/", "headers": {"X": 1}}]})

    def test_body_must_be_string(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/", "body": {"a": 1}}]})

    def test_delay_must_be_non_negative(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": [{"path": "/", "delay_ms": -1}]})

    def test_routes_must_be_non_empty(self):
        with self.assertRaises(ConfigError):
            self.load({"routes": []})

    def test_top_level_must_be_object(self):
        with self.assertRaises(ConfigError):
            self.load([])

    def test_malformed_json(self):
        with self.assertRaises(ConfigError):
            self.load_text('{"routes": [')

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/mockd.json")


if __name__ == "__main__":
    unittest.main()
