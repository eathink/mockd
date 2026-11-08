import io
import unittest
from contextlib import redirect_stderr

from mockd.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_defaults(self):
        args = build_parser().parse_args(["mock.json"])

        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8080)
        self.assertEqual(args.max_requests, 50)
        self.assertFalse(args.quiet)

    def test_missing_config_returns_two(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["/nonexistent/mockd.json"])

        self.assertEqual(code, 2)
        self.assertIn("mockd:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
