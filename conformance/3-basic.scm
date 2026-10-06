;; R7RS-small chapter 3: basic concepts.
;; "It is an error" situations are not tested: the report does not require
;; them to be signalled.
(import (scheme base) (scheme read) (scheme write)
        (scheme case-lambda) (conformance test))

(define (read-from s) (read (open-input-string s)))

(section "3.1 Variables, syntactic keywords, and regions")
(define x 'outer)
(test 'inner (let ((x 'inner)) x))
(test 'outer (begin (let ((x 'inner)) x) x))
(test '(inner outer) (list ((lambda (x) x) 'inner) x))
(test 'innermost (let ((x 'a)) (let ((x 'innermost)) x)))
;; an identifier bound as a variable shadows a syntactic keyword
(test '(1 2) (let ((if list)) (if 1 2)))
(test 3 (let ((quote -)) (quote 5 2)))
;; referring to an unbound variable is an error (signalled here)
(test-error (let () this-variable-is-not-bound))

(section "3.2 Disjointness of types")
(define-record-type point (make-point x y) point? (x point-x) (y point-y))
(define predicates
  (list boolean? bytevector? char? eof-object? null? number? pair?
        port? procedure? string? symbol? vector? point?))
(define samples
  (list #t #f (bytevector 1) #\a (eof-object) '() 0 1.5 (cons 1 2)
        (current-output-port) car (lambda (x) x) "s" 'sym (vector 1)
        (make-point 1 2) (make-bytevector 0) "" (vector)))
(for-each
 (lambda (obj)
   (test 1 (let loop ((ps predicates) (n 0))
             (if (null? ps) n (loop (cdr ps) (if ((car ps) obj) (+ n 1) n))))))
 samples)
;; only #f is false
(test '(yes yes yes yes yes no)
      (map (lambda (v) (if v 'yes 'no)) (list 0 '() "" (vector) 'nil #f)))

(section "3.3 External representations")
(test 28 (read-from "28"))
(test 28 (read-from "#e28.000"))
(test 28 (read-from "#x1c"))
(test '(8 13) (read-from "( 08 13 )"))
(test '(8 13) (read-from "(8 . (13 . ()))"))
(test '(+ 2 6) (read-from "(+ 2 6)"))
(test #t (pair? (read-from "(+ 2 6)")))

(section "3.4 Storage model")
(test #t (let ((p (list 1 2))) (eqv? (car p) (car p))))
(test "baa" (let ((s (make-string 3 #\a))) (string-set! s 0 #\b) s))
(test #t (let ((s (make-string 3 #\a))) (eq? s (begin (string-set! s 0 #\b) s))))
(test #(x 2) (let ((v (vector 1 2))) (vector-set! v 0 'x) v))
(test '(9 2) (let ((p (list 1 2))) (set-car! p 9) p))
(test #t (eq? '() '()))
(test 'fetched (let ((v (vector 'fetched))) (vector-ref v 0)))

(section "3.5 Proper tail recursion")
;; Each loop makes 10000 calls in the tail context under test. On an
;; implementation without proper tail calls these exhaust the stack.
(define n 10000)
(define-syntax tail-loop
  (syntax-rules ()
    ((_ (loop k) body)
     (letrec ((loop (lambda (k) (if (= k 0) 'done body)))) (loop n)))))
(test 'done (tail-loop (loop k) (if #t (loop (- k 1)) #f)))
(test 'done (tail-loop (loop k) (if #f #f (loop (- k 1)))))
(test 'done (tail-loop (loop k) (cond (#f 1) (else (loop (- k 1))))))
(test 'done (tail-loop (loop k) (cond ((- k 1) => loop))))
(test 'done (tail-loop (loop k) (case 1 ((1) (loop (- k 1))) (else #f))))
(test 'done (tail-loop (loop k) (case 1 ((2) #f) (else (loop (- k 1))))))
(test 'done (tail-loop (loop k) (case (- k 1) ((-1) #f) (else => loop))))
(test 'done (tail-loop (loop k) (and #t (loop (- k 1)))))
(test 'done (tail-loop (loop k) (or #f (loop (- k 1)))))
(test 'done (tail-loop (loop k) (when #t (loop (- k 1)))))
(test 'done (tail-loop (loop k) (unless #f (loop (- k 1)))))
(test 'done (tail-loop (loop k) (let ((j (- k 1))) (loop j))))
(test 'done (tail-loop (loop k) (let* ((j k) (j (- j 1))) (loop j))))
(test 'done (tail-loop (loop k) (letrec ((j (- k 1))) (loop j))))
(test 'done (tail-loop (loop k) (letrec* ((j (- k 1))) (loop j))))
(test 'done (tail-loop (loop k) (let-values (((j) (- k 1))) (loop j))))
(test 'done (tail-loop (loop k) (let*-values (((j) (- k 1))) (loop j))))
(test 'done (tail-loop (loop k) (let-syntax () (loop (- k 1)))))
(test 'done (tail-loop (loop k) (letrec-syntax () (loop (- k 1)))))
(test 'done (tail-loop (loop k) (begin 1 (loop (- k 1)))))
(test 'done (tail-loop (loop k) (do ((i 0 (+ i 1))) ((= i 1) (loop (- k 1))))))
(test 'done (tail-loop (loop k) ((lambda () 1 (loop (- k 1))))))
(test 'done (tail-loop (loop k) ((case-lambda ((a) (loop a))) (- k 1))))
(test 'done (let loop ((k n)) (if (= k 0) 'done (loop (- k 1)))))
(test 'done (tail-loop (loop k) (apply loop (list (- k 1)))))
(test 'done (tail-loop (loop k) (call-with-current-continuation (lambda (c) (loop (- k 1))))))
(test 'done (tail-loop (loop k) (call-with-values (lambda () (- k 1)) loop)))
;; mutual recursion
(define (even2? k) (if (= k 0) #t (odd2? (- k 1))))
(define (odd2? k) (if (= k 0) #f (even2? (- k 1))))
(test #t (even2? n))

(test-report)
