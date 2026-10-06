# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 5: conformance

Design for this stage: a conformance suite under `conformance/`, one Scheme
file per section of the R7RS-small report (chapters 2 to 6, plus the
derived-forms and library chapters where they say something testable),
written from the report's text and examples rather than from tulip's own
behavior. Each file uses a small test library `(conformance test)` with
`test`, `test-error`, `test-values` and `section`, written in portable R7RS
so the suite could run on another implementation. A runner runs every file
on both engines and reports pass/fail per section; the unittest suite calls
it so CI covers it. Anything the report requires that tulip does not do is
recorded in `conformance/UNSUPPORTED.md` with the section and the reason,
and the test is marked as an expected failure there rather than deleted.

1. Fetch the R7RS-small report into `data_lake/downloads/` (it permits
   copying) and record its source and date.
2. `conformance/test.sld` (the test library), `conformance/run.py` (both
   engines, per-section results, exit 1 on unexpected failure), and a unittest
   that runs it.
3. Chapters 2 and 3: lexical conventions, datum labels, disjointness of
   types, proper tail recursion (deep loops in every tail context 3.5 lists).
4. Chapter 4: primitive and derived expressions, quasiquote, case-lambda,
   parameterize, guard, delay/force, macros (4.3).
5. Chapter 5: programs, import, definitions, define-record-type, libraries.
6. Chapter 6.1 to 6.9: equivalence, numbers, booleans, lists, symbols,
   characters, strings, vectors, bytevectors.
7. Chapter 6.10 to 6.14: control, exceptions, eval, I/O, system interface.
8. Fix what the suite finds (each fix with a regression test), record what
   stays unsupported, and write up the results in the README.
