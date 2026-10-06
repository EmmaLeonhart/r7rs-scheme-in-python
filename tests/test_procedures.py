"""Standard procedures (R7RS 6.1, 6.3-6.10); expected values mostly from the
report."""

import unittest

from helpers import SchemeTestCase


class EquivalenceTests(SchemeTestCase):
    def test_eqv(self):
        self.checks([
            ("(eqv? 'a 'a)", "#t"), ("(eqv? 'a 'b)", "#f"), ("(eqv? 2 2)", "#t"),
            ("(eqv? 2 2.0)", "#f"), ("(eqv? '() '())", "#t"),
            ("(eqv? 100000000 100000000)", "#t"), ("(eqv? 0.0 +nan.0)", "#f"),
            ("(eqv? (cons 1 2) (cons 1 2))", "#f"),
            ("(eqv? (lambda () 1) (lambda () 2))", "#f"),
            ("(let ((p (lambda (x) x))) (eqv? p p))", "#t"), ("(eqv? #f 'nil)", "#f"),
            ("(eqv? #\\a #\\a)", "#t"), ("(eqv? \"\" \"\")", "#f"),
            ("(eqv? 1/2 1/2)", "#t"), ("(eqv? 0.5 0.5)", "#t"),
            # signed zeros are = but not eqv? (found by the conformance suite)
            ("(eqv? 0.0 -0.0)", "#f"), ("(eqv? -0.0 -0.0)", "#t"), ("(= 0.0 -0.0)", "#t"),
            ("(memv -0.0 '(0.0 -0.0))", "(-0.0)"), ("(case -0.0 ((0.0) 'pos) (else 'other))", "other"),
        ])

    def test_eq(self):
        self.checks([
            ("(eq? 'a 'a)", "#t"), ("(eq? (list 'a) (list 'a))", "#f"),
            ("(eq? '() '())", "#t"), ("(eq? car car)", "#t"),
            ("(let ((x '(a))) (eq? x x))", "#t"), ("(eq? 5 5)", "#t"),
        ])

    def test_equal(self):
        self.checks([
            ("(equal? 'a 'a)", "#t"), ("(equal? '(a) '(a))", "#t"),
            ("(equal? '(a (b) c) '(a (b) c))", "#t"), ('(equal? "abc" "abc")', "#t"),
            ("(equal? 2 2)", "#t"), ("(equal? (make-vector 5 'a) (make-vector 5 'a))", "#t"),
            ("(equal? '#(1 (2)) (vector 1 (list 2)))", "#t"), ("(equal? 2 2.0)", "#f"),
            ("(equal? #u8(1 2) (bytevector 1 2))", "#t"), ("(equal? '(1 2) '(1 2 3))", "#f"),
        ])
        # terminates on circular structure
        self.check("(let ((a (list 1 2)) (b (list 1 2))) (set-cdr! (cdr a) a)"
                   " (set-cdr! (cdr b) b) (equal? a b))", "#t")


