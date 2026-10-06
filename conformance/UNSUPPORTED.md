# What tulip does not support

Every test in the conformance suite marked `test-unsupported` is listed here
by section, with the reason. The runner reports these as XFAIL; if one starts
passing it is reported as XPASS and fails the run, so this list stays true.

## Complex numbers (6.2)

R7RS lets an implementation leave out parts of the numeric tower (6.2.3).
tulip implements exact integers, exact rationals and inexact reals, and no
complex numbers: the reader rejects `3+4i` and `2@0`, and `(sqrt -1)`,
`(asin 2)` and the like raise an error instead of returning a complex
result. `(scheme complex)` works on real numbers only.

Affected tests (14, in `6.2-numbers.scm`):

- 6.2.5: reading `3+4i`, `2@0`.
- 6.2.6 type predicates: `complex?`, `real?`, `integer?` on `3+4i`,
  `-2.5+0i`, `-2.5+0.0i`, `3+0i`; `finite?`, `infinite?`, `nan?` on
  `3.0+inf.0i`, `+nan.0+5.0i`, `1+2i`.
- 6.2.6 transcendental functions: `(asin 2)`.
- 6.2.6 `sqrt`: `(sqrt -1)`.
- 6.2.6 complex library: `magnitude` of `(make-rectangular 3 4)`,
  `make-polar` with a non-zero angle.

## Not covered by the suite

- **5.7 The REPL**: a program cannot drive a REPL portably; tulip's REPL is
  tested in `tests/test_system.py`.
- **6.14 `exit` and `emergency-exit`** end the process, so they cannot run
  inside a section file; `tests/test_system.py` tests them (exit codes,
  `after` thunks run by `exit` and not by `emergency-exit`, not catchable by
  `guard`, exit status through the CLI).
- **"It is an error" cases** are not tested anywhere in the suite: the
  report does not require them to be signalled.
- **Unspecified results** (for example `(eqv? "" "")`) are not tested.
