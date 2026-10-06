"""Special forms, derived forms, tail calls and hygiene of the built-in
derived forms."""

import unittest

from helpers import SchemeTestCase


class CoreFormTests(SchemeTestCase):
    def test_basics(self):
        self.checks([
            ("(quote (a b))", "(a b)"),
            ("'#(a b)", "#(a b)"),
            ("#(1 2)", "#(1 2)"),
            ('"abc"', '"abc"'),
            ("(if #f 1 2)", "2"),
            ("(if '() 1 2)", "1"),
            ("(if 0 1 2)", "1"),
            ("((lambda (x y) (+ x y)) 1 2)", "3"),
            ("((lambda x x) 1 2)", "(1 2)"),
            ("((lambda (a . r) r) 1 2 3)", "(2 3)"),
            ("(begin 1 2 3)", "3"),
            ("(let ((x 1)) (set! x 2) x)", "2"),
        ])

    def test_define(self):
        self.check("(define x 10) x", "10")
        self.check("(define (f a b) (- a b)) (f 5 3)", "2")
        self.check("(define (g . r) r) (g 1 2)", "(1 2)")
        self.check("(define ((curried a) b) (list a b)) ((curried 1) 2)", "(1 2)")
        self.check("(define x 1) (set! x (+ x 1)) x", "2")

    def test_internal_defines(self):
        self.check("(define (f) (define a 1) (define (g) (+ a 1)) (g)) (f)", "2")
        self.check("(define (f) (define (ev? n) (if (= n 0) #t (od? (- n 1))))"
                   " (define (od? n) (if (= n 0) #f (ev? (- n 1)))) (ev? 100)) (f)",
                   "#t")
        self.check("(let () (begin (define a 1) (define b 2)) (+ a b))", "3")
        self.error("(define (f) (define a b) (define b 1) a) (f)", "before its definition")

    def test_closures(self):
        self.check("(define (counter) (let ((n 0)) (lambda () (set! n (+ n 1)) n)))"
                   " (define c (counter)) (c) (c) (c)", "3")
        self.check("(define (adder n) (lambda (x) (+ x n))) ((adder 5) 10)", "15")
        self.check("(((lambda (a) (lambda (b) (lambda (c) (list a b c)))) 1) 2)"
                   " ", "#<procedure anonymous>")
        self.check("((((lambda (a) (lambda (b) (lambda (c) (list a b c)))) 1) 2) 3)",
                   "(1 2 3)")

    def test_errors(self):
        self.error("undefined-variable", "unbound variable")
        self.error("(car '())", "not a pair")
        self.error("((lambda (x) x))", "wrong number of arguments")
        self.error("(1 2)", "not a procedure")
        self.error("(if)", "syntax error")
        self.error("(set! undefined-thing 1)", "unbound")
        self.error("()", "empty combination")
        self.error("(error \"boom\" 1 2)", "boom 1 2")
        self.error("(let ((x 1) (x 2)) x)", "duplicate parameter")


