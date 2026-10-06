;; (conformance test): a small test library for the conformance suite, in
;; portable R7RS-small so the suite can run on other implementations too.
;;
;;   (section "6.2 Numbers")          names the tests that follow
;;   (test expected expr)             expr's value is equal? to expected
;;   (test-approx expected expr)      inexact comparison, relative 1e-9
;;   (test-values (v ...) expr)       expr returns exactly the values v ...
;;   (test-error expr)                evaluating expr raises something
;;   (test-assert expr)               expr's value is not #f
;;   (test-unsupported "why" test)    a known gap: failing is expected (XFAIL),
;;                                    passing is reported (XPASS) so the
;;                                    record can be updated
;;   (test-report)                    prints the summary; call it last
;;
;; Output: one line per failure, tab-separated, read by conformance/run.py:
;;   FAIL / XFAIL / XPASS <tab> section <tab> expression <tab> detail
;;   SUMMARY <tab> pass <tab> fail <tab> xfail <tab> xpass

(define-library (conformance test)
  (export section test test-approx test-values test-error test-assert
          test-unsupported test-report)
  (import (scheme base) (scheme write) (scheme inexact))
  (begin
    (define current-section "")
    (define passed 0)
    (define failed 0)
    (define xfailed 0)
    (define xpassed 0)
    ;; #f, or the reason a test is expected to fail
    (define expected-failure (make-parameter #f))

    (define (section name) (set! current-section name))

    (define (tab) (write-char #\tab))

    (define (line kind expr detail)
      (display kind) (tab)
      (display current-section) (tab)
      (write expr) (tab)
      (display detail)
      (newline))

    (define (record ok expr detail)
      (let ((why (expected-failure)))
        (cond ((and ok (not why)) (set! passed (+ passed 1)))
              (ok (set! xpassed (+ xpassed 1)) (line "XPASS" expr why))
              (why (set! xfailed (+ xfailed 1)) (line "XFAIL" expr why))
              (else (set! failed (+ failed 1)) (line "FAIL" expr detail)))))

    (define (show x)
      (let ((port (open-output-string)))
        (write x port)
        (get-output-string port)))

    ;; Run thunk; return (ok . values-list) or (#f . "raised: ...").
    (define (attempt thunk)
      (call-with-current-continuation
       (lambda (k)
         (with-exception-handler
          (lambda (e)
            (k (cons #f (string-append
                         "raised "
                         (if (error-object? e)
                             (show (cons (error-object-message e)
                                         (error-object-irritants e)))
                             (show e))))))
          (lambda ()
            (call-with-values thunk
              (lambda vals (cons #t vals))))))))

    (define (check expr thunk expected same?)
      (let ((r (attempt thunk)))
        (cond ((not (car r)) (record #f expr (cdr r)))
              ((and (= (length (cdr r)) 1) (same? (cadr r) expected))
               (record #t expr ""))
              (else
               (record #f expr (string-append
                                "expected " (show expected)
                                " got " (show (if (= (length (cdr r)) 1)
                                                  (cadr r)
                                                  (cons 'values (cdr r))))))))))

    (define (approx= a b)
      (and (number? a) (number? b)
           (or (= a b)
               (<= (abs (- a b)) (* 1e-9 (max (abs a) (abs b)))))))

    (define (check-values expr thunk expected)
      (let ((r (attempt thunk)))
        (cond ((not (car r)) (record #f expr (cdr r)))
              ((equal? (cdr r) expected) (record #t expr ""))
              (else (record #f expr (string-append
                                     "expected values " (show expected)
                                     " got " (show (cdr r))))))))

    (define (check-error expr thunk)
      (let ((r (attempt thunk)))
        (if (car r)
            (record #f expr (string-append "no error; returned " (show (cdr r))))
            (record #t expr ""))))

    (define-syntax test
      (syntax-rules ()
        ((_ expected expr)
         (check 'expr (lambda () expr) expected equal?))))

    (define-syntax test-approx
      (syntax-rules ()
        ((_ expected expr)
         (check 'expr (lambda () expr) expected approx=))))

    (define-syntax test-values
      (syntax-rules ()
        ((_ (v ...) expr)
         (check-values 'expr (lambda () expr) (list v ...)))))

    (define-syntax test-error
      (syntax-rules ()
        ((_ expr) (check-error 'expr (lambda () expr)))))

    (define-syntax test-assert
      (syntax-rules ()
        ((_ expr) (check 'expr (lambda () (if expr #t #f)) #t eq?))))

    (define-syntax test-unsupported
      (syntax-rules ()
        ((_ why t) (parameterize ((expected-failure why)) t))))

    (define (test-report)
      (display "SUMMARY") (tab)
      (display passed) (tab) (display failed) (tab)
      (display xfailed) (tab) (display xpassed)
      (newline))))
