;; Library declarations of 5.6.1: export with rename, several begins,
;; include, include-ci, include-library-declarations and cond-expand.
(define-library (conformance decls)
  (export (rename internal-name external-name) first-begin second-begin)
  (include-library-declarations "decls-more.scm")
  (import (scheme base))
  (begin (define internal-name 'renamed)
         (define first-begin 1))
  (begin (define second-begin (+ first-begin 1)))
  (include "data/decls-body.scm")
  (include-ci "data/decls-body-ci.scm")
  (cond-expand
   (r7rs (begin (define expanded 'r7rs)))
   (else (begin (define expanded 'other))))
  (cond-expand
   ((library (scheme base)) (export from-cond-expand) (begin (define from-cond-expand 'yes)))
   (else (begin (define from-cond-expand 'no)))))