class ListTests(SchemeTestCase):
    def test_pairs(self):
        self.checks([
            ("(pair? '(a . b))", "#t"), ("(pair? '())", "#f"), ("(pair? '#(a b))", "#f"),
            ("(cons 'a '())", "(a)"), ("(cons '(a) '(b c d))", "((a) b c d)"),
            ("(cons \"a\" '(b c))", '("a" b c)'), ("(cons 'a 3)", "(a . 3)"),
            ("(car '((a) b c d))", "(a)"), ("(cdr '(1 . 2))", "2"),
            ("(let ((p (list 1 2))) (set-car! p 9) p)", "(9 2)"),
            ("(caddr '(1 2 3))", "3"), ("(cdddr '(1 2 3 4))", "(4)"),
            ("(cadadr '(1 (2 3)))", "3"),
        ])
        self.error("(car '())", "not a pair")

    def test_lists(self):
        self.checks([
            ("(list? '(a b c))", "#t"), ("(list? '())", "#t"), ("(list? '(a . b))", "#f"),
            ("(let ((x (list 'a))) (set-cdr! x x) (list? x))", "#f"),
            ("(null? '())", "#t"), ("(make-list 2 3)", "(3 3)"),
            ("(list 'a (+ 3 4) 'c)", "(a 7 c)"), ("(list)", "()"),
            ("(length '(a (b) (c d e)))", "3"), ("(length '())", "0"),
            ("(append '(x) '(y))", "(x y)"), ("(append '(a) '(b c d))", "(a b c d)"),
            ("(append '(a (b)) '((c)))", "(a (b) (c))"), ("(append '(a b) '(c . d))",
                                                            "(a b c . d)"),
            ("(append '() 'a)", "a"), ("(append)", "()"), ("(append '(1))", "(1)"),
            ("(reverse '(a (b c) d (e (f))))", "((e (f)) d (b c) a)"),
            ("(list-tail '(a b c d) 2)", "(c d)"), ("(list-ref '(a b c d) 2)", "c"),
            ("(let ((ls (list 'one 'two 'five!))) (list-set! ls 2 'three) ls)",
             "(one two three)"),
            ("(let* ((a (list 1 2)) (b (list-copy a))) (set-car! b 9) (list a b))",
             "((1 2) (9 2))"),
            ("(list-copy 5)", "5"),
        ])
        self.error("(length '(1 . 2))", "not a proper list")
        self.error("(list-ref '(1 2) 5)", "not a pair")

    def test_membership(self):
        self.checks([
            ("(memq 'a '(a b c))", "(a b c)"), ("(memq 'b '(a b c))", "(b c)"),
            ("(memq 'a '(b c d))", "#f"), ("(memq (list 'a) '(b (a) c))", "#f"),
            ("(member (list 'a) '(b (a) c))", "((a) c)"),
            ('(member "B" \'("a" "b" "c") string-ci=?)', '("b" "c")'),
            ("(memv 101 '(100 101 102))", "(101 102)"),
            ("(assq 'a '((a 1) (b 2)))", "(a 1)"), ("(assq 'd '((a 1)))", "#f"),
            ("(assoc (list 'a) '(((a)) ((b))))", "((a))"),
            ("(assoc 2.0 '((1 1) (2 4) (3 9)) =)", "(2 4)"),
            ("(assv 5 '((2 3) (5 7) (11 13)))", "(5 7)"),
        ])

    def test_map_for_each(self):
        self.checks([
            ("(map cadr '((a b) (d e) (g h)))", "(b e h)"),
            ("(map (lambda (n) (expt n n)) '(1 2 3 4 5))", "(1 4 27 256 3125)"),
            ("(map + '(1 2 3) '(10 20 30))", "(11 22 33)"),
            ("(map + '(1 2 3) '(10 20))", "(11 22)"),
            ("(let ((v (make-vector 5))) (for-each (lambda (i) (vector-set! v i (* i i)))"
             " '(0 1 2 3 4)) v)", "#(0 1 4 9 16)"),
            ("(let ((acc '())) (for-each (lambda (a b) (set! acc (cons (+ a b) acc)))"
             " '(1 2) '(10 20 30)) acc)", "(22 11)"),
            ("(apply + (list 3 4))", "7"), ("(apply + 1 2 '(3 4))", "10"),
            ("(apply list '())", "()"),
        ])


