"""Shared test helpers: a fresh runtime per test, results compared as their
``write`` representation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tulip.printer import write_string  # noqa: E402
from tulip.runtime import Runtime  # noqa: E402
from tulip.types import SchemeError  # noqa: E402


class SchemeTestCase(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()

    def ev(self, src):
        return self.rt.eval_string(src)

    def w(self, src):
        return write_string(self.ev(src))

    def check(self, src, expected):
        self.assertEqual(self.w(src), expected, src)

    def checks(self, pairs):
        for src, expected in pairs:
            with self.subTest(src=src):
                self.check(src, expected)

    def error(self, src, fragment=""):
        with self.assertRaises(SchemeError) as cm:
            self.ev(src)
        if fragment:
            self.assertIn(fragment, str(cm.exception))
