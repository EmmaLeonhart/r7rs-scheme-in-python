"""Tests specific to the bytecode VM: the specialized opcodes and their
fallbacks, calls between VM and interpreter procedures, and re-entering
continuations through VM frames. These always run on the VM, whatever
TULIP_ENGINE says; where it helps, results are compared with the
interpreter's."""

import unittest

from helpers import write_string, Runtime, SchemeError

from tulip import vm
from tulip.reader import Reader


def run_both(src):
    out = []
    for engine in ("interp", "vm"):
        try:
            out.append(write_string(Runtime(engine=engine).eval_string(src)))
        except SchemeError as e:
            out.append("error: %s" % e)
    return out


def chain_length(k):
    n = 0
    while k is not None:
        n += 1
        k = k.next
    return n


class VMTestCase(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime(engine="vm")

    def w(self, src):
        return write_string(self.rt.eval_string(src))

    def same(self, src):
        interp, vm_ = run_both(src)
        self.assertEqual(vm_, interp, src)
        return vm_

    def ops_of(self, src):
        """Every opcode name in the compiled code of ``src`` (one form),
        nested lambdas included."""
        node = self.rt.expander_for(self.rt.env).expand_toplevel(Reader(src).read())
        names, todo = [], [vm.compile_toplevel(node)]
        while todo:
            code = todo.pop()
            for op, a in zip(code.ops, code.args):
                names.append(vm.OPNAMES[op])
                if isinstance(a, vm.VMCode):
                    todo.append(a)
        return names


class FastOpTests(VMTestCase):
    def test_hot_builtins_compile_to_fast_ops(self):
        ops = self.ops_of("(lambda (a b) (if (< a b) (+ a b) (car (cons a b))))")
        for name in ("LT", "ADD", "CAR", "CONS"):
            self.assertIn(name, ops)
        self.assertIn("PRIM", self.ops_of("(lambda (v) (vector-ref v 0))"))
        # wrong arity is an ordinary call, so the error comes at run time
        self.assertNotIn("CAR", self.ops_of("(lambda () (car 1 2))"))

    def test_non_fixnum_operands(self):
        for src in ["(+ 1/2 1/3)", "(- 1.5 2)", "(< 1 2.5)", "(>= 3/2 1.5)",
                    "(= 1 1.0)", "(zero? 0.0)", "(zero? 1/2)", "(+ (expt 2 70) 1)",
                    "(eq? '() '())", "(eq? 'a 'a)", "(eq? (list 1) (list 1))",
                    "(not 0)", "(null? '())", "(pair? '())", "(+ #t 1)", "(car 5)",
                    "(cdr '())", "(< 'a 1)", "(zero? \"0\")"]:
            with self.subTest(src=src):
                self.same(src)

    def test_errors_from_fast_ops_reach_guard(self):
        self.same("(guard (e ((error-object? e) (error-object-message e))"
                  "          (#t 'other))"
                  "  (+ 1 (car 5)))")
        self.assertEqual(self.w("(guard (e (#t 'caught)) (list 1 (< 'a 1)))"), "caught")


class FallbackTests(VMTestCase):
    """A call compiled to a fast op checks at run time that the global still
    holds the built-in; ``my+`` and friends are globals that start out holding
    one and are changed later."""

    def test_alias_compiles_to_fast_op_then_falls_back(self):
        self.rt.eval_string("(define my+ +) (define my-car car) (define my-list list)")
        self.assertIn("ADD", self.ops_of("(define (f a b) (my+ a b))"))
        self.assertEqual(self.w(
            "(define (f a b) (my+ a b))"
            "(define (g x) (my-car x))"
            "(define (h a b) (my-list a b))"
            "(list (f 1 2) (g '(7)) (h 1 2))"), "(3 7 (1 2))")
        self.assertEqual(self.w(
            "(set! my+ (lambda (a b) (list 'plus a b)))"
            "(set! my-car string-length)"
            "(set! my-list vector)"
            "(list (f 1 2) (g \"abc\") (h 1 2))"), "((plus 1 2) 3 #(1 2))")
        self.rt.eval_string("(set! my+ 5)")
        with self.assertRaises(SchemeError):
            self.rt.eval_string("(f 1 2)")

    def test_fallback_in_tail_position_is_a_tail_call(self):
        # one alias per kind of opcode: FAST1, FAST2 and PRIM
        cases = [("not", "(alias n)", "(lambda (n) (loop (- n 1)))"),
                 ("+", "(alias n n)", "(lambda (n m) (loop (- n 1)))"),
                 ("list", "(alias n n n)", "(lambda (n m o) (loop (- n 1)))")]
        for builtin, call, replacement in cases:
            with self.subTest(op=builtin):
                self.rt.eval_string(
                    "(define alias %s)"
                    "(define (loop n)"
                    "  (if (= n 0) (call/cc (lambda (k) k)) %s))"
                    "(set! alias %s)" % (builtin, call, replacement))
                k = self.rt.eval_string("(loop 20000)")
                # the loop ran 20000 times; a non-tail fallback would have
                # left one frame per iteration
                self.assertLess(chain_length(k.k), 20)

    def test_interp_engine_agrees_on_fallback(self):
        src = ("(define my* *)"
               "(define (sq x) (my* x x))"
               "(define a (sq 5))"
               "(set! my* +)"
               "(list a (sq 5))")
        self.assertEqual(self.same(src), "(25 10)")


class InteropTests(VMTestCase):
    def define_with(self, engine, src):
        saved = self.rt.engine
        self.rt.engine = engine
        try:
            self.rt.eval_string(src)
        finally:
            self.rt.engine = saved

    def test_vm_calls_interpreter_closures_and_back(self):
        self.define_with("interp", "(define (twice f x) (f (f x)))"
                                   "(define (count-down n) (if (= n 0) 'done (vm-step n)))")
        self.rt.eval_string("(define (vm-step n) (count-down (- n 1)))")
        self.assertEqual(self.w("(twice (lambda (y) (* y 2)) 5)"), "20")
        self.assertEqual(self.w("(map (lambda (p) (twice p 1)) (list (lambda (x) (+ x 1)) -))"),
                         "(3 1)")
        # mutual tail recursion across the two engines runs in constant space
        self.assertEqual(self.w("(count-down 50000)"), "done")

    def test_escape_through_interpreter_frames(self):
        self.define_with("interp", "(define (call-each f lst) (for-each f lst) 'finished)")
        self.assertEqual(self.w(
            "(call/cc (lambda (k)"
            "  (call-each (lambda (x) (if (> x 2) (k (list 'escaped x)))) '(1 2 3 4))))"),
            "(escaped 3)")
        self.assertEqual(self.w(
            "(guard (e ((symbol? e) (list 'caught e)))"
            "  (call-each (lambda (x) (if (= x 2) (raise 'two))) '(1 2 3)))"),
            "(caught two)")

    def test_dynamic_wind_across_engines(self):
        self.define_with("interp", "(define (with-log log thunk)"
                                   "  (dynamic-wind (lambda () (set-car! log (cons 'in (car log))))"
                                   "                thunk"
                                   "                (lambda () (set-car! log (cons 'out (car log))))))")
        self.assertEqual(self.w(
            "(let ((log (list '())))"
            "  (call/cc (lambda (k) (with-log log (lambda () (k 1)))))"
            "  (reverse (car log)))"), "(in out)")


class ReentryTests(VMTestCase):
    def test_reentry_restores_pending_operands(self):
        src = ("(let ((k #f) (count 0) (results '()))"
               "  (let ((v (list 1 2 (call/cc (lambda (c) (set! k c) 0)) 4)))"
               "    (set! results (cons v results))"
               "    (set! count (+ count 1))"
               "    (if (< count 3) (k (* count 10)) (reverse results))))")
        self.assertEqual(self.same(src), "((1 2 0 4) (1 2 10 4) (1 2 20 4))")

    def test_reentry_through_fast_op_and_nested_frames(self):
        src = ("(define saved #f)"
               "(define (inner) (+ 100 (call/cc (lambda (c) (set! saved c) 1))))"
               "(define (outer) (* 2 (inner)))"
               "(define seen '())"
               "(let ((r (outer)))"
               "  (set! seen (cons r seen))"
               "  (if (< (length seen) 3) (saved (length seen)) (reverse seen)))")
        self.assertEqual(self.same(src), "(202 202 204)")

    def test_generator_by_reentry(self):
        src = ("(define (make-gen lst)"
               "  (define return #f)"
               "  (define resume #f)"
               "  (lambda ()"
               "    (call/cc (lambda (r)"
               "      (set! return r)"
               "      (if resume"
               "          (resume #f)"
               "          (begin"
               "            (for-each (lambda (x)"
               "                        (call/cc (lambda (next) (set! resume next) (return x))))"
               "                      lst)"
               "            (return 'eof)))))))"
               "(define g (make-gen '(a b c)))"
               "(let loop ((acc '()))"
               "  (let ((x (g)))"
               "    (if (eq? x 'eof) (reverse acc) (loop (cons x acc)))))")
        self.assertEqual(self.same(src), "(a b c)")


if __name__ == "__main__":
    unittest.main()
