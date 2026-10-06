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

**Stages 1 to 4 are done**: the interpreter, control and macros,
libraries, ports and the REPL, and the bytecode VM. Run a program with
`python -m tulip program.scm [args...]`, or start the REPL with
`python -m tulip`. Add `--engine vm` (before the file name) to run on the
bytecode VM instead of the reference interpreter.

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

Stage 3 added: `define-library` and `import` (with `only`, `except`,
`prefix`, `rename`), every R7RS-small standard library (`(scheme base)`,
`char`, `complex`, `cxr`, `eval`, `file`, `inexact`, `lazy`, `load`,
`process-context`, `read`, `repl`, `time`, `write`, `r5rs`), libraries loaded
from `name/part.sld` files on a search path, `cond-expand`, `include`,
`include-ci`, `include-library-declarations`, `features`; textual and binary
ports over strings, bytevectors, files and the console (the current ports are
parameters, so `parameterize` and `with-output-to-file` redirect them);
`read`; `eval` with `environment`, `interaction-environment` and the R5RS
environments; `load`; `command-line`, `exit` (which runs pending
`dynamic-wind` after thunks first), `emergency-exit`, environment variables;
`current-second` and `current-jiffy`.

The REPL prints every value of a multiple-value result, keeps going after an
error, and reads a datum across lines. A program's exit status is its
`(exit n)` value, or 70 after an uncaught error (the message goes to stderr).

A program may start with `import` declarations as R7RS programs do. For
convenience, a file without them (and the REPL) sees every standard library.

Next: stage 5, a conformance suite written from the R7RS report (`todo.md`).

## Design

```
text --reader--> data --expander--> core AST --compile--> nodes --machine--> value
                                                 \--vm.compile--> bytecode --VM loop--/
```

The two engines share everything up to the core AST, and the same machine:
the VM is a second way to run code on it, not a separate runtime.

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
- **Libraries** (`tulip/libraries.py`): each library is an environment
  plus an export table. Importing shares bindings: a variable's importer gets
  the exporter's own cell, so imports are live and cost nothing at run time.
  All built-ins live in one system environment and the standard libraries
  export parts of it; user code has its own environment, so redefining `if`
  or `list` there leaves the built-in macros alone.
- **Bytecode VM** (`tulip/vm.py`, `--engine vm`): compiles the same core
  AST to code objects (parallel lists of opcodes and operands, lexical
  addresses as in the interpreter) for a stack machine, run by one Python
  loop that keeps `code`, `pc`, `env` and the operand stack in locals.
  Calls and returns between VM closures stay in the loop, as do `apply`,
  `call/cc` and continuation calls that cross no `dynamic-wind`. A non-tail
  call pushes a `VMFrame`, which is an ordinary machine continuation frame,
  so call/cc, dynamic-wind, handlers and parameters work unchanged and VM
  and interpreter procedures call each other. A frame saves the pending
  operand stack as a tuple, so re-entering a continuation twice is safe.
  Calls to hot built-ins (`+`, `car`, `<`, `cons`, `null?`...) compile to
  specialized opcodes that check at run time that the global still holds the
  built-in (and, for arithmetic, that the operands are fixnums) and otherwise
  make an ordinary call, a tail call in tail position. The interpreter stays
  the reference: the whole test suite runs on both, in CI too.
- **Primitives** are Python functions (`tulip/prims_*.py`); procedures that
  call other procedures (`map`, `for-each`, `member` with a predicate,
  `force`...) are written in Scheme in `tulip/prelude.scm`, so continuations
  and tail calls work through them.

## Limits

- **No complex numbers.** `1+2i` is rejected by the reader, and `(sqrt -4)`,
  `(log -1)` and the like raise an error rather than return a complex result.
- **Speed.** On the benchmarks in `bench/` the VM is about 1.9 times as
  fast as the interpreter overall: 2 to 2.6 times on calls and fixnum
  arithmetic, 1.3 to 1.5 times on closure-heavy and call/cc-heavy code
  (`bench/RESULTS.md`). A 300,000-iteration loop takes about 0.6 s on the
  VM and 1.5 s on the interpreter on a desktop machine. Both are tree- or
  bytecode-walking loops in Python; there is no native code generation.
- **Literal strings are immutable** (`string-set!` on a literal is an error,
  as R7RS permits); strings made by `make-string`, `string-copy` and so on
  are mutable.
- **`(scheme complex)` covers real numbers only**: `real-part`,
  `imag-part`, `angle`, `magnitude` work on reals, and `make-rectangular` /
  `make-polar` work only when the result is real.
- **Programs without `import` see everything.** R7RS says a program sees only
  what it imports; tulip gives a program with no import declarations all the
  standard libraries.
- **Redefining an imported name** at top level (in the REPL or a program)
  shadows it for code compiled afterwards; `set!` of an imported variable is
  an error, as R7RS requires.
- **`char-ready?` on the console** reports whether input is already
  buffered; it cannot see characters the terminal has not delivered.
- **Continuations and top-level forms.** A program is run one top-level
  form at a time. Invoking a continuation captured in an earlier top-level
  form finishes that form, then carries on with the form that invoked it; it
  does not re-run the forms in between.
- **Only `syntax-rules`.** There are no low-level macro transformers
  (`er-macro-transformer`, `syntax-case`); R7RS-small does not require them.
- **Top-level definitions a macro introduces are not renamed**: a macro that
  expands to `(define helper ...)` at top level defines `helper` itself.
  Internal definitions introduced by a macro are hygienic.

## Development

Requires Python 3.9 or newer and nothing else. Run the tests with:

    python -m unittest discover -s tests

Set `TULIP_ENGINE=vm` to run the same suite on the bytecode VM. Compare the
engines with `python bench/run.py` (`--markdown` prints the table in
`bench/RESULTS.md`).

## Working on it

Run `cleanvibe` in this folder (or double-click `!runClaude.bat` on Windows) to
open a new Claude session here. It starts with Remote Control on, so you can
continue from the Claude app or web. Earlier sessions are in `sessions/`.
