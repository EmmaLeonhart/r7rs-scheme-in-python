;; R7RS-small 4.3: macros.
;; syntax-error cannot be tested at run time: the report says applications
;; cannot count on catching it. Only the non-error rule of its example is used.
(import (scheme base) (conformance test))

(section "4.3.1 let-syntax, letrec-syntax")
(test 'now (let-syntax ((given-that (syntax-rules ()
                                      ((_ test stmt1 stmt2 ...)
                                       (if test (begin stmt1 stmt2 ...))))))
             (let ((if #t))
               (given-that if (set! if 'now))
               if)))
(test 'outer (let ((x 'outer))
               (let-syntax ((m (syntax-rules () ((m) x))))
                 (let ((x 'inner))
                   (m)))))
(test 7 (letrec-syntax
            ((my-or (syntax-rules ()
                      ((my-or) #f)
                      ((my-or e) e)
                      ((my-or e1 e2 ...)
                       (let ((temp e1))
                         (if temp temp (my-or e2 ...)))))))
          (let ((x #f) (y 7) (temp 8) (let odd?) (if even?))
            (my-or x (let temp) (if y) y))))
;; let-syntax keywords are not visible to each other's transformers
(test 'outer-m (let-syntax ((m (syntax-rules () ((_) 'outer-m))))
                 (let-syntax ((m (syntax-rules () ((_) 'inner-m)))
                              (n (syntax-rules () ((_) (m)))))
                   (n))))
(test 'inner-m (let-syntax ((m (syntax-rules () ((_) 'outer-m))))
                 (letrec-syntax ((m (syntax-rules () ((_) 'inner-m)))
                                 (n (syntax-rules () ((_) (m)))))
                   (n))))
;; the body of let-syntax may contain definitions
(test 3 (let () (let-syntax ((m (syntax-rules () ((_) 1)))) (define a (m)) (+ a 2))))

(section "4.3.2 Pattern language")
(define-syntax be-like-begin
  (syntax-rules ()
    ((be-like-begin name)
     (define-syntax name
       (syntax-rules ()
         ((name expr (... ...))
          (begin expr (... ...))))))))
(be-like-begin sequence)
(test 4 (sequence 1 2 3 4))
(test 'ok (let ((=> #f)) (cond (#t => 'ok))))
;; literals
(define-syntax arrow-test
  (syntax-rules (=>)
    ((_ a => b) (list 'arrow a b))
    ((_ a b c) (list 'plain a b c))))
(test '(arrow 1 2) (arrow-test 1 => 2))
(test '(plain 1 2 3) (arrow-test 1 2 3))
(test '(plain 1 #f 2) (let ((=> #f)) (arrow-test 1 => 2)))
;; underscore matches anything and binds nothing
(define-syntax second
  (syntax-rules () ((_ _ b . _) 'b)))
(test 'y (second x y z w))
(define-syntax under-literal
  (syntax-rules (_) ((m _) 'underscore) ((m x) 'other)))
(test 'underscore (under-literal _))
(test 'other (under-literal 5))
;; ellipsis with zero matches, nested ellipses
(define-syntax my-list (syntax-rules () ((_ x ...) (list x ...))))
(test '() (my-list))
(test '(1 2 3) (my-list 1 2 3))
(define-syntax my-let*
  (syntax-rules ()
    ((_ () body ...) (let () body ...))
    ((_ ((x v) rest ...) body ...) (let ((x v)) (my-let* (rest ...) body ...)))))
(test 3 (my-let* ((a 1) (b (+ a 1))) (+ a b)))
(define-syntax flatten-pairs
  (syntax-rules () ((_ (a b ...) ...) '((a ...) ((b ...) ...)))))
(test '((1 4) ((2 3) (5 6))) (flatten-pairs (1 2 3) (4 5 6)))
;; patterns after an ellipsis, and dotted tails
(define-syntax last-of
  (syntax-rules () ((_ x ... y) 'y)))
(test 'c (last-of a b c))
(test 'a (last-of a))
(define-syntax ends
  (syntax-rules () ((_ a b ... c d) '(a c d))))
(test '(1 4 5) (ends 1 2 3 4 5))
(test '(1 2 3) (ends 1 2 3))
(define-syntax dotted
  (syntax-rules () ((_ a ... . r) '((a ...) r))))
(test '((1 2) ()) (dotted 1 2))
(define-syntax improper
  (syntax-rules () ((_ (a . b)) '(a b))))
(test '(1 (2 3)) (improper (1 2 3)))
(test '(1 2) (improper (1 . 2)))
;; vector patterns
(define-syntax vec
  (syntax-rules () ((_ #(a b ...)) '(a (b ...)))))
(test '(1 (2 3)) (vec #(1 2 3)))
(define-syntax vec-tail
  (syntax-rules () ((_ #(a ... b c)) '(b c))))
(test '(2 3) (vec-tail #(1 2 3)))
;; constants in patterns match by equal?
(define-syntax konst
  (syntax-rules () ((_ 1) 'one) ((_ "s") 'string) ((_ #t) 'true) ((_ x) 'other)))
(test '(one string true other) (list (konst 1) (konst "s") (konst #t) (konst 2)))
;; a custom ellipsis
(define-syntax my-list2
  (syntax-rules ::: () ((_ x :::) (list x :::))))
(test '(1 2) (my-list2 1 2))
(define-syntax ellipsis-literal
  (syntax-rules ::: (...) ((_ ...) 'dots) ((_ x) 'other)))
(test 'dots (ellipsis-literal ...))
;; the first matching rule wins
(define-syntax first-rule
  (syntax-rules () ((_ x) 'one) ((_ x ...) 'many)))
(test 'one (first-rule a))
(test 'many (first-rule a b))

(section "4.3.2 Hygiene")
(define-syntax swap!
  (syntax-rules ()
    ((_ a b) (let ((tmp a)) (set! a b) (set! b tmp)))))
(test '(2 1) (let ((tmp 1) (other 2)) (swap! tmp other) (list tmp other)))
(define-syntax my-if
  (syntax-rules () ((_ c a b) (cond (c a) (else b)))))
(test 'yes (let ((cond #f) (else #f)) (my-if #t 'yes 'no)))
(define helper-value 'from-definition)
(define-syntax get-helper (syntax-rules () ((_) helper-value)))
(test 'from-definition (let ((helper-value 'local)) (get-helper)))
(define-syntax while
  (syntax-rules ()
    ((_ c body ...) (let lp () (when c body ... (lp))))))
(test 3 (let ((i 0) (lp 'user)) (while (< i 3) (set! i (+ i 1))) i))
;; macros defined in a body
(test 10 (let ()
           (define-syntax double (syntax-rules () ((_ x) (* 2 x))))
           (double 5)))

(section "4.3.3 Signaling errors in macro transformers")
(define-syntax simple-let
  (syntax-rules ()
    ((_ (head ... ((x . y) val) . tail) body1 body2 ...)
     (syntax-error "expected an identifier but got" (x . y)))
    ((_ ((name val) ...) body1 body2 ...)
     ((lambda (name ...) body1 body2 ...) val ...))))
(test 3 (simple-let ((a 1) (b 2)) (+ a b)))

(test-report)
