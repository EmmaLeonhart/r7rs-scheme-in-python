;; call/cc: early exit from a search, and a generator that re-enters
;; continuations.
(define (find-first pred lst)
  (call/cc (lambda (return) (for-each (lambda (x) (if (pred x) (return x))) lst) #f)))
(define (make-gen lst)
  (define return #f)
  (define resume #f)
  (lambda ()
    (call/cc (lambda (r)
      (set! return r)
      (if resume
          (resume #f)
          (begin
            (for-each (lambda (x) (call/cc (lambda (next) (set! resume next) (return x)))) lst)
            (return 'eof)))))))
(define (iota* n) (let loop ((i (- n 1)) (acc '())) (if (< i 0) acc (loop (- i 1) (cons i acc)))))
(define (run)
  (let ((xs (iota* 200)))
    (let loop ((round 0) (acc 0))
      (if (= round 150)
          acc
          (let ((g (make-gen xs)))
            (let sum ((total (find-first (lambda (x) (> x round)) xs)))
              (let ((v (g)))
                (if (eq? v 'eof) (loop (+ round 1) (+ acc total)) (sum (+ total v))))))))))
