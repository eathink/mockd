import io
import unittest
from contextlib import redirect_stderr

from mockd.cli import build_parser, main, parse_cli_routes
from mockd.config import ConfigError, Route


class CliTests(unittest.TestCase):
    def test_defaults(self):
        args = build_parser().parse_args(["mock.json"])

        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8080)
        self.assertEqual(args.max_requests, 50)
        self.assertFalse(args.quiet)

    def test_route_flag_is_repeatable(self):
        args = build_parser().parse_args(
            ["m.json", "--route", '{"path":"/x"}', "--route", '{"path":"/y"}']
        )

        self.assertEqual(len(args.route), 2)

    def test_parse_cli_routes(self):
        routes = parse_cli_routes(['{"path":"/x","body":"ok"}'])

        self.assertEqual(routes, [Route("/x", body="ok")])

    def test_parse_cli_routes_invalid_json(self):
        with self.assertRaises(ConfigError):
            parse_cli_routes(["{bad"])

    def test_parse_cli_routes_invalid_schema(self):
        with self.assertRaises(ConfigError):
            parse_cli_routes(['{"path":"relative"}'])

    def test_missing_config_returns_two(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["/nonexistent/mockd.json"])

        self.assertEqual(code, 2)
        self.assertIn("mockd:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
