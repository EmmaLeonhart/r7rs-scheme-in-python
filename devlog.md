# devlog.md

Where "done" lives: dated entries for finished queue items, releases and
milestones. Newest at the bottom.

## 2026-10-05

- Project created with cleanvibe 2.0.4. The thirty-minute intake (22:45 PST)
  found `data_lake/brief.md` and no chat, so work mode started.
- `INTENT.md` written from the brief; private repo
  `EmmaLeonhart/r7rs-scheme-in-python` created and pushed.
- cleanvibe update check: v2.0.4 is the latest, skills already current.
- README filled in; `todo.md` (stages 2 to 5) and `queue.md` (stage 1) written.

## 2026-10-05 (stage 1, first pass)

- Package skeleton: `tulip/` (stdlib only), `python -m tulip [FILE]` with a
  basic REPL, `pyproject.toml`, unittest suite under `tests/`, GitHub Actions
  CI on Ubuntu and Windows with Python 3.9 and 3.13.
- Data model (`types.py`): interned symbols, pairs/NIL, mutable strings,
  chars, vectors as lists, bytevectors as bytearray, closures, primitives,
  promises, records, error objects.
- Reader (`reader.py`): all stage 1 lexical syntax, plus datum labels and
  `#!fold-case`. Complex-number syntax is rejected with a clear error.
- Printer (`printer.py`): write (labels only cycles), write-shared,
  write-simple, display.
- Expander (`expander.py`) to a core AST (`ast.py`): explicit-renaming
  aliases, so the built-in derived forms are hygienic already; internal
  defines with letrec* semantics. Derived forms: let/let*/letrec/letrec*,
  named let, cond/case with `=>`, and/or/when/unless, do, nested
  quasiquote, delay/delay-force, case-lambda, define-record-type.
- Interpreter (`interp.py`): explicit-continuation machine over lexically
  addressed nodes. Proper tail calls; deep non-tail recursion (300k) runs
  without touching the Python stack. 1M-iteration loop: about 2.8 s.
- 34 unit tests pass (reader, printer, core and derived forms, hygiene of
  derived forms, tail positions).

## 2026-10-05 (stage 1 done)

- Numeric tower tested (`tests/test_numbers.py`, report examples):
  predicates, comparison with mixed exactness, arithmetic incl. bignums and
  inexact division by zero, floor/ and truncate/ families, gcd/lcm,
  numerator/denominator, rationalize, rounding (half to even),
  transcendental functions, exact sqrt where possible, exactness conversion,
  number<->string with radix.
- Standard procedures tested (`tests/test_procedures.py`): equivalence
  (`equal?` terminates on cycles), pairs and lists, member/assoc with a
  predicate, multi-list map/for-each, symbols, chars, strings, vectors,
  bytevectors, booleans.
- `values` and `call-with-values` added early (a small `MultipleValues`
  object; `call-with-values` is a machine-level primitive).
- README: status, design and limits. CI green on Ubuntu and Windows,
  Python 3.9 and 3.13. 58 tests.
- Stage 2 planned into `queue.md` (dynamic-state register design).

## 2026-10-05 (stage 2 done)

- Dynamic state on the machine (winders, handler stack, parameter
  bindings), captured by continuations (`tulip/control.py`).
- call/cc with escape and re-entry; continuations accept multiple values.
  dynamic-wind, including the report's connect/talk/disconnect example.
- Exceptions: with-exception-handler, raise, raise-continuable; primitive
  failures and unbound variables are error objects that go through the same
  handlers; guard follows the report's reference expansion (re-raise with
  raise-continuable in the original dynamic environment).
- make-parameter (with converter) and parameterize.
- let-values, let*-values, define-values (top level and internal).
- syntax-rules (`tulip/syntax_rules.py`): define-syntax, let-syntax,
  letrec-syntax, internal define-syntax; literals, `_`, ellipsis followed by
  more patterns, dotted tails, vectors, nested ellipses, custom ellipsis,
  `(... ...)`; hygiene checked with the report's let-syntax and
  letrec-syntax examples.
- Three of my first stage 2 tests were wrong (a generator that never updated
  its return continuation and so looped forever, and two that expected
  top-level forms to re-run after re-entering a continuation). Fixed the
  tests and recorded the top-level behavior as a limit in the README.
- 93 tests pass.

