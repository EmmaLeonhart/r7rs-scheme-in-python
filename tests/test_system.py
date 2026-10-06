"""eval, environments, load, process context, time, the CLI and REPL."""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import ENGINE, SchemeTestCase
from tulip.prims_system import SchemeExit
from tulip.runtime import Runtime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EvalTests(SchemeTestCase):
    def test_eval(self):
        self.checks([
            ("(eval '(* 7 3) (environment '(scheme base)))", "21"),
            ("(let ((f (eval '(lambda (f x) (f x x)) (null-environment 5)))) (f + 10))",
             "20"),
            ("(eval '(if #t 'a 'b) (scheme-report-environment 5))", "a"),
            ("(begin (eval '(define evx 5) (interaction-environment)) evx)", "5"),
            ("(guard (e (#t (error-object-message e)))"
             " (eval '(car 1) (environment '(scheme base))))", '"car: not a pair"'),
            ("(guard (e (#t 'unbound)) (eval 'display (environment '(only (scheme base) car))))",
             "unbound"),
            ("(eval '(let loop ((i 0)) (if (< i 10) (loop (+ i 1)) i)))", "10"),
        ])

    def test_eval_is_a_tail_call(self):
        self.check("(define (f n) (if (= n 0) 'done (eval (list 'f (- n 1)))))"
                   " (f 20000)", "done")

    def test_environment_isolation(self):
        self.check("(define e (environment '(scheme base))) (eval '(define z 1) e)"
                   " (guard (x (#t 'not-here)) z)", "not-here")


class LoadTests(SchemeTestCase):
    def test_load(self):
        d = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "defs.scm")
        with open(path, "w", encoding="utf-8") as f:
            f.write("(define loaded-value 99)")
        self.check('(load "%s") loaded-value' % path.replace("\\", "/"), "99")
        self.check('(guard (e ((file-error? e) \'missing)) (load "%s/nope.scm"))'
                   % d.replace("\\", "/"), "missing")


class ProcessContextTests(SchemeTestCase):
    def test_command_line_and_environment(self):
        rt = Runtime(["prog.scm", "x"], engine=ENGINE)
        from tulip.printer import write_string
        self.assertEqual(write_string(rt.eval_string("(command-line)")), '("prog.scm" "x")')
        self.check('(string? (get-environment-variable "PATH"))', "#t")
        self.check('(get-environment-variable "TULIP_SURELY_UNSET_VARIABLE")', "#f")
        self.check("(pair? (car (get-environment-variables)))", "#t")

    def test_exit_runs_after_thunks(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SchemeExit) as cm:
                self.ev("(dynamic-wind (lambda () #f) (lambda () (exit 3))"
                        " (lambda () (display \"after\")))")
        self.assertEqual(cm.exception.code, 3)
        self.assertEqual(buf.getvalue(), "after")

    def test_exit_codes(self):
        for src, code in [("(exit)", 0), ("(exit #t)", 0), ("(exit #f)", 1),
                          ("(exit 7)", 7), ("(emergency-exit 2)", 2)]:
            with self.subTest(src=src):
                with self.assertRaises(SchemeExit) as cm:
                    self.ev(src)
                self.assertEqual(cm.exception.code, code)

    def test_exit_not_caught_by_guard(self):
        with self.assertRaises(SchemeExit):
            self.ev("(guard (e (#t 'caught)) (exit 1))")

    def test_time(self):
        self.checks([
            ("(real? (current-second))", "#t"),
            ("(exact-integer? (current-jiffy))", "#t"),
            ("(jiffies-per-second)", "1000000000"),
            ("(let ((a (current-jiffy))) (<= a (current-jiffy)))", "#t"),
        ])

    def test_complex_library_on_reals(self):
        self.checks([
            ("(real-part 5)", "5"), ("(imag-part 2.5)", "0"), ("(magnitude -3)", "3"),
            ("(angle 1)", "0"), ("(angle -1)", "3.141592653589793"),
            ("(make-rectangular 2 0)", "2"), ("(make-polar 2 0)", "2"),
        ])
        self.error("(make-rectangular 1 2)", "complex numbers are not supported")

    def test_all_standard_names_exist(self):
        self.assertEqual(self.rt.libraries.missing, [])


class CLITests(unittest.TestCase):
    def run_tulip(self, args, stdin=""):
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "tulip"] + args, input=stdin,
                              capture_output=True, text=True, env=env, cwd=ROOT,
                              encoding="utf-8", timeout=60)

    def test_program_and_exit_status(self):
        d = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        prog = os.path.join(d, "prog.scm")
        with open(prog, "w", encoding="utf-8") as f:
            f.write("(import (scheme base) (scheme write) (scheme process-context))\n"
                    "(display (cdr (command-line))) (newline)\n"
                    "(exit (length (command-line)))\n")
        r = self.run_tulip([prog, "a", "b"])
        self.assertEqual(r.stdout, "(a b)\n")
        self.assertEqual(r.returncode, 3)

    def test_uncaught_error_status(self):
        d = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        prog = os.path.join(d, "bad.scm")
        with open(prog, "w", encoding="utf-8") as f:
            f.write('(display "partial")\n(car 5)\n')
        r = self.run_tulip([prog])
        self.assertEqual(r.stdout, "partial")
        self.assertIn("car: not a pair 5", r.stderr)
        self.assertEqual(r.returncode, 70)

    def test_engine_option(self):
        d = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        prog = os.path.join(d, "prog.scm")
        with open(prog, "w", encoding="utf-8") as f:
            f.write("(import (scheme base) (scheme write) (scheme process-context))\n"
                    "(define (f n) (if (= n 0) 'done (f (- n 1))))\n"
                    "(write (list (f 10000) (cdr (command-line)))) (newline)\n")
        for args in (["--engine", "vm"], ["--engine=interp"], ["--engine", "vm", "--"]):
            r = self.run_tulip(args + [prog, "--engine"])
            self.assertEqual(r.stdout, '(done ("--engine"))\n', args)
            self.assertEqual(r.returncode, 0)
        r = self.run_tulip(["--engine", "jit", prog])
        self.assertIn("unknown engine", r.stderr)
        self.assertEqual(r.returncode, 2)
        r = self.run_tulip(["--engine", "vm"], stdin="(+ 1 2)\n")
        self.assertEqual(r.stdout, "3\n")

    def test_repl(self):
        r = self.run_tulip([], stdin="(values 1 2)\n(car '())\n(define x\n  5)\nx\n(exit 4)\nx\n")
        self.assertEqual(r.stdout, "1\n2\nerror: car: not a pair ()\n5\n")
        self.assertEqual(r.returncode, 4)


if __name__ == "__main__":
    unittest.main()
