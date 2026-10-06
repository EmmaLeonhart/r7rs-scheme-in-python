# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 1: the interpreter

Design decision for this stage: the evaluator is an explicit-continuation
machine (a loop over heap-allocated continuation frames), not a recursive
Python `eval`. That gives proper tail calls, no Python recursion-limit crashes
on deep recursion, and makes stage 2's call/cc and dynamic-wind a matter of
capturing the frame stack rather than a rewrite.

1. Numeric tower (code written in `prims_numbers.py`; needs its tests): exact integers (Python int), exact rationals
   (fractions.Fraction), inexact reals (float); arithmetic, comparisons,
   exact/inexact, quotient/remainder/modulo, floor/ and truncate/ families,
   gcd/lcm, numerator/denominator, floor/ceiling/round/truncate, exact-integer-sqrt,
   expt, sqrt (exact results where exact), number->string / string->number with
   radix, and the predicates.
2. Standard procedures (code written in `prims_data.py`, `prims_misc.py`,
   `prelude.scm`; needs its tests): booleans, pairs and lists (including list-copy,
   member/assoc with optional compare), symbols, chars (char-upcase etc.),
   strings (string-copy!, string-fill!, string-map, string-for-each, substring),
   vectors (vector-map, vector-for-each, vector->list ranges, vector-fill!),
   bytevectors (bytevector-copy!, utf8->string, string->utf8), apply, map,
   for-each, eq?/eqv?/equal?.
3. Stage 1 wrap-up: README status and limits, devlog entry, and a check that
   the stage 2 items in `todo.md` still fit the design.