## 2026-10-05 (stage 3 done)

- Libraries (`tulip/libraries.py`): per-library environments, imports share
  cells (live bindings), all R7RS-small standard libraries as export lists
  over the system environment, import sets, define-library with every
  declaration kind, `name/part.sld` lookup on a search path, cond-expand,
  include/include-ci, features, syntax-error. User code now has its own
  environment: redefining `if` no longer breaks `cond`.
- Ports (`tulip/ports.py`, `tulip/prims_ports.py`): textual/binary,
  string/bytevector/file/console; current ports are parameters; `read` on
  the console fills line by line until a datum is complete.
- `tulip/prims_system.py`: eval (a tail call), environment,
  interaction-environment, scheme-report-environment/null-environment, load,
  command-line, exit (runs pending after thunks via an empty-state
  continuation), emergency-exit, environment variables, time, and the
  real-number subset of (scheme complex).
- CLI: arguments reach `command-line`; exit status from `exit`, 70 after an
  uncaught error. REPL prints multiple values and survives errors.
- Fixes on the way: `port?` was missing from the (scheme base) export list;
  `platform.machine()` cost about 2 s per process on Windows and was dropped
  from `features`.
- 132 tests pass; a test asserts that every R7RS-small standard name exists.

## 2026-10-06 (stage 4: VM, engines)

- `tulip/vm.py` (commit f5b012d, logged here because that commit left the
  queue and devlog behind): compiler from the core AST to bytecode, lexical
  addressing, tail calls, direct `let`-style application, and the VM loop.
  VM frames are machine continuation frames, so call/cc, dynamic-wind,
  handlers, parameters and values work unchanged, and VM and interpreter
  procedures call each other.
- `Runtime(engine="vm")` compiles the prelude and user code with the VM;
  `eval` and `load` follow the runtime's engine. New: the CLI takes
  `--engine interp|vm` before FILE (exit 2 on a bad option).
- 133 tests pass under both engines (`TULIP_ENGINE=vm`).

## 2026-10-06 (stage 4: fast ops tested, CI on both engines)

- The specialized opcodes for hot built-ins (`+ - < > <= >= = cons eq?`,
  `car cdr null? pair? not zero?`, and PRIM for other primitives) were already
  in f5b012d. `tests/test_vm.py` (12 tests) now covers them: non-fixnum
  operands and errors match the interpreter; a global that held a built-in
  and is later changed falls back to an ordinary call, and in tail position
  that call is a tail call (checked by counting continuation frames: under 20
  after 20000 iterations, against one frame per iteration for a non-tail
  call); VM and interpreter closures call each other, including mutual tail
  recursion, escapes, `guard` and `dynamic-wind`; re-entering continuations
  through VM frames restores the pending operands.
- CI runs the suite under both engines (`engine: [interp, vm]` in the matrix).
- 145 tests pass under both engines.

## 2026-10-06 (stage 4: benchmarks)

- `bench/`: nine programs (fib, tak, a named-let loop, list work, string
  work, closures, call/cc, merge sort, 8-queens) and `bench/run.py`, which
  times `(run)` on both engines (best of 3) and fails if the results differ.
- `bench/RESULTS.md`: the VM is 1.85x faster in total; 2 to 2.5x on calls
  and fixnum arithmetic, 1.36x on `closures` and 1.09x on `callcc`. Those
  two are queued for profiling.

## 2026-10-06 (stage 4: profiling closures and call/cc)

- Profile: `closures` and `callcc` re-entered the VM loop 90,000 and 120,000
  times, because `apply`, `call/cc` and continuation calls went through the
  machine. The VM now handles them in the loop (a continuation only when its
  winders are the current ones, so `dynamic-wind` still goes through the
  machine). `callcc` 1.09x -> 1.32x, `closures` 1.36x -> 1.43x; the rest is
  ordinary dispatch on closure calls, recorded in `bench/RESULTS.md`.
- `tests/test_vm.py`: parity tests for the in-loop paths (arity errors,
  multiple values, re-entry, parameters, raise-continuable) and 50,000-deep
  `apply` and `call/cc` loops. 147 tests pass under both engines.

## 2026-10-06 (stage 4 done)

- README: the VM in the design section (shared AST and machine, frames,
  fast opcodes and their fallbacks, what stays in the loop), the benchmark
  numbers in the limits section, `TULIP_ENGINE=vm` and `bench/run.py` under
  Development.
