;; Counts how many times its body runs: a library is loaded once however
;; many import declarations name it (5.6.1).
(define-library (conformance counter)
  (export loads a b)
  (import (scheme base))
  (begin
    (define loads 0)
    (set! loads (+ loads 1))
    (define a 'a)
    (define b 'b)))
