;; Takeuchi's function: deep non-tail recursion with three arguments.
(define (tak x y z)
  (if (not (< y x))
      z
      (tak (tak (- x 1) y z) (tak (- y 1) z x) (tak (- z 1) x y))))
(define (run) (tak 20 12 6))
