"""syntax-rules, define-syntax, let-syntax, letrec-syntax, and hygiene."""

import unittest

from helpers import SchemeTestCase


class SyntaxRulesTests(SchemeTestCase):
    def test_basic(self):
        self.check("(define-syntax swap! (syntax-rules () ((_ a b)"
                   " (let ((tmp a)) (set! a b) (set! b tmp)))))"
                   " (define x 1) (define y 2) (swap! x y) (list x y)", "(2 1)")

    def test_recursive_macro(self):
        self.check("""
            (define-syntax my-or (syntax-rules ()
              ((_) #f) ((_ e) e)
              ((_ e r ...) (let ((t e)) (if t t (my-or r ...))))))
            (list (my-or) (my-or #f 3) (my-or #f #f))""", "(#f 3 #f)")

    def test_patterns(self):
        self.check("(define-syntax tail (syntax-rules () ((_ a ... b) '(b a ...))))"
                   " (tail 1 2 3 4)", "(4 1 2 3)")
        self.check("(define-syntax mid (syntax-rules () ((_ a b ... c d) '(a (b ...) c d))))"
                   " (list (mid 1 2 3) (mid 1 2 3 4 5))", "((1 () 2 3) (1 (2 3) 4 5))")
        self.check("(define-syntax dot (syntax-rules () ((_ a . b) 'b))) (dot 1 2 3)",
                   "(2 3)")
        self.check("(define-syntax dt (syntax-rules () ((_ a ... . r) '((a ...) r))))"
                   " (dt 1 2 . 3)", "((1 2) 3)")
        self.check("(define-syntax vec (syntax-rules () ((_ #(a ...)) (list a ...))))"
                   " (vec #(1 2 3))", "(1 2 3)")
        self.check("(define-syntax vt (syntax-rules () ((_ a ...) #(a ... end))))"
                   " (vt 1 2)", "#(1 2 end)")
        self.check("(define-syntax nest (syntax-rules () ((_ (a b ...) ...) '((b ... a) ...))))"
                   " (nest (1 2 3) (4 5))", "((2 3 1) (5 4))")
        self.check("(define-syntax flat (syntax-rules () ((_ (a ...) ...) '(a ... ...))))"
                   " (flat (1 2) (3) ())", "(1 2 3)")
        self.check("(define-syntax ign (syntax-rules () ((_ _ x _) x))) (ign 1 2 3)", "2")
        self.check("(define-syntax num (syntax-rules () ((_ 1 x) 'one) ((_ y x) 'other)))"
                   " (list (num 1 a) (num 2 a))", "(one other)")
        self.check("(define-syntax const (syntax-rules () ((_ x ...) (list 'x ...))))"
                   " (const a b)", "(a b)")

    def test_non_ellipsis_var_repeated(self):
        self.check("(define-syntax pairs (syntax-rules () ((_ k v ...) '((k v) ...))))"
                   " (pairs x 1 2 3)", "((x 1) (x 2) (x 3))")

    def test_literals(self):
        self.check("""
            (define-syntax lit (syntax-rules (key) ((_ key) 'matched) ((_ other) 'nope)))
            (list (lit key) (lit foo) (let ((key 1)) (lit key)))""", "(matched nope nope)")
        self.check("""
            (define-syntax my-if (syntax-rules (then else)
              ((_ c then t else e) (if c t e))))
            (my-if #f then 1 else 2)""", "2")

    def test_custom_ellipsis_and_escape(self):
        self.check("(define-syntax my-elli (syntax-rules ::: () ((_ x :::) (list x :::))))"
                   " (my-elli 1 2 3)", "(1 2 3)")
        self.check("""
            (define-syntax be-like-begin
              (syntax-rules ()
                ((be-like-begin name)
                 (define-syntax name
                   (syntax-rules ()
                     ((name expr (... ...)) (begin expr (... ...))))))))
            (be-like-begin sequence)
            (sequence 1 2 3 4)""", "4")
        self.check("(define-syntax q (syntax-rules () ((_) '(... ...)))) (q)", "...")

    def test_no_match(self):
        self.error("(define-syntax one (syntax-rules () ((_ x) x))) (one 1 2)",
                   "no syntax-rules pattern matches")

    def test_macro_defining_definitions(self):
        self.check("""
            (define-syntax def-getter (syntax-rules ()
              ((_ name val) (define (name) val))))
            (def-getter get-five 5)
            (get-five)""", "5")


class HygieneTests(SchemeTestCase):
    def test_introduced_binding_does_not_capture(self):
        self.check("""
            (define-syntax my-or2 (syntax-rules ()
              ((_ a b) (let ((t a)) (if t t b)))))
            (let ((t 5)) (my-or2 #f t))""", "5")

    def test_free_identifier_refers_to_definition_site(self):
        self.check("""
            (define-syntax my-if2 (syntax-rules () ((_ c a b) (cond (c a) (else b)))))
            (let ((if list) (cond 'shadowed) (else #f)) (my-if2 #f 1 2))""", "2")
        self.check("""
            (let ((x 'outer))
              (define-syntax m (syntax-rules () ((_) x)))
              (let ((x 'inner)) (m)))""", "outer")
        self.check("(define (g x) (define-syntax getx (syntax-rules () ((_) x)))"
                   " (let ((x 100)) (getx))) (g 5)", "5")

    def test_report_let_syntax_example(self):
        self.check("""
            (let-syntax ((given-that (syntax-rules ()
                            ((_ test stmt1 stmt2 ...) (if test (begin stmt1 stmt2 ...))))))
              (let ((if #t))
                (given-that if (set! if 'now))
                if))""", "now")
        self.check("""
            (let ((x 'outer))
              (let-syntax ((m (syntax-rules () ((m) x))))
                (let ((x 'inner))
                  (m))))""", "outer")

    def test_report_letrec_syntax_example(self):
        self.check("""
            (letrec-syntax
                ((my-or (syntax-rules ()
                          ((my-or) #f)
                          ((my-or e) e)
                          ((my-or e1 e2 ...)
                           (let ((temp e1)) (if temp temp (my-or e2 ...)))))))
              (let ((x #f) (y 7) (temp 8) (let odd?) (if even?))
                (my-or x (let temp) (if y) y)))""", "7")

    def test_cond_literals_by_binding(self):
        self.check("(let ((=> #f)) (cond (#t => 'ok)))", "ok")

    def test_internal_define_syntax(self):
        self.check("(define (f x) (define-syntax double (syntax-rules () ((_ e) (* 2 e))))"
                   " (double x)) (f 5)", "10")
        self.check("""
            (define (f)
              (define-syntax def2 (syntax-rules () ((_ a b v) (begin (define a v) (define b v)))))
              (def2 p q 3)
              (+ p q))
            (f)""", "6")


if __name__ == "__main__":
    unittest.main()
