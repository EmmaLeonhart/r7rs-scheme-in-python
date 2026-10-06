"""Ports and file I/O (R7RS 6.13, (scheme file))."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest

from helpers import SchemeTestCase
from tulip import ports


class StringPortTests(SchemeTestCase):
    def test_reading(self):
        self.checks([
            ('(let ((p (open-input-string "(a b) 42 \\"s\\" line2\\nrest")))'
             ' (list (read p) (read p) (read p) (read-char p) (read-line p)'
             ' (read-line p) (eof-object? (read-line p))))',
             '((a b) 42 "s" #\\space "line2" "rest" #t)'),
            ('(let ((p (open-input-string "abc"))) (list (peek-char p) (read-char p)'
             ' (read-string 5 p) (eof-object? (read-char p)) (eof-object? (peek-char p))))',
             '(#\\a #\\a "bc" #t #t)'),
            ('(let ((p (open-input-string "a\\r\\nb\\rc\\n"))) (list (read-line p)'
             ' (read-line p) (read-line p) (eof-object? (read-line p))))',
             '("a" "b" "c" #t)'),
            ('(eof-object? (read (open-input-string "  ; just a comment\\n")))', "#t"),
            ('(read (open-input-string "#0=(1 . #0#)"))', "#0=(1 . #0#)"),
            ('(char-ready? (open-input-string ""))', "#t"),
            ("(eof-object? (eof-object))", "#t"),
            ('(read-string 0 (open-input-string "abc"))', '""'),
        ])
        self.error('(read (open-input-string "(1 2"))', "end of input")

    def test_writing(self):
        self.checks([
            ('(let ((p (open-output-string))) (write "a" p) (display "a" p)'
             ' (write-char #\\b p) (write-string "hello" p 1 3) (newline p)'
             ' (get-output-string p))', '"\\"a\\"abel\\n"'),
            ('(let ((p (open-output-string)))'
             ' (parameterize ((current-output-port p)) (display 1) (write \'x))'
             ' (get-output-string p))', '"1x"'),
        ])

    def test_predicates_and_closing(self):
        self.checks([
            ('(let ((p (open-input-string "x"))) (list (port? p) (input-port? p)'
             ' (output-port? p) (textual-port? p) (binary-port? p) (input-port-open? p)))',
             "(#t #t #f #t #f #t)"),
            ('(let ((p (open-input-string "x"))) (close-port p) (input-port-open? p))', "#f"),
            ("(output-port? (current-output-port))", "#t"),
            ("(input-port? (current-input-port))", "#t"),
            ("(textual-port? (current-error-port))", "#t"),
            ("(port? 5)", "#f"),
        ])
        self.error('(let ((p (open-input-string "x"))) (close-input-port p) (read-char p))',
                   "closed")
        self.error('(read-char (open-output-string))', "wrong kind of port")


class BinaryPortTests(SchemeTestCase):
    def test_binary(self):
        self.checks([
            ("(let ((p (open-input-bytevector (bytevector 1 2 3))))"
             " (list (read-u8 p) (peek-u8 p) (u8-ready? p) (read-bytevector 5 p)"
             " (eof-object? (read-u8 p))))", "(1 2 #t #u8(2 3) #t)"),
            ("(let ((p (open-output-bytevector))) (write-u8 7 p)"
             " (write-bytevector (bytevector 1 2 3) p 1) (get-output-bytevector p))",
             "#u8(7 2 3)"),
            ("(let ((p (open-input-bytevector (bytevector 1 2 3))) (bv (make-bytevector 4 0)))"
             " (let ((n (read-bytevector! bv p 1))) (list n bv)))", "(3 #u8(0 1 2 3))"),
            ("(binary-port? (open-input-bytevector (bytevector)))", "#t"),
            ("(eof-object? (read-bytevector 1 (open-input-bytevector (bytevector))))", "#t"),
        ])


class FilePortTests(SchemeTestCase):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp(prefix="tulip-test-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name).replace("\\", "/")

    def test_text_files(self):
        f = self.path("out.txt")
        self.check('(call-with-output-file "%s" (lambda (p) (write \'(1 "two") p)'
                   ' (newline p) (display "line two" p)))' % f, "")
        self.check('(file-exists? "%s")' % f, "#t")
        self.check('(call-with-input-file "%s" (lambda (p) (list (read p) (read-line p)'
                   ' (read-line p))))' % f, '((1 "two") "" "line two")')
        self.check('(with-input-from-file "%s" (lambda () (read)))' % f, '(1 "two")')
        self.check('(begin (with-output-to-file "%s" (lambda () (display "replaced")))'
                   ' (call-with-input-file "%s" read-line))' % (f, f), '"replaced"')
        self.check('(begin (delete-file "%s") (file-exists? "%s"))' % (f, f), "#f")

    def test_unicode_round_trip(self):
        f = self.path("u.txt")
        self.check('(begin (with-output-to-file "%s" (lambda () (write "λ→✓")))'
                   ' (with-input-from-file "%s" read))' % (f, f), '"λ→✓"')

    def test_binary_files(self):
        f = self.path("b.bin")
        self.check('(let ((p (open-binary-output-file "%s"))) (write-bytevector'
                   ' (bytevector 0 255 10) p) (close-port p)'
                   ' (let ((q (open-binary-input-file "%s"))) (let ((b (read-bytevector 10 q)))'
                   ' (close-port q) b)))' % (f, f), "#u8(0 255 10)")

    def test_file_errors(self):
        self.check('(guard (e ((file-error? e) \'file-error)) (open-input-file "%s"))'
                   % self.path("missing.txt"), "file-error")
        self.check('(guard (e ((file-error? e) \'file-error)) (delete-file "%s"))'
                   % self.path("missing.txt"), "file-error")
        self.check('(guard (e ((read-error? e) \'read-error))'
                   ' (read (open-input-string "(1 . )")))', "read-error")


class ConsoleTests(SchemeTestCase):
    def test_console_output_follows_sys_stdout(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ev('(display "hello") (newline) (write #\\a)')
        self.assertEqual(buf.getvalue(), "hello\n#\\a")

    def test_console_input_reads_across_lines(self):
        port = ports.ConsoleInputPort()
        lines = iter(["(a\n", " b)  42\n", ""])
        port.source = lambda: next(lines)
        self.assertEqual(repr(port.read_datum()), "(a b)")
        self.assertEqual(port.read_datum(), 42)


if __name__ == "__main__":
    unittest.main()
