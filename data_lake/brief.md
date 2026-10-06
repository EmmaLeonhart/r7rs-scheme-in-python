# Brief

A Scheme implementation in pure Python (standard library only), aiming at
R7RS-small. This is a long project: work through it in stages and keep
going after each one.

1. An interpreter: reader, the core special forms, proper tail calls, the
   numeric tower (exact integers and rationals, inexact reals), strings,
   characters, vectors, bytevectors, and the standard procedures.
2. call/cc and dynamic-wind, exceptions (raise, guard, with-exception-handler),
   multiple values, and hygienic syntax-rules macros.
3. Libraries (define-library, import), ports and file I/O, and a REPL.
4. A compiler from the expanded core language to a bytecode VM, keeping the
   interpreter as the reference, with benchmarks comparing the two.
5. A conformance suite written from the R7RS report, section by section,
   that both the interpreter and the VM pass; record what is not supported.

Document the design and its limits in the README. If a stage turns out
harder or different than expected, adjust the plan and say why.
