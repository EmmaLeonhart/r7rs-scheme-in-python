"""Stage 2 control: call/cc, dynamic-wind, exceptions, parameters, multiple
values. Many cases are the R7RS report's examples."""

import unittest

from helpers import SchemeTestCase


class ContinuationTests(SchemeTestCase):
    def test_escape(self):
        self.checks([
            ("(call-with-current-continuation (lambda (exit)"
             " (for-each (lambda (x) (if (negative? x) (exit x))) '(54 0 37 -3 245 19)) #t))",
             "-3"),
            ("(+ 1 (call/cc (lambda (k) (+ 10 (k 1)))))", "2"),
            ("(call/cc (lambda (k) 5))", "5"),
            ("(call/cc procedure?)", "#t"),
        ])

    def test_list_length_example(self):
        self.check("""
            (define list-length
              (lambda (obj)
                (call-with-current-continuation
                  (lambda (return)
                    (letrec ((r (lambda (obj)
                                  (cond ((null? obj) 0)
                                        ((pair? obj) (+ (r (cdr obj)) 1))
                                        (else (return #f))))))
                      (r obj))))))
            (list (list-length '(1 2 3 4)) (list-length '(a b . c)))""", "(4 #f)")

    def test_reentry(self):
        self.check("""
            (define r #f) (define n 0)
            (define x (+ 1 (call/cc (lambda (k) (set! r k) 1))))
            (set! n (+ n 1))
            (if (< n 3) (r n))
            (list x n)""", "(2 1)")
        # re-entering inside a single expression
        self.check("""
            (let ((k* #f) (count 0))
              (let ((v (call/cc (lambda (k) (set! k* k) 0))))
                (set! count (+ count 1))
                (if (< v 5) (k* (+ v 1)) (list v count))))""", "(5 6)")

    def test_generator(self):
        # each call records where to return to, then resumes the traversal
        self.check("""
            (define (make-gen lst)
              (define return #f)
              (define resume #f)
              (lambda ()
                (call/cc (lambda (r)
                  (set! return r)
                  (if resume
                      (resume #f)
                      (begin
                        (for-each (lambda (x)
                                    (call/cc (lambda (next)
                                               (set! resume next)
                                               (return x))))
                                  lst)
                        (return 'done)))))))
            (define g (make-gen '(a b c)))
            (let* ((x1 (g)) (x2 (g)) (x3 (g)) (x4 (g))) (list x1 x2 x3 x4))""",
                   "(a b c done)")

    def test_multiple_values_to_continuation(self):
        self.check("(call-with-values (lambda () (call/cc (lambda (k) (k 1 2)))) list)",
                   "(1 2)")
        self.check("(call-with-values (lambda () (call/cc (lambda (k) (k)))) list)", "()")

    def test_map_with_reentry(self):
        # map builds a fresh result, so re-entering a mapped continuation
        # does not disturb an earlier result
        self.check("""
            (let ((k* #f) (results '()))
              (let ((r (map (lambda (x)
                              (call/cc (lambda (k) (if (= x 2) (set! k* k)) x)))
                            '(1 2 3))))
                (set! results (cons r results))
                (if (= (length results) 1) (k* 20))
                results))""", "((1 20 3) (1 2 3))")


class DynamicWindTests(SchemeTestCase):
    def test_report_example(self):
        self.check("""
            (let ((path '()) (c #f))
              (let ((add (lambda (s) (set! path (cons s path)))))
                (dynamic-wind
                  (lambda () (add 'connect))
                  (lambda () (add (call-with-current-continuation
                                    (lambda (c0) (set! c c0) 'talk1))))
                  (lambda () (add 'disconnect)))
                (if (< (length path) 4)
                    (c 'talk2)
                    (reverse path))))""",
                   "(connect talk1 disconnect connect talk2 disconnect)")

    def test_value_and_order(self):
        self.check("""
            (let ((log '()))
              (define (note x) (set! log (cons x log)))
              (let ((v (dynamic-wind (lambda () (note 'in))
                                     (lambda () (note 'body) 'result)
                                     (lambda () (note 'out)))))
                (list v (reverse log))))""", "(result (in body out))")

    def test_escape_runs_after(self):
        self.check("""
            (let ((log '()))
              (call/cc (lambda (k)
                (dynamic-wind (lambda () (set! log (cons 'before log)))
                              (lambda () (k 'escaped))
                              (lambda () (set! log (cons 'after log))))))
              (reverse log))""", "(before after)")

    def test_nested(self):
        self.check("""
            (let ((log '()))
              (define (note x) (set! log (cons x log)))
              (call/cc (lambda (k)
                (dynamic-wind
                  (lambda () (note 'a-in))
                  (lambda () (dynamic-wind (lambda () (note 'b-in))
                                           (lambda () (k 0))
                                           (lambda () (note 'b-out))))
                  (lambda () (note 'a-out)))))
              (reverse log))""", "(a-in b-in b-out a-out)")

    def test_error_unwinds(self):
        self.check("""
            (let ((log '()))
              (guard (e (#t (set! log (cons 'handled log))))
                (dynamic-wind (lambda () (set! log (cons 'in log)))
                              (lambda () (raise 'oops))
                              (lambda () (set! log (cons 'out log)))))
              (reverse log))""", "(in out handled)")