class DerivedFormTests(SchemeTestCase):
    def test_let_family(self):
        self.checks([
            ("(let ((x 1) (y 2)) (+ x y))", "3"),
            ("(let () 5)", "5"),
            ("(let ((x 1)) (let ((x 2) (y x)) y))", "1"),
            ("(let* ((x 1) (y (+ x 1))) (list x y))", "(1 2)"),
            ("(let* () 7)", "7"),
            ("(letrec ((even? (lambda (n) (if (= n 0) #t (odd? (- n 1)))))"
             " (odd? (lambda (n) (if (= n 0) #f (even? (- n 1)))))) (even? 101))", "#f"),
            ("(letrec* ((a 1) (b (+ a 1))) b)", "2"),
            ("(let loop ((i 0) (acc '())) (if (= i 3) acc (loop (+ i 1) (cons i acc))))",
             "(2 1 0)"),
        ])

    def test_named_let_scope(self):
        # the loop name is not visible in the init expressions
        self.check("(define (loop x) 'outer) (let loop ((x (loop 1))) x)", "outer")

    def test_cond_case(self):
        self.checks([
            ("(cond ((> 3 2) 'greater) ((< 3 2) 'less))", "greater"),
            ("(cond ((> 3 3) 'greater) ((< 3 3) 'less) (else 'equal))", "equal"),
            ("(cond ((assv 'b '((a 1) (b 2))) => cadr) (else #f))", "2"),
            ("(cond (#f 1))", ""),
            ("(cond (5))", "5"),
            ("(case (* 2 3) ((2 3 5 7) 'prime) ((1 4 6 8 9) 'composite))", "composite"),
            ("(case (car '(c d)) ((a e i o u) 'vowel) ((w y) 'semivowel)"
             " (else => (lambda (x) x)))", "c"),
            ("(case 'x ((x) => (lambda (s) (list s s))) (else 'no))", "(x x)"),
            ("(case 1.0 ((1) 'exact) (else 'other))", "other"),
        ])

    def test_and_or_when_unless(self):
        self.checks([
            ("(and 1 2 'c '(f g))", "(f g)"),
            ("(and)", "#t"),
            ("(and 1 #f 3)", "#f"),
            ("(or (= 2 2) (> 2 1))", "#t"),
            ("(or #f #f #f)", "#f"),
            ("(or (memq 'b '(a b c)) (/ 3 0))", "(b c)"),
            ("(or)", "#f"),
            ("(when (> 1 0) 'a 'b)", "b"),
            ("(unless (> 1 0) 'a 'b)", ""),
            ("(unless #f 'x)", "x"),
        ])

    def test_do(self):
        self.check("(do ((vec (make-vector 5)) (i 0 (+ i 1))) ((= i 5) vec)"
                   " (vector-set! vec i i))", "#(0 1 2 3 4)")
        self.check("(let ((x '(1 3 5 7 9))) (do ((x x (cdr x)) (sum 0 (+ sum (car x))))"
                   " ((null? x) sum)))", "25")

    def test_quasiquote(self):
        self.checks([
            ("`(list ,(+ 1 2) 4)", "(list 3 4)"),
            ("(let ((name 'a)) `(list ,name ',name))", "(list a 'a)"),
            ("`(a ,(+ 1 2) ,@(map abs '(4 -5 6)) b)", "(a 3 4 5 6 b)"),
            ("`(( foo ,(- 10 3)) ,@(cdr '(c)) . ,(car '(cons)))", "((foo 7) . cons)"),
            ("`#(10 5 ,(sqrt 4) ,@(map sqrt '(16 9)) 8)", "#(10 5 2 4 3 8)"),
            ("(let ((foo '(foo bar)) (@baz 'baz)) `(list ,@foo , @baz))",
             "(list foo bar baz)"),
            ("`(a `(b ,(c ,(+ 1 2))))", "(a `(b ,(c 3)))"),
            ("`(a `(b ,(c) ,(foo ,(+ 1 3) d) e) f)",
             "(a `(b ,(c) ,(foo 4 d) e) f)"),
            ("(let ((name1 'x) (name2 'y)) `(a `(b ,,name1 ,',name2 d) e))",
             "(a `(b ,x ,'y d) e)"),
            ("`(1 ,@'() 2)", "(1 2)"),
            ("`x", "x"),
            ("`5", "5"),
        ])

    def test_delay(self):
        self.checks([
            ("(force (delay (+ 1 2)))", "3"),
            ("(let ((p (delay (+ 1 2)))) (list (force p) (force p)))", "(3 3)"),
            ("(force (make-promise 5))", "5"),
            ("(promise? (delay 1))", "#t"),
            ("(force 7)", "7"),
        ])
        self.check("""
            (define count 0)
            (define p (delay (begin (set! count (+ count 1))
                                    (if (> count x) count (force p)))))
            (define x 5)
            (list (force p) (begin (set! x 10) (force p)))""", "(6 6)")
        # delay-force chains run in constant space
        self.check("""
            (define (loop n) (delay-force (if (= n 0) (delay 'done) (loop (- n 1)))))
            (force (loop 100000))""", "done")

    def test_case_lambda(self):
        self.check("""
            (define range (case-lambda ((e) (range 0 e))
                                       ((b e) (do ((r '() (cons e r)) (e (- e 1) (- e 1)))
                                                  ((< e b) r)))))
            (list (range 3) (range 3 5))""", "((0 1 2) (3 4))")
        self.error("((case-lambda ((a) a)) 1 2)", "wrong number of arguments")

    def test_records(self):
        self.check("""
            (define-record-type <pare> (kons x y) pare? (x kar set-kar!) (y kdr))
            (define k (kons 1 2))
            (set-kar! k 3)
            (list (pare? k) (pare? 5) (kar k) (kdr k))""", "(#t #f 3 2)")
        self.error("(define-record-type point (mk x) point? (x px)) (px 5)", "not a")


