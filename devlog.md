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
