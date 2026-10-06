# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 2: control and macros

Design for this stage: the machine gets one more register, the *dynamic
state*: an immutable linked record of the dynamic-wind winders, the
exception-handler stack and the parameter bindings. A continuation captures
`k` plus the dynamic state; invoking it runs the `after` thunks being exited
and the `before` thunks being entered (as ordinary Scheme calls through
continuation frames) before delivering the values. Errors raised from Python
primitives go through the same handler stack as `raise`.

1. call/cc (`call-with-current-continuation`) and dynamic-wind, with
   re-entry and escape both ways; continuations accept multiple values.
2. Exceptions: with-exception-handler, raise, raise-continuable, error
   objects from `error` and from primitive failures, and `guard` (with `=>`
   and re-raise when no clause matches) per R7RS 4.2.7.
3. Parameters: make-parameter (with converter) and parameterize.
4. Multiple values forms: let-values, let*-values, define-values (top level
   and internal).
5. syntax-rules: define-syntax, let-syntax, letrec-syntax, internal
   define-syntax; patterns with literals, `_`, ellipsis anywhere in a list
   (including before a tail), dotted tails, vectors, nested ellipses, custom
   ellipsis identifier, `(... ...)` escapes; hygiene for both introduced
   bindings and free identifiers.
6. Stage 2 wrap-up: tests for each item, README status and limits, devlog,
   and a check that stage 3 in `todo.md` still fits.
