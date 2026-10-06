"""The numeric tower (R7RS 6.2); expected values mostly from the report."""

import unittest

from helpers import SchemeTestCase


class NumberTests(SchemeTestCase):
    def test_predicates(self):
        self.checks([
            ("(complex? 3)", "#t"), ("(real? 3)", "#t"), ("(real? 1.5)", "#t"),
            ("(rational? 6/10)", "#t"), ("(rational? 6/3)", "#t"),
            ("(rational? +inf.0)", "#f"), ("(rational? +nan.0)", "#f"),
            ("(integer? 3.0)", "#t"), ("(integer? 8/4)", "#t"), ("(integer? 1.5)", "#f"),
            ("(number? 'a)", "#f"), ("(number? #t)", "#f"), ("(integer? #t)", "#f"),
            ("(exact? 3.0)", "#f"), ("(exact? 1/2)", "#t"), ("(inexact? 3.)", "#t"),
            ("(exact-integer? 32)", "#t"), ("(exact-integer? 32.0)", "#f"),
            ("(exact-integer? 32/5)", "#f"),
            ("(finite? 3)", "#t"), ("(finite? +inf.0)", "#f"),
            ("(infinite? -inf.0)", "#t"), ("(infinite? 3.0)", "#f"),
            ("(nan? +nan.0)", "#t"), ("(nan? 32)", "#f"),
            ("(zero? 0)", "#t"), ("(zero? -0.0)", "#t"), ("(zero? 1/2)", "#f"),
            ("(positive? 1/2)", "#t"), ("(negative? -0.5)", "#t"),
            ("(odd? 3)", "#t"), ("(even? 0)", "#t"), ("(even? 4.0)", "#t"),
            ("(odd? -1)", "#t"),
        ])
        self.error("(odd? 1.5)", "not an integer")
        self.error("(zero? 'a)", "not a number")

    def test_comparison(self):
        self.checks([
            ("(= 1 1.0 1)", "#t"), ("(= 1 2)", "#f"), ("(< 1 2 3)", "#t"),
            ("(< 1 3 2)", "#f"), ("(<= 1 1 2)", "#t"), ("(> 3 2 1)", "#t"),
            ("(>= 3 3 1)", "#t"), ("(< 1/3 0.34)", "#t"),
            ("(= +nan.0 +nan.0)", "#f"), ("(< 1 +inf.0)", "#t"),
            ("(= 1/2 0.5)", "#t"),
            ("(max 3 4)", "4"), ("(max 3.9 4)", "4.0"), ("(min 1 2.0)", "1.0"),
            ("(min 1/2 1/3)", "1/3"),
        ])

    def test_arithmetic(self):
        self.checks([
            ("(+ 3 4)", "7"), ("(+ 3)", "3"), ("(+)", "0"), ("(* 4)", "4"), ("(*)", "1"),
            ("(- 3 4)", "-1"), ("(- 3 4 5)", "-6"), ("(- 3)", "-3"),
            ("(/ 3 4 5)", "3/20"), ("(/ 3)", "1/3"), ("(/ 6 3)", "2"),
            ("(/ 1.0 4)", "0.25"), ("(+ 1/2 1/2)", "1"), ("(* 1/2 4)", "2"),
            ("(+ 1/2 0.5)", "1.0"), ("(abs -7)", "7"), ("(abs -7/2)", "7/2"),
            ("(* 99999999999 99999999999)", "9999999999800000000001"),
            ("(/ 1.0 0)", "+inf.0"), ("(/ -1 0.0)", "-inf.0"), ("(/ 0.0 0)", "+nan.0"),
        ])
        self.error("(/ 1 0)", "division by zero")
        self.error("(+ 1 'a)", "not a number")

    def test_integer_division(self):
        self.checks([
            ("(call-with-values (lambda () (floor/ 5 2)) list)", "(2 1)"),
            ("(call-with-values (lambda () (floor/ -5 2)) list)", "(-3 1)"),
            ("(call-with-values (lambda () (floor/ 5 -2)) list)", "(-3 -1)"),
            ("(call-with-values (lambda () (floor/ -5 -2)) list)", "(2 -1)"),
            ("(call-with-values (lambda () (truncate/ 5 2)) list)", "(2 1)"),
            ("(call-with-values (lambda () (truncate/ -5 2)) list)", "(-2 -1)"),
            ("(call-with-values (lambda () (truncate/ 5 -2)) list)", "(-2 1)"),
            ("(call-with-values (lambda () (truncate/ -5 -2)) list)", "(2 -1)"),
            ("(call-with-values (lambda () (truncate/ -5.0 2)) list)", "(-2.0 -1.0)"),
            ("(floor-quotient 7 -2)", "-4"), ("(floor-remainder 7 -2)", "-1"),
            ("(modulo -7 2)", "1"), ("(remainder -7 2)", "-1"), ("(quotient -7 2)", "-3"),
            ("(gcd 32 -36)", "4"), ("(gcd)", "0"), ("(lcm 32 -36)", "288"),
            ("(lcm 32.0 -36)", "288.0"), ("(lcm)", "1"),
        ])
        self.error("(quotient 1 0)", "division by zero")

    def test_rationals(self):
        self.checks([
            ("(numerator (/ 6 4))", "3"), ("(denominator (/ 6 4))", "2"),
            ("(denominator (inexact (/ 6 4)))", "2.0"), ("(numerator 0.5)", "1.0"),
            ("(denominator 5)", "1"),
            ("(rationalize (exact .3) 1/10)", "1/3"), ("(rationalize .3 1/10)",
                                                       "0.3333333333333333"),
        ])

    def test_rounding(self):
        self.checks([
            ("(floor -4.3)", "-5.0"), ("(ceiling -4.3)", "-4.0"),
            ("(truncate -4.3)", "-4.0"), ("(round -4.3)", "-4.0"),
            ("(floor 3.5)", "3.0"), ("(ceiling 3.5)", "4.0"), ("(truncate 3.5)", "3.0"),
            ("(round 3.5)", "4.0"), ("(round 7/2)", "4"), ("(round 7)", "7"),
            ("(round 2.5)", "2.0"), ("(round -2.5)", "-2.0"), ("(floor 5/2)", "2"),
            ("(ceiling 5/2)", "3"), ("(round +inf.0)", "+inf.0"),
        ])

    def test_transcendental(self):
        self.checks([
            ("(exp 0)", "1.0"), ("(log 1)", "0.0"), ("(log 100 10)", "2.0"),
            ("(log 0)", "-inf.0"), ("(sin 0)", "0.0"), ("(atan 1 1)", "0.7853981633974483"),
            ("(square 42)", "1764"), ("(square 2.0)", "4.0"), ("(square 1/2)", "1/4"),
            ("(sqrt 9)", "3"), ("(sqrt 2)", "1.4142135623730951"), ("(sqrt 1/4)", "1/2"),
            ("(sqrt 16.0)", "4.0"),
            ("(call-with-values (lambda () (exact-integer-sqrt 4)) list)", "(2 0)"),
            ("(call-with-values (lambda () (exact-integer-sqrt 5)) list)", "(2 1)"),
            ("(expt 2 10)", "1024"), ("(expt 2 -2)", "1/4"), ("(expt 2.0 3)", "8.0"),
            ("(expt 4 1/2)", "2.0"), ("(expt 0 0)", "1"), ("(expt 0.0 0)", "1.0"),
            ("(expt 1/2 2)", "1/4"),
        ])
        self.error("(sqrt -4)", "complex numbers are not supported")

    def test_exactness(self):
        self.checks([
            ("(exact 2.5)", "5/2"), ("(exact 2.0)", "2"), ("(inexact 1/4)", "0.25"),
            ("(exact->inexact 1/3)", "0.3333333333333333"),
            ("(inexact->exact 0.5)", "1/2"),
            ("(inexact (expt 10 400))", "+inf.0"),
        ])
        self.error("(exact +inf.0)", "no exact representation")

    def test_number_string_conversion(self):
        self.checks([
            ('(number->string 255 16)', '"ff"'), ('(number->string -10 2)', '"-1010"'),
            ('(number->string 1/3 2)', '"1/11"'), ('(number->string 3.5)', '"3.5"'),
            ('(string->number "100")', "100"), ('(string->number "100" 16)', "256"),
            ('(string->number "1e2")', "100.0"), ('(string->number "#xff")', "255"),
            ('(string->number "abc")', "#f"), ('(string->number "1/2")', "1/2"),
            ('(string->number "")', "#f"), ('(string->number "1+2i")', "#f"),
            ('(string->number "-1.5e-3")', "-0.0015"),
        ])


if __name__ == "__main__":
    unittest.main()
