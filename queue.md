# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 3: libraries, ports, REPL

Design for this stage: every library gets its own `Environment`. Importing
copies *bindings*: the same `Cell` object for a variable (so imports are live
and cost nothing at run time) and the same macro/keyword object for syntax.
All built-ins live in one system environment; the standard libraries
(`(scheme base)` and the rest) are export lists over it. User code runs in
its own environment, so redefining `if` or `list` there no longer affects the
built-in derived forms. Port defaults (`current-output-port` and friends)
become real parameters, so `parameterize` and `with-output-to-file` work.

1. Libraries: a system environment plus standard-library export lists for
   every R7RS-small library (base, case-lambda, char, complex (real numbers
   only), cxr, eval, file, inexact, lazy, load, process-context, read, repl,
   time, write, r5rs); import sets (only, except, prefix, rename);
   define-library with export (incl. rename), import, begin, include,
   include-ci, include-library-declarations, cond-expand; library lookup on a
   search path (`foo/bar.sld`); programs that start with `import`; set! on
   an imported binding is an error.
2. cond-expand as an expression/definition form, `features`, include and
   include-ci at top level and in bodies.
3. Ports: textual and binary, input and output; string, bytevector and file
   ports; current-input/output/error-port as parameters; read-char,
   peek-char, read-line, read-string, char-ready?, read-u8, peek-u8,
   u8-ready?, read-bytevector(!), write-u8, write-bytevector, close-*,
   call-with-port, call-with-input-file, call-with-output-file,
   with-input-from-file, with-output-to-file, open-*-file, file-exists?,
   delete-file, eof-object; `read` from a port (incrementally for stdin).
4. eval, environment, interaction-environment, load, and the
   process-context and time procedures: command-line, exit (running
   outstanding dynamic-wind afters), emergency-exit,
   get-environment-variable(s), current-second, current-jiffy,
   jiffies-per-second.
5. REPL: multiple values printed, recovery after errors, `python -m tulip
   FILE ARGS...` passing arguments to `command-line`.
6. Stage 3 wrap-up: tests for each item, README, devlog, check stage 4.
