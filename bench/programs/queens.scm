;; N-queens: count the solutions for an 8x8 board by backtracking.
(define (ok? row dist placed)
  (or (null? placed)
      (and (not (= (car placed) (+ row dist)))
           (not (= (car placed) (- row dist)))
           (not (= (car placed) row))
           (ok? row (+ dist 1) (cdr placed)))))
(define (queens n)
  (let try ((col 0) (placed '()))
    (if (= col n)
        1
        (let loop ((row 0) (count 0))
          (if (= row n)
              count
              (loop (+ row 1)
                    (if (ok? row 1 placed) (+ count (try (+ col 1) (cons row placed))) count)))))))
(define (run) (queens 8))
