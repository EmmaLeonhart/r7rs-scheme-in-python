# What this project is for

_Maintained by Claude: a running read of what the user is trying to do. It is
analysis, not a transcript, and it changes as understanding improves._

## Current understanding

Build a Scheme implementation in pure Python (standard library only) that aims
at R7RS-small, in the five stages `data_lake/brief.md` lays out:

1. Interpreter: reader, core special forms, proper tail calls, numeric tower
   (exact integers and rationals, inexact reals), strings, characters, vectors,
   bytevectors, standard procedures.
2. call/cc and dynamic-wind, exceptions (raise, guard,
   with-exception-handler), multiple values, hygienic syntax-rules.
3. Libraries (define-library, import), ports and file I/O, a REPL.
4. A compiler from the expanded core language to a bytecode VM, with the
   interpreter kept as the reference, and benchmarks comparing the two.
5. A conformance suite written from the R7RS report, section by section, that
   both the interpreter and the VM pass, with unsupported features recorded.

The README documents the design and its limits. If a stage turns out harder or
different than expected, the plan changes and the reason is written down.

## What supports it

- `data_lake/brief.md`, the only material in the folder, is a spec that states
  this outright. The brief says "This is a long project: work through it in
  stages and keep going after each one."
- The folder name `silver-jolly-tulip` is generated and carries no meaning.
- The user has said nothing in chat (intake report, 2026-10-05 22:45).

## Constraints from the user

- The implementation uses only the Python standard library (from the brief).
- From the starting prompt: the repo is private; don't invent work beyond what
  the material says.

## Assumptions (made without the user; revisit if they say otherwise)

- Tests use stdlib `unittest`, not pytest, so that "standard library only"
  holds for the test suite as well.
- Target Python 3.9+ (cleanvibe's own floor); developed on Python 3.13.
- Package name `pyscheme` was rejected as too generic; the package is `tulip`
  (after the folder), a working name that is easy to change.
- The conformance suite is written from the R7RS-small report, fetched on
  2026-10-06 into `data_lake/downloads/r7rs.pdf` (the report permits
  copying; see `data_lake/downloads/SOURCES.md`).

## Open questions

- None blocking. A different package name or Python version floor would be
  easy to change early.

## Confidence

High: the brief is explicit about what to build and in what order.

## Timeline

- Work mode started 2026-10-05 22:45 PST (from `date`), by the intake verdict
  WORK MODE (material present, no chat).
- Stages 1 to 3 done 2026-10-05; stage 4 (bytecode VM, benchmarks) done
  2026-10-06 01:00; stage 5 (conformance suite, 1273 tests per engine, all
  passing; complex numbers recorded as unsupported) done 2026-10-06 01:33
  (times from `date`). The user has said nothing in chat; the plan followed
  the brief unchanged.

## Where it stands

Everything the brief asks for is done. The brief says "keep going after
each one" but lists nothing after stage 5, so there is no further planned
work. Not queued, on purpose:

- Complex numbers: the brief's stage 1 names the numeric tower as exact
  integers, rationals and inexact reals, and R7RS makes complex numbers
  optional (6.2.3). Adding them would be new scope: NEEDS-DECISION by the
  user.
- Further VM speed work: the brief asks for a VM and benchmarks, not a
  target speed. Also NEEDS-DECISION by the user.