class HygieneTests(SchemeTestCase):
    def test_derived_forms_ignore_local_rebinding(self):
        self.checks([
            ("(let ((if list)) (cond (#t 1) (else 2)))", "1"),
            ("(let ((let 5) (lambda 6)) (let* ((x 1)) (+ x let lambda)))", "12"),
            ("(let ((cons list)) `(1 ,@(list 2)))", "(1 2)"),
            ("(let ((t 5)) (or #f t))", "5"),
            ("(let ((memv (lambda args #f))) (case 1 ((1) 'one) (else 'other)))", "one"),
        ])

    def test_local_shadowing_of_keywords(self):
        self.check("(let ((if (lambda (a b c) 'shadowed))) (if #t 1 2))", "shadowed")
        self.check("(define (f quote) (quote 1)) (f -)", "-1")
        self.check("(let ((else #f)) (cond (else 'is-a-variable)))", "")


class TailCallTests(SchemeTestCase):
    def test_tail_positions(self):
        n = 200000
        self.checks([
            ("(let loop ((i 0)) (if (< i %d) (loop (+ i 1)) i))" % n, str(n)),
            ("(define (f i) (cond ((= i %d) 'done) (else (f (+ i 1))))) (f 0)" % n, "done"),
            ("(define (f i) (and #t (if (= i %d) 'done (f (+ i 1))))) (f 0)" % n, "done"),
            ("(define (f i) (or #f (if (= i %d) 'done (f (+ i 1))))) (f 0)" % n, "done"),
            ("(define (f i) (when #t (if (= i %d) 'done (f (+ i 1))))) (f 0)" % n, "done"),
            ("(define (f i) (case i ((%d) 'done) (else (f (+ i 1))))) (f 0)" % n, "done"),
            ("(define (f i) (let* ((j (+ i 1))) (if (= j %d) 'done (f j)))) (f 0)" % n,
             "done"),
            ("(define (f i) (apply (if (= i %d) (lambda (x) 'done) f) (list (+ i 1))))"
             " (f 0)" % n, "done"),
            ("(do ((i 0 (+ i 1))) ((= i %d) 'done))" % n, "done"),
        ])

    def test_mutual_recursion(self):
        self.check("(define (ev? n) (if (= n 0) #t (od? (- n 1))))"
                   " (define (od? n) (if (= n 0) #f (ev? (- n 1)))) (ev? 300001)", "#f")

    def test_long_and_circular_literals(self):
        # quoted data used to be walked recursively by the expander, so long
        # and circular literals raised RecursionError (found by the
        # conformance suite)
        self.check("(length '(%s))" % " ".join(["1"] * 5000), "5000")
        self.check("(let ((x '#1=(a b . #1#))) (eq? x (cddr x)))", "#t")
        self.check("(let ((v '#0=#(1 #0#))) (eq? v (vector-ref v 1)))", "#t")
        self.check("(let-syntax ((m (syntax-rules () ((_) '(%s)))))"
                   "  (length (m)))" % " ".join(["1"] * 3000), "3000")

    def test_deep_non_tail_recursion(self):
        # grows the heap continuation, not the Python stack
        self.check("(define (count n) (if (= n 0) 0 (+ 1 (count (- n 1))))) (count 300000)",
                   "300000")
        self.check("(length (map (lambda (x) x) (make-list 100000 0)))", "100000")


if __name__ == "__main__":
    unittest.main()