class ExceptionTests(SchemeTestCase):
    def test_report_examples(self):
        self.check("""
            (call-with-current-continuation
              (lambda (k)
                (with-exception-handler
                  (lambda (e) (k (list 'condition e)))
                  (lambda () (+ 1 (raise 'an-error))))))""", "(condition an-error)")
        self.check("""
            (with-exception-handler
              (lambda (con) (cond ((string? con) 'was-a-string) (else 'other)) 42)
              (lambda () (+ (raise-continuable "should be a number") 23)))""",
                   "65")
        self.checks([
            ("(guard (con ((assq 'a con) => cdr) ((assq 'b con)))"
             " (raise (list (cons 'a 42))))", "42"),
            ("(guard (con ((assq 'a con) => cdr) ((assq 'b con)))"
             " (raise (list (cons 'b 23))))", "(b . 23)"),
        ])

    def test_handler_returning_from_raise_is_an_error(self):
        self.error("(with-exception-handler (lambda (e) 0) (lambda () (raise 'boom)))",
                   "handler returned")

    def test_uncaught(self):
        self.error("(raise 'boom)", "non-condition object raised: boom")
        self.error("(guard (e ((string? e) 'no)) (raise 'boom))", "boom")

    def test_error_objects(self):
        self.checks([
            ('(guard (e ((error-object? e) (list (error-object-message e)'
             ' (error-object-irritants e)))) (error "bad thing" 1 \'two))',
             '("bad thing" (1 two))'),
            ("(guard (e ((symbol? e) e)) (raise 'sym))", "sym"),
            ("(guard (e ((error-object? e) 'primitive-error)) (car 5))", "primitive-error"),
            ("(guard (e ((error-object? e) (error-object-message e))) (vector-ref #(1) 3))",
             '"vector-ref: index out of range"'),
            ("(guard (e (#t 'zero)) (/ 1 0))", "zero"),
            ("(guard (e ((error-object? e) 'unbound)) undefined-variable-xyz)", "unbound"),
            ("(guard (e (else (list 'else e))) (raise 1))", "(else 1)"),
            ("(guard (e ((read-error? e) 'read) ((file-error? e) 'file) (else 'other))"
             " (error \"x\"))", "other"),
        ])

    def test_handler_stack(self):
        self.check("""
            (with-exception-handler
              (lambda (e) (list 'outer e))
              (lambda ()
                (with-exception-handler
                  (lambda (e) (raise-continuable (list 'inner e)))
                  (lambda () (raise-continuable 'x)))))""", "(outer (inner x))")
        # guard re-raises in the original dynamic environment
        self.check("""
            (with-exception-handler
              (lambda (e) 10)
              (lambda ()
                (guard (e ((string? e) 'no))
                  (+ 1 (raise-continuable 'c)))))""", "11")

    def test_guard_body_and_values(self):
        self.check("(guard (e (#t 'x)) (define a 1) (+ a 1))", "2")
        self.check("(call-with-values (lambda () (guard (e (#t 'x)) (values 1 2))) list)",
                   "(1 2)")


class ParameterTests(SchemeTestCase):
    def test_parameters(self):
        self.check("""
            (define radix (make-parameter 10 (lambda (x)
              (if (and (exact-integer? x) (<= 2 x 16)) x (error "invalid radix")))))
            (define (f n) (number->string n (radix)))
            (list (f 12) (parameterize ((radix 2)) (f 12)) (f 12))""",
                   '("12" "1100" "12")')
        self.error("""
            (define radix (make-parameter 10 (lambda (x)
              (if (and (exact-integer? x) (<= 2 x 16)) x (error "invalid radix")))))
            (parameterize ((radix 0)) 1)""", "invalid radix")
        self.check("(define p (make-parameter 1)) (parameterize ((p 2))"
                   " (parameterize ((p 3)) (p)))", "3")

    def test_parameter_and_continuations(self):
        # re-entering a parameterize body restores its binding
        self.check("""
            (define p (make-parameter 'outer))
            (let ((k* #f) (log '()))
              (parameterize ((p 'inner))
                (call/cc (lambda (k) (set! k* k)))
                (set! log (cons (p) log)))
              (set! log (cons (p) log))
              (if (< (length log) 4) (k* #f))
              (reverse log))""", "(inner outer inner outer)")


class ValuesFormTests(SchemeTestCase):
    def test_let_values(self):
        self.checks([
            ("(let-values (((root rem) (exact-integer-sqrt 32))) (* root rem))", "35"),
            ("(let ((a 'a) (b 'b) (x 'x) (y 'y)) (let*-values (((a b) (values x y))"
             " ((x y) (values a b))) (list a b x y)))", "(x y x y)"),
            ("(let-values (((a . rest) (values 1 2 3)) (all (values 4 5))) (list a rest all))",
             "(1 (2 3) (4 5))"),
            ("(let ((a 1)) (let-values (((a) (values 2)) ((b) (values a))) (list a b)))",
             "(2 1)"),
            ("(let-values () 5)", "5"),
        ])

    def test_define_values(self):
        self.check("(define-values (q r) (floor/ 17 5)) (list q r)", "(3 2)")
        self.check("(define (f) (define-values (x y . z) (values 1 2 3 4)) (list x y z)) (f)",
                   "(1 2 (3 4))")
        self.check("(define-values all (values 1 2)) all", "(1 2)")
        self.check("(let () (define-values (x y) (values 1 2)) (+ x y))", "3")


if __name__ == "__main__":
    unittest.main()
