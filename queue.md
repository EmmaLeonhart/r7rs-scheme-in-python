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

7. Chapter 6.10 to 6.14: control, exceptions, eval, I/O, system interface.
8. Fix what the suite finds (each fix with a regression test), record what
   stays unsupported, and write up the results in the README.
