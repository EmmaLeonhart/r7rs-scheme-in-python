# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 1: the interpreter

Design decision for this stage: the evaluator is an explicit-continuation
machine (a loop over heap-allocated continuation frames), not a recursive
Python `eval`. That gives proper tail calls, no Python recursion-limit crashes
on deep recursion, and makes stage 2's call/cc and dynamic-wind a matter of
capturing the frame stack rather than a rewrite.

1. Package skeleton: `tulip/` package, `tests/` with unittest, a CLI entry
   (`python -m tulip file.scm`), GitHub Actions CI on Python 3.9 and 3.13.
2. Data model: symbols (interned), pairs and the empty list, booleans, chars,
   mutable strings, vectors, bytevectors, the unspecified and EOF objects,
   procedures (primitive and closure), environments.
3. Reader: all R7RS lexical syntax for stage 1: lists, dotted pairs, quote /
   quasiquote / unquote / unquote-splicing abbreviations, vectors `#(`,
   bytevectors `#u8(`, chars (`#\a`, named, `#\x41`), strings with escapes,
   numbers (integers, rationals, decimals, exponents, radix prefixes `#x #b #o
   #d`, exactness prefixes `#e #i`, `+inf.0 -inf.0 +nan.0`), `|symbol|`,
   comments `;`, `#| |#` nested, `#;` datum comment, `#!fold-case`.
4. Printer: `write` and `display` representations for every type.
5. Evaluator core: the continuation machine with quote, if, define, set!,
   lambda (fixed, rest and variadic args), begin, and application; proper tail
   calls verified by a loop of a million iterations.
6. Derived forms: let, let*, letrec, letrec*, named let, cond (with `=>`),
   case (with `=>`), and, or, when, unless, do, quasiquote (nested levels,
   vectors), internal defines, delay / delay-force / force / make-promise,
   and case-lambda. (make-parameter / parameterize and guard belong with
   dynamic-wind and exceptions in stage 2.)
7. Numeric tower: exact integers (Python int), exact rationals
   (fractions.Fraction), inexact reals (float); arithmetic, comparisons,
   exact/inexact, quotient/remainder/modulo, floor/ and truncate/ families,
   gcd/lcm, numerator/denominator, floor/ceiling/round/truncate, exact-integer-sqrt,
   expt, sqrt (exact results where exact), number->string / string->number with
   radix, and the predicates.
8. Standard procedures: booleans, pairs and lists (including list-copy,
   member/assoc with optional compare), symbols, chars (char-upcase etc.),
   strings (string-copy!, string-fill!, string-map, string-for-each, substring),
   vectors (vector-map, vector-for-each, vector->list ranges, vector-fill!),
   bytevectors (bytevector-copy!, utf8->string, string->utf8), apply, map,
   for-each, eq?/eqv?/equal?.
9. Stage 1 wrap-up: README status and limits, devlog entry, and a check that
   the stage 2 items in `todo.md` still fit the design.
