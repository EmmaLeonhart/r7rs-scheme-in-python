import unittest

from helpers import SchemeTestCase


class PrinterTests(SchemeTestCase):
    def test_write_and_display(self):
        self.checks([
            ('"a\\nb"', '"a\\nb"'),
            (r"#\a", r"#\a"),
            (r"#\space", r"#\space"),
            (r"#\x0", r"#\null"),
            ("'|a b|", "|a b|"),
            ("'||", "||"),
            ("(string->symbol \"1\")", "|1|"),
            ("'(quote x)", "'x"),
            ("'(quote x y)", "(quote x y)"),
            ("1.0", "1.0"),
            ("1e21", "1.0e+21"),
            ("-0.0", "-0.0"),
            ("#u8(1 2)", "#u8(1 2)"),
            ("(vector 1 \"a\" #\\b)", '#(1 "a" #\\b)'),
        ])

    def test_display_output(self):
        self.check('(let ((p (open-output-string))) '
                   '(display "a\\nb" p) (display #\\c p) (display (list "x" #\\y) p) '
                   '(get-output-string p))', '"a\\nbc(x y)"')

    def test_cycles(self):
        self.check("(let ((x (list 1 2))) (set-cdr! (cdr x) x) "
                   "(let ((p (open-output-string))) (write x p) (get-output-string p)))",
                   '"#0=(1 2 . #0#)"')
        # shared but acyclic structure is not labelled by write...
        self.check("(let ((x (list 1))) (let ((p (open-output-string)))"
                   " (write (list x x) p) (get-output-string p)))", '"((1) (1))"')
        # ...but is by write-shared
        self.check("(let ((x (list 1))) (let ((p (open-output-string)))"
                   " (write-shared (list x x) p) (get-output-string p)))",
                   '"(#0=(1) #0#)"')
        self.check("(let ((v (vector 1 2))) (vector-set! v 0 v)"
                   " (let ((p (open-output-string))) (write v p) (get-output-string p)))",
                   '"#0=#(#0# 2)"')


if __name__ == "__main__":
    unittest.main()
