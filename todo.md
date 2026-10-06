# todo.md: long-horizon goals

Abstract destinations, from `data_lake/brief.md`. Each is pulled into
`queue.md` as concrete steps when its turn comes.

- **Stage 3: libraries, ports, REPL.** define-library and import with the
  standard (scheme base) etc. library names, cond-expand, include; textual and
  binary ports, string ports, file I/O, read/write/display including
  datum labels for shared structure; a REPL with error recovery.
- **Stage 4: bytecode VM.** A compiler from the expanded core language to
  bytecode, a VM that runs it with proper tail calls and first-class
  continuations, the interpreter kept as the reference, and benchmarks
  comparing the two.
- **Stage 5: conformance.** A suite written from the R7RS-small report,
  section by section, run against both the interpreter and the VM; a record of
  what is not supported and why.
- **Throughout:** the README documents the design and its limits; when a stage
  turns out harder or different than expected, adjust the plan and say why.
