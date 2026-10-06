"""The R7RS conformance suite (conformance/), run on the engine TULIP_ENGINE
selects, plus a check that the harness itself reports what it should."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ENGINE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "conformance"))

import run as conformance  # noqa: E402

HARNESS_CHECK = """
(import (scheme base) (conformance test))
(section "0 Harness")
(test 3 (+ 1 2))
(test 4 (+ 1 2))
(test-approx 0.3 (+ 0.1 0.2))
(test-values (1 2) (values 1 2))
(test-values (1 2) (values 1 3))
(test-error (car 1))
(test-error (+ 1 1))
(test 1 (raise 'boom))
(test-assert (memq 'a '(a)))
(test-unsupported "gap" (test 1 2))
(test-unsupported "gap" (test 2 2))
(test-report)
"""


class HarnessTests(unittest.TestCase):
    def test_harness_reports_each_outcome(self):
        d = Path(tempfile.mkdtemp(prefix="tulip-conf-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "conformance").mkdir()
        shutil.copy(ROOT / "conformance" / "conformance" / "test.sld", d / "conformance")
        prog = d / "check.scm"
        prog.write_text(HARNESS_CHECK, encoding="utf-8")
        r = conformance.Result(prog, ENGINE, *conformance.run_file(prog, ENGINE))
        self.assertEqual(r.summary, [5, 4, 1, 1], r.out + r.err)
        self.assertEqual(len(r.lines["FAIL"]), 4)
        self.assertIn("expected 4 got 3", r.lines["FAIL"][0])
        self.assertIn("raised boom", r.lines["FAIL"][3])
        self.assertFalse(r.ok)


class ConformanceTests(unittest.TestCase):
    def test_sections(self):
        files = conformance.section_files()
        self.assertTrue(files)
        for path in files:
            with self.subTest(section=path.name):
                r = conformance.Result(path, ENGINE, *conformance.run_file(path, ENGINE))
                self.assertTrue(r.ok, "%s: %s\n%s" % (
                    path.name, r.describe(), "\n".join(r.lines["FAIL"] + r.lines["XPASS"])))


if __name__ == "__main__":
    unittest.main()