class SymbolCharTests(SchemeTestCase):
    def test_symbols(self):
        self.checks([
            ("(symbol? 'foo)", "#t"), ("(symbol? (car '(a b)))", "#t"),
            ('(symbol? "bar")', "#f"), ("(symbol? 'nil)", "#t"), ("(symbol? '())", "#f"),
            ("(symbol=? 'a 'a 'a)", "#t"), ("(symbol=? 'a 'b)", "#f"),
            ("(symbol->string 'flying-fish)", '"flying-fish"'),
            ('(string->symbol "mISSISSIppi")', "mISSISSIppi"),
            ('(eq? \'bitBlt (string->symbol "bitBlt"))', "#t"),
        ])

    def test_chars(self):
        self.checks([
            ("(char? #\\a)", "#t"), ("(char=? #\\a #\\a)", "#t"),
            ("(char<? #\\a #\\b #\\c)", "#t"), ("(char<? #\\a #\\c #\\b)", "#f"),
            ("(char-ci=? #\\a #\\A)", "#t"), ("(char-alphabetic? #\\a)", "#t"),
            ("(char-numeric? #\\1)", "#t"), ("(char-whitespace? #\\space)", "#t"),
            ("(char-upper-case? #\\A)", "#t"), ("(char-lower-case? #\\A)", "#f"),
            ("(digit-value #\\3)", "3"), ("(digit-value #\\x0664)", "4"),
            ("(digit-value #\\a)", "#f"), ("(char->integer #\\A)", "65"),
            ("(integer->char 955)", "#\\λ"), ("(char-upcase #\\a)", "#\\A"),
            ("(char-downcase #\\A)", "#\\a"), ("(char-foldcase #\\A)", "#\\a"),
            ("(char-upcase #\\ß)", "#\\ß"),
        ])


class StringTests(SchemeTestCase):
    def test_strings(self):
        self.checks([
            ('(string? "a")', "#t"), ("(make-string 3 #\\x)", '"xxx"'),
            ("(string #\\a #\\b)", '"ab"'), ('(string-length "abc")', "3"),
            ('(string-ref "abc" 1)', "#\\b"),
            ('(let ((s (make-string 3 #\\a))) (string-set! s 1 #\\b) s)', '"aba"'),
            ('(string=? "a" "a" "a")', "#t"), ('(string<? "abc" "abd")', "#t"),
            ('(string-ci=? "Strasse" "STRASSE")', "#t"), ('(string>? "b" "a")', "#t"),
            ('(string-upcase "abc")', '"ABC"'), ('(string-downcase "ABC")', '"abc"'),
            ('(string-foldcase "ABC")', '"abc"'), ('(substring "hello" 1 3)', '"el"'),
            ('(string-append "a" "b" "c")', '"abc"'), ("(string-append)", '""'),
            ('(string->list "abc")', "(#\\a #\\b #\\c)"),
            ('(string->list "abcd" 1 3)', "(#\\b #\\c)"),
            ("(list->string '(#\\a #\\b))", '"ab"'), ('(string-copy "hello" 2)', '"llo"'),
            ('(let ((a "12345") (b (string-copy "abcde"))) (string-copy! b 1 a 0 2) b)',
             '"a12de"'),
            ('(let ((s (make-string 4 #\\a))) (string-fill! s #\\z 1 3) s)', '"azza"'),
            ('(string-map char-upcase "abc")', '"ABC"'),
            ('(string-map (lambda (a b) (if (char<? a b) a b)) "adc" "bbbz")', '"abb"'),
            ('(let ((acc \'())) (string-for-each (lambda (c) (set! acc (cons c acc))) "ab") acc)',
             "(#\\b #\\a)"),
        ])
        self.error('(string-set! "literal" 0 #\\a)', "immutable")
        self.error('(string-ref "abc" 3)', "out of range")
        self.error('(substring "abc" 2 1)', "bad range")


