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

;;; Ports (R7RS 6.13). The port argument is optional and defaults to the
;;; current port parameter, so these wrap %-primitives that take it
;;; explicitly. (%arg rest i default) is the i-th optional argument.

(define (%arg rest i default)
  (cond ((null? rest) default)
        ((= i 0) (car rest))
        (else (%arg (cdr rest) (- i 1) default))))

(define (read-char . p) (%read-char (%arg p 0 (current-input-port))))
(define (peek-char . p) (%peek-char (%arg p 0 (current-input-port))))
(define (char-ready? . p) (%char-ready? (%arg p 0 (current-input-port))))
(define (read-line . p) (%read-line (%arg p 0 (current-input-port))))
(define (read-string k . p) (%read-string k (%arg p 0 (current-input-port))))
(define (read . p) (%read (%arg p 0 (current-input-port))))
(define (read-u8 . p) (%read-u8 (%arg p 0 (current-input-port))))
(define (peek-u8 . p) (%peek-u8 (%arg p 0 (current-input-port))))
(define (u8-ready? . p) (%u8-ready? (%arg p 0 (current-input-port))))
(define (read-bytevector k . p)
  (%read-bytevector k (%arg p 0 (current-input-port))))
(define (read-bytevector! bv . r)
  (%read-bytevector! bv (%arg r 0 (current-input-port)) (%arg r 1 #f) (%arg r 2 #f)))

(define (write obj . p) (%write obj (%arg p 0 (current-output-port))))
(define (write-shared obj . p) (%write-shared obj (%arg p 0 (current-output-port))))
(define (write-simple obj . p) (%write-simple obj (%arg p 0 (current-output-port))))
(define (display obj . p) (%display obj (%arg p 0 (current-output-port))))
(define (newline . p) (%newline (%arg p 0 (current-output-port))))
(define (write-char c . p) (%write-char c (%arg p 0 (current-output-port))))
(define (write-string s . r)
  (%write-string s (%arg r 0 (current-output-port)) (%arg r 1 #f) (%arg r 2 #f)))
(define (write-u8 b . p) (%write-u8 b (%arg p 0 (current-output-port))))
(define (write-bytevector bv . r)
  (%write-bytevector bv (%arg r 0 (current-output-port)) (%arg r 1 #f) (%arg r 2 #f)))
(define (flush-output-port . p)
  (%flush-output-port (%arg p 0 (current-output-port))))

(define (call-with-port port proc)
  (call-with-values (lambda () (proc port))
    (lambda vals (close-port port) (apply values vals))))

(define (call-with-input-file file proc)
  (call-with-port (open-input-file file) proc))

(define (call-with-output-file file proc)
  (call-with-port (open-output-file file) proc))

(define (with-input-from-file file thunk)
  (let ((port (open-input-file file)))
    (call-with-values (lambda () (parameterize ((current-input-port port)) (thunk)))
      (lambda vals (close-input-port port) (apply values vals)))))

(define (with-output-to-file file thunk)
  (let ((port (open-output-file file)))
    (call-with-values (lambda () (parameterize ((current-output-port port)) (thunk)))
      (lambda vals (close-output-port port) (apply values vals)))))
