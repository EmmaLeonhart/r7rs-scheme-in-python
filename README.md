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

**Stages 1 (the interpreter) and 2 (control and macros) are done.** Run a
program with
`python -m tulip program.scm`, or start a basic REPL with `python -m tulip`.

```
$ python -m tulip
tulip> (define (fact n) (if (= n 0) 1 (* n (fact (- n 1)))))
tulip> (fact 30)
265252859812191058636308480000000
tulip> `(1 ,@(map square '(2 3)) ,(exact->inexact 1/3))
(1 4 9 0.3333333333333333)
```

What works: the full lexical syntax (including datum labels and
`#!fold-case`); `quote`, `if`, `define`, `set!`, `lambda`, `begin`; the
derived forms `let`, `let*`, `letrec`, `letrec*`, named `let`, `cond`, `case`,
`and`, `or`, `when`, `unless`, `do`, nested `quasiquote`, `delay`,
`delay-force`, `make-promise`, `case-lambda`, `define-record-type`; proper tail
calls in every tail position; the numeric tower (exact integers of any size,
exact rationals, inexact reals); the standard procedures on booleans, pairs
and lists, symbols, characters, strings, vectors and bytevectors; `apply`,
`map`, `for-each` and the string/vector variants; `values` and
`call-with-values`; `write`, `write-shared`, `write-simple`, `display` and
string output ports.

Stage 2 added: `call/cc` (escaping and re-entrant, multi-shot) and
`dynamic-wind`; `with-exception-handler`, `raise`, `raise-continuable`,
`guard`, and error objects (errors signalled by primitives, such as `(car 5)`,
are ordinary error objects a handler or `guard` can catch); `make-parameter`
and `parameterize`; `let-values`, `let*-values`, `define-values`; and
hygienic `syntax-rules` with `define-syntax`, `let-syntax`, `letrec-syntax`
and internal `define-syntax`. Patterns support literals, `_`, an ellipsis
anywhere in a list (`(a ... b c)`), dotted tails, vectors, nested ellipses,
a custom ellipsis identifier and the `(... ...)` escape.

Next: stage 3 (libraries, ports and file I/O, a REPL); see `todo.md`.

## Design

```
text --reader--> data --expander--> core AST --compile--> nodes --machine--> value
```

- **Reader** (`tulip/reader.py`): text to Scheme data. Pairs are `Pair`,
  the empty list is `NIL`, strings are mutable `MString`, vectors are Python
  lists, bytevectors `bytearray`, exact integers `int`, rationals
  `Fraction`, reals `float`.
- **Expander** (`tulip/expander.py`): surface syntax to a small core AST
  (`tulip/ast.py`: constants, local and global references, `if`, `lambda`,
  `set!`, definitions, sequences, calls). Every lexical variable becomes a
  unique `Var`, so the core has no names left to clash. Identifiers a macro
  introduces are *aliases* that remember the macro's environment (explicit
  renaming), so the built-in derived forms are hygienic:
  `(let ((if list)) (cond (#t 1)))` is still 1.
- **Interpreter** (`tulip/interp.py`): compiles the AST to nodes with
  lexical addresses and runs them on an explicit-continuation machine: a loop
  over immutable, heap-allocated continuation frames rather than recursive
  Python calls. Tail calls push no frame, deep recursion grows the heap rather
  than the Python stack, and a continuation is simply the frame chain, which
  is what `call/cc` captures. The machine also keeps the *dynamic state*
  (the `dynamic-wind` entries, the exception-handler stack and `parameterize`
  bindings) as immutable linked lists that continuations capture too; calling
  a continuation runs the `after` and `before` thunks it crosses as ordinary
  Scheme calls (`tulip/control.py`).
- **Macros** (`tulip/syntax_rules.py`): `syntax-rules` matches patterns and
  instantiates templates, renaming every identifier the template introduces to
  an alias of the macro's definition environment. The same alias mechanism
  the derived forms use then gives hygiene in both directions.
- **Primitives** are Python functions (`tulip/prims_*.py`); procedures that
  call other procedures (`map`, `for-each`, `member` with a predicate,
  `force`...) are written in Scheme in `tulip/prelude.scm`, so continuations
  and tail calls work through them.

## Limits

- **No complex numbers.** `1+2i` is rejected by the reader, and `(sqrt -4)`,
  `(log -1)` and the like raise an error rather than return a complex result.
- **Speed.** This is the reference interpreter: a million-iteration loop
  takes about 3 seconds on a desktop machine. Stage 4's bytecode VM is
  meant to improve on that.
- **Literal strings are immutable** (`string-set!` on a literal is an error,
  as R7RS permits); strings made by `make-string`, `string-copy` and so on
  are mutable.
- **Top-level redefinition of a keyword** (`(define if ...)`) also affects the
  built-in derived forms that expand into it; the library system (stage 3)
  will separate user and system bindings.
- **Continuations and top-level forms.** A program is run one top-level
  form at a time. Invoking a continuation captured in an earlier top-level
  form finishes that form, then carries on with the form that invoked it; it
  does not re-run the forms in between.
- **Only `syntax-rules`.** There are no low-level macro transformers
  (`er-macro-transformer`, `syntax-case`); R7RS-small does not require them.
- **Top-level definitions a macro introduces are not renamed**: a macro that
  expands to `(define helper ...)` at top level defines `helper` itself.
  Internal definitions introduced by a macro are hygienic.
- Not yet implemented (stage 3): libraries (`define-library`, `import`),
  input ports and file I/O, `read`, `eval`, `load`, the process-context
  and time procedures.

## Development

Requires Python 3.9 or newer and nothing else. Run the tests with:

    python -m unittest discover -s tests

## Working on it

Run `cleanvibe` in this folder (or double-click `!runClaude.bat` on Windows) to
open a new Claude session here. It starts with Remote Control on, so you can
continue from the Claude app or web. Earlier sessions are in `sessions/`.
