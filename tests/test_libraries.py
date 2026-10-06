"""define-library, import sets, library files, cond-expand, include."""

import os
import shutil
import tempfile
import unittest

from helpers import SchemeTestCase


class LibraryTests(SchemeTestCase):
    def test_define_and_import(self):
        self.check("""
            (define-library (stack)
              (export make-stack push! (rename pop-internal pop!) stack-items)
              (import (scheme base))
              (begin
                (define (make-stack) (list 'stack))
                (define (push! s x) (set-cdr! s (cons x (cdr s))))
                (define (pop-internal s) (let ((x (cadr s))) (set-cdr! s (cddr s)) x))
                (define (stack-items s) (cdr s))))
            (import (stack))
            (define s (make-stack))
            (push! s 1) (push! s 2)
            (list (pop! s) (stack-items s))""", "(2 (1))")

    def test_library_private_names(self):
        self.error("""
            (define-library (hidden) (export visible) (import (scheme base))
              (begin (define (helper) 1) (define (visible) (helper))))
            (import (hidden))
            (helper)""", "unbound variable")

    def test_import_sets(self):
        self.ev("""
            (define-library (nums) (export one two three) (import (scheme base))
              (begin (define one 1) (define two 2) (define three 3)))""")
        self.check("(import (only (nums) one)) one", "1")
        self.check("(import (prefix (nums) n:)) (list n:one n:two)", "(1 2)")
        self.check("(import (rename (nums) (two zwei))) zwei", "2")
        self.check("(import (except (nums) three)) two", "2")
        self.check("(import (prefix (only (nums) three) my-)) my-three", "3")
        self.error("(import (only (nums) four))", "not exported")

    def test_exported_macro_hygiene(self):
        # the macro's free identifier refers to the library's private helper
        self.check("""
            (define-library (twice) (export twice) (import (scheme base))
              (begin
                (define (helper x) (* 2 x))
                (define-syntax twice (syntax-rules () ((_ e) (helper e))))))
            (import (twice))
            (define (helper x) 'user-helper)
            (twice 21)""", "42")

    def test_live_bindings(self):
        self.check("""
            (define-library (counter) (export count bump!) (import (scheme base))
              (begin (define count 0) (define (bump!) (set! count (+ count 1)))))
            (import (counter))
            (bump!) (bump!)
            count""", "2")
        self.error("(define-library (c2) (export v) (import (scheme base)) (begin (define v 1)))"
                   " (import (c2)) (set! v 2)", "imported")

    def test_user_redefinition_does_not_break_builtins(self):
        self.check("(define (if a) 'mine) (list (if 1) (cond (#f 1) (else 2)))", "(mine 2)")
        self.check("(define list vector) (let*-values (((a b) (values 1 2))) (list a b))",
                   "#(1 2)")
        self.check("(define car cdr) (car '(1 2))", "(2)")

    def test_missing_library(self):
        self.error("(import (no such library))", "library not found")

    def test_standard_library_contents(self):
        self.check("(import (scheme char)) (char-upcase #\\a)", "#\\A")
        self.check("(import (only (scheme cxr) caddar)) (caddar '((1 2 3)))", "3")
        self.check("(import (prefix (scheme lazy) lazy:)) (lazy:force (lazy:delay 1))", "1")

    def test_syntax_error_form(self):
        self.error("(define-syntax must-be-pair (syntax-rules () ((_ (a . b)) 'ok)"
                   " ((_ x) (syntax-error \"expected a pair\" x)))) (must-be-pair 5)",
                   "expected a pair 5")


class CondExpandTests(SchemeTestCase):
    def test_expression_form(self):
        self.checks([
            ("(cond-expand (r7rs 'yes) (else 'no))", "yes"),
            ("(cond-expand (no-such-feature 'yes) (else 'no))", "no"),
            ("(cond-expand ((and r7rs (not no-such-feature)) 'both) (else 'no))", "both"),
            ("(cond-expand ((or no-such-feature tulip) 'either) (else 'no))", "either"),
            ("(cond-expand ((library (scheme base)) 'have-base) (else 'no))", "have-base"),
            ("(cond-expand ((library (not a lib)) 'yes) (else 'no))", "no"),
            ("(memq 'r7rs (features))", "(r7rs exact-closed ratios full-unicode tulip"
             " tulip-0.1 python %s %s)" % self._platform_features()),
        ])
        self.check("(cond-expand (r7rs (define cx 5))) cx", "5")

    def _platform_features(self):
        from tulip.libraries import FEATURES
        return tuple(FEATURES[-2:])

    def test_in_library(self):
        self.check("""
            (define-library (ce) (export which) (import (scheme base))
              (cond-expand
                (no-such-feature (begin (define which 'wrong)))
                (else (begin (define which 'right)))))
            (import (ce)) which""", "right")


class FileTests(SchemeTestCase):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.rt.libraries.search_path.insert(0, self.dir)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_library_from_file(self):
        self.write("geometry/points.sld", """
            (define-library (geometry points)
              (export make-point point-x)
              (import (scheme base))
              (include "points-impl.scm"))""")
        self.write("geometry/points-impl.scm", """
            (define-record-type point (make-point x y) point? (x point-x) (y point-y))""")
        self.check("(import (geometry points)) (point-x (make-point 3 4))", "3")

    def test_include_library_declarations(self):
        self.write("decl/lib.sld", """
            (define-library (decl lib)
              (include-library-declarations "decls.scm"))""")
        self.write("decl/decls.scm", """
            (export answer) (import (scheme base)) (begin (define answer 42))""")
        self.check("(import (decl lib)) answer", "42")

    def test_include_and_include_ci(self):
        path = self.write("inc.scm", "(define included 'yes) (define Mixed 1)")
        p = path.replace("\\", "/")
        self.check('(include "%s") included' % p, "yes")
        self.check('(include-ci "%s") mixed' % p, "1")
        self.check('(define (f) (include "%s") included) (f)' % p, "yes")
        self.error('(include "%s/no-such-file.scm")' % self.dir.replace("\\", "/"),
                   "cannot read file")

    def test_program_file(self):
        self.write("lib/util.sld", """
            (define-library (lib util) (export double) (import (scheme base))
              (begin (define (double x) (* 2 x))))""")
        prog = self.write("prog.scm", """
            (import (scheme base) (lib util))
            (define result (double 21))""")
        self.rt.load_file(prog)
        self.check("result", "42")


if __name__ == "__main__":
    unittest.main()