- Stage 5 (conformance) moved from `todo.md` into `queue.md` as concrete
  steps.

## 2026-10-06 (stage 5: the report)

- Fetched the R7RS-small report (July 6, 2013) into
  `data_lake/downloads/r7rs.pdf`, with its source and copying permission in
  `data_lake/downloads/SOURCES.md`. INTENT.md updated (timeline, source).

## 2026-10-06 (stage 5: harness, chapters 2 and 3)

- `conformance/conformance/test.sld`: the `(conformance test)` library in
  portable R7RS (`test`, `test-approx`, `test-values`, `test-error`,
  `test-assert`, `test-unsupported` for recorded gaps, `test-report`).
- `conformance/run.py`: runs each section file on both engines through the
  CLI, reports pass/fail/xfail/xpass per file, and fails on any FAIL, XPASS,
  crash, or difference between the engines' outputs.
  `tests/test_conformance.py` checks the harness and runs the suite on the
  engine under test, so CI covers it.
- `2-lexical.scm` (identifiers, fold-case directives, comments, other
  notations, datum labels) and `3-basic.scm` (regions, disjointness of
  types, external representations, storage, tail calls in every tail context
  of 3.5): 132 tests, all passing on both engines. Two first-run failures
  were mistakes in the tests (an ill-formed `a#|x|#b`, an undeclared record
  field), fixed in the tests.

## 2026-10-06 (stage 5: chapter 4)

- `4.1-primitive.scm` (55 tests: literals, calls, lambda formals, if, set!,
  include and include-ci with files under `conformance/data/`),
  `4.2-derived.scm` (120: cond, case, and/or, when/unless, cond-expand,
  the let family, do and named let, delay/delay-force/make-promise,
  parameterize, guard, quasiquote including nesting, case-lambda),
  `4.3-macros.scm` (38: let-syntax/letrec-syntax scoping, the pattern
  language including literals, underscore, tail and vector patterns, custom
  ellipsis and `(... ...)`, hygiene in both directions, syntax-error's
  example). All pass on both engines; tulip needed no changes.
- Removed from the tests on review: a `test` call with three arguments, an
  arity error the report does not require to be signalled, and a
  `(b ... ...)` template, which is beyond R7RS's template grammar (7.1.5).

## 2026-10-06 (stage 5: chapter 5)

- `5-programs.scm` (48 tests): every import-set form, top-level and internal
  definitions, define-values, define-syntax (including macros that expand
  into definitions), define-record-type (generativity, partial constructors),
  library declarations (export rename, several begins, include, include-ci,
  include-library-declarations, cond-expand with export), load-once, and the
  report's own grid/life library example from 5.6.2 run for four
  generations. Libraries in `conformance/example/` and
  `conformance/conformance/`. All pass on both engines with no changes to
  tulip; one first-run failure was a miscounted escape sequence in the test.
  5.7 (the REPL) is left to `tests/test_system.py`.

## 2026-10-06 (stage 5: 6.1 to 6.3, and three fixes)

- `6.1-equivalence.scm` (64 tests) and `6.2-numbers.scm` (258, plus the 14
  complex-number examples as expected failures; 6.3 booleans are in the
  same file). `conformance/UNSUPPORTED.md` records the complex-number gap.
- The suite found three bugs in tulip, each fixed with a regression test:
  - `(eqv? 0.0 -0.0)` was `#t`; tulip distinguishes negative zero, so 6.1
    requires `#f`. `eqv?` now compares the sign of zeros (`memv`, `case`
    follow).
  - A circular literal in program text (`'#1=(a b . #1#)`, allowed by 2.4)
    sent the expander's `strip_syntax` into infinite recursion. It now
    returns alias-free data untouched and copies the rest with a memo,
    walking list spines iteratively; a quoted list of 5000 elements, which
    also raised RecursionError, now works.
  - Same depth problem in syntax-rules template instantiation for long
    literal lists in a template; the spine is now walked in a loop.
- Test mistakes found on the way (fixed in the tests): `(remainder 13 4)` is
  1, and `rationalize`'s inexact result must be compared with `(inexact 1/3)`.
- 150 unit tests pass on both engines; the suite so far: 715 tests per
  engine, all pass, 14 expected failures.