class VectorTests(SchemeTestCase):
    def test_vectors(self):
        self.checks([
            ("(vector? #(1))", "#t"), ("(make-vector 2 'a)", "#(a a)"),
            ("(vector 'a 'b 'c)", "#(a b c)"), ("(vector-length #(1 2 3))", "3"),
            ("(vector-ref '#(1 1 2 3 5 8 13 21) 5)", "8"),
            ("(let ((v (vector 0 '(2 2 2 2) \"Anna\"))) (vector-set! v 1 '(\"Sue\" \"Sue\")) v)",
             '#(0 ("Sue" "Sue") "Anna")'),
            ("(vector->list '#(dah dah didah))", "(dah dah didah)"),
            ("(vector->list '#(dah dah didah) 1)", "(dah didah)"),
            ("(vector->list '#(dah dah didah) 1 2)", "(dah)"),
            ("(list->vector '(dididit dah))", "#(dididit dah)"),
            ("(string->vector \"ABC\")", "#(#\\A #\\B #\\C)"),
            ("(vector->string #(#\\1 #\\2 #\\3))", '"123"'),
            ("(vector-copy #(1 2 3) 1)", "#(2 3)"),
            ("(let ((a (vector 1 2 3 4 5)) (b (vector 10 20 30 40 50)))"
             " (vector-copy! b 1 a 0 2) b)", "#(10 1 2 40 50)"),
            ("(vector-append #(a b c) #(d e f))", "#(a b c d e f)"),
            ("(let ((a (vector 1 2 3 4 5))) (vector-fill! a 'smash 2 4) a)",
             "#(1 2 smash smash 5)"),
            ("(vector-map cadr '#((a b) (d e) (g h)))", "#(b e h)"),
            ("(vector-map + #(1 2) #(10 20 30))", "#(11 22)"),
            ("(let ((v (make-vector 5)))"
             " (vector-for-each (lambda (i) (vector-set! v i (* i i))) '#(0 1 2 3 4)) v)",
             "#(0 1 4 9 16)"),
        ])
        self.error("(vector-ref #(1 2) 2)", "out of range")

    def test_bytevectors(self):
        self.checks([
            ("(bytevector? #u8(1))", "#t"), ("(make-bytevector 2 12)", "#u8(12 12)"),
            ("(bytevector 1 3 5 1 3 5)", "#u8(1 3 5 1 3 5)"), ("(bytevector)", "#u8()"),
            ("(bytevector-u8-ref #u8(1 1 2 3 5 8 13 21) 5)", "8"),
            ("(let ((bv (bytevector 1 2 3 4))) (bytevector-u8-set! bv 1 3) bv)",
             "#u8(1 3 3 4)"),
            ("(bytevector-length #u8(1 2))", "2"),
            ("(bytevector-copy #u8(1 2 3 4 5) 2 4)", "#u8(3 4)"),
            ("(let ((a (bytevector 1 2 3 4 5)) (b (bytevector 10 20 30 40 50)))"
             " (bytevector-copy! b 1 a 0 2) b)", "#u8(10 1 2 40 50)"),
            ("(bytevector-append #u8(0 1 2) #u8(3 4 5))", "#u8(0 1 2 3 4 5)"),
            ("(utf8->string #u8(#x41))", '"A"'), ('(string->utf8 "λ")', "#u8(206 187)"),
        ])
        self.error("(bytevector 256)", "not a byte")


class ControlTests(SchemeTestCase):
    def test_procedure_p(self):
        self.checks([
            ("(procedure? car)", "#t"), ("(procedure? 'car)", "#f"),
            ("(procedure? (lambda (x) (* x x)))", "#t"),
            ("(procedure? '(lambda (x) (* x x)))", "#f"),
            ("(procedure? (case-lambda ((x) x)))", "#t"),
        ])

    def test_booleans(self):
        self.checks([
            ("(not #t)", "#f"), ("(not 3)", "#f"), ("(not (list 3))", "#f"),
            ("(not #f)", "#t"), ("(not '())", "#f"), ("(boolean? #f)", "#t"),
            ("(boolean? 0)", "#f"), ("(boolean=? #t #t)", "#t"),
            ("(boolean=? #f #f #t)", "#f"),
        ])

    def test_values(self):
        self.checks([
            ("(call-with-values (lambda () (values 4 5)) (lambda (a b) b))", "5"),
            ("(call-with-values * -)", "-1"),
            ("(call-with-values (lambda () (values)) list)", "()"),
            ("(+ 1 (values 2))", "3"),
        ])


if __name__ == "__main__":
    unittest.main()
