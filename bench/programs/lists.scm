;; List work through the standard library: map, filter-like folds, append,
;; reverse, assoc.
(define (iota* n) (let loop ((i (- n 1)) (acc '())) (if (< i 0) acc (loop (- i 1) (cons i acc)))))
(define (keep pred lst)
  (cond ((null? lst) '()) ((pred (car lst)) (cons (car lst) (keep pred (cdr lst)))) (else (keep pred (cdr lst)))))
(define (run)
  (let loop ((round 0) (total 0))
    (if (= round 20)
        total
        (let* ((xs (iota* 1000))
               (sq (map (lambda (x) (* x x)) xs))
               (ev (keep even? sq))
               (both (append (reverse ev) xs))
               (al (map (lambda (x) (cons x (* 2 x))) xs)))
          (loop (+ round 1)
                (+ total (length both) (apply + ev) (cdr (assv 999 al))))))))
