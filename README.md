# tulip: a Scheme in pure Python

> Started with [cleanvibe](https://github.com/EmmaLeonhart/cleanvibe) on 2026-10-05.
> The brief is in `data_lake/brief.md`; the running read of the goal is in `INTENT.md`.

A Scheme implementation in pure Python (standard library only), aiming at
R7RS-small. It is built in stages:

1. An interpreter: reader, core special forms, proper tail calls, the numeric
   tower (exact integers and rationals, inexact reals), strings, characters,
   vectors, bytevectors, and the standard procedures.
2. call/cc and dynamic-wind, exceptions, multiple values, hygienic
   syntax-rules macros.
3. Libraries (define-library, import), ports and file I/O, and a REPL.
4. A compiler from the expanded core language to a bytecode VM, with the
   interpreter kept as the reference, and benchmarks comparing the two.
5. A conformance suite written from the R7RS report, section by section.

## Status

Stage 1 is in progress. Nothing runs yet. This section will describe what
works and what doesn't as each stage lands.

## Design and limits

To be written as the design settles. Known limits will be listed here.

## Development

Requires Python 3.9 or newer and nothing else. Run the tests with:

    python -m unittest discover -s tests

## Working on it

Run `cleanvibe` in this folder (or double-click `!runClaude.bat` on Windows) to
open a new Claude session here. It starts with Remote Control on, so you can
continue from the Claude app or web. Earlier sessions are in `sessions/`.
