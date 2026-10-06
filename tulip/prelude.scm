;;; prelude.scm: standard procedures written in Scheme.
;;;
;;; These take procedure arguments, so they are written in Scheme rather than
;;; Python: that way call/cc, tail calls and errors work through them.
;;; Results are built fresh (accumulate, then reverse) so a continuation
;;; captured inside the mapped procedure can be re-entered safely.

(define (map f l . ls)
  (if (null? ls)
      (let loop ((l l) (acc '()))
        (if (pair? l)
            (loop (cdr l) (cons (f (car l)) acc))
            (reverse acc)))
      (let loop ((ls (cons l ls)) (acc '()))
        (let ((split (%cars+cdrs ls)))
          (if split
              (loop (cdr split) (cons (apply f (car split)) acc))
              (reverse acc))))))

(define (for-each f l . ls)
  (if (null? ls)
      (let loop ((l l))
        (if (pair? l)
            (begin (f (car l)) (loop (cdr l)))))
      (let loop ((ls (cons l ls)))
        (let ((split (%cars+cdrs ls)))
          (if split
              (begin (apply f (car split)) (loop (cdr split))))))))

(define (string-map f s . ss)
  (list->string (apply map f (string->list s) (map string->list ss))))

(define (string-for-each f s . ss)
  (apply for-each f (string->list s) (map string->list ss)))

(define (vector-map f v . vs)
  (list->vector (apply map f (vector->list v) (map vector->list vs))))

(define (vector-for-each f v . vs)
  (apply for-each f (vector->list v) (map vector->list vs)))

(define (member x l . compare)
  (if (null? compare)
      (%member x l)
      (let ((same? (car compare)))
        (let loop ((l l))
          (cond ((not (pair? l)) #f)
                ((same? x (car l)) l)
                (else (loop (cdr l))))))))

(define (assoc x alist . compare)
  (if (null? compare)
      (%assoc x alist)
      (let ((same? (car compare)))
        (let loop ((l alist))
          (cond ((not (pair? l)) #f)
                ((same? x (car (car l))) (car l))
                (else (loop (cdr l))))))))

;; R7RS 7.3 reference implementation: iterative forcing of delay-force chains.
(define (force promise)
  (if (promise? promise)
      (if (%promise-done? promise)
          (%promise-value promise)
          (let ((promise* ((%promise-value promise))))
            (if (not (%promise-done? promise))
                (%promise-update! promise* promise))
            (force promise)))
      promise))

;;; Parameters (R7RS 4.2.6). The converter is applied to the initial value
;;; and to every parameterize value.

(define (make-parameter value . converter)
  (if (null? converter)
      (%make-parameter value (lambda (x) x))
      (%make-parameter ((car converter) value) (car converter))))

(define (%parameterize params vals body)
  (%with-parameters params
                    (map (lambda (p v) ((%parameter-converter p) v)) params vals)
                    body))
