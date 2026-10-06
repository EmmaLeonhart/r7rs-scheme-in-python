;; A named-let loop: tail calls and fixnum arithmetic only.
(define (run)
  (let loop ((i 0) (acc 0))
    (if (= i 300000) acc (loop (+ i 1) (+ acc (* i i))))))
