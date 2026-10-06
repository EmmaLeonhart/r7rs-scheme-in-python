# queue.md: work in progress

Delete-only: a finished item is deleted here and recorded in `devlog.md` in the
same commit. Long-horizon goals are in `todo.md`.

## Stage 4: bytecode VM

Design for this stage: a compiler from the core AST (the same one the
interpreter uses, so the expander is shared) to bytecode for a stack VM. Code
objects hold parallel lists of opcodes and operands; the VM runs them in one
Python loop with the hot locals (`code`, `pc`, `env`, `stack`) in Python
locals. VM-to-VM calls and returns stay inside the loop. A non-tail call pushes
a `VMFrame`, which *is* a machine continuation frame (it has `resume(m)` and
`next`), so `call/cc`, `dynamic-wind`, handlers, parameters and `values` work
unchanged, and VM code and interpreter code can call each other. A frame's
pending operand stack is saved as a tuple, so re-entering a continuation
twice is safe. Calls to hot built-ins (`+`, `car`, `<`...) compile to
specialized opcodes that check at run time that the global still holds the
built-in and fall back to an ordinary (tail) call otherwise.

1. `tulip/vm.py`: compiler (constants, lexical and global references with
   lexical addressing, if, sequences, set!/define, lambda, calls and tail
   calls, `let`-style direct application without a closure) and the VM loop.
2. Specialized opcodes for hot primitives with a correct fallback, including
   a tail-call fallback in tail position.
3. `Runtime(engine="vm")`: prelude and user code compiled by the VM;
   `eval` and `load` follow the runtime's engine; CLI flag `--engine vm`.
4. The whole test suite runs under both engines (`TULIP_ENGINE=vm`), in CI
   too, plus VM-specific tests (interop with interpreter closures, re-entry
   through VM frames, redefined built-ins).
5. Benchmarks (`bench/`): a set of programs (fib, tak, loops, list and
   string work, closures, call/cc, a sort, n-queens...), a runner that times
   both engines and checks they agree, and `bench/RESULTS.md`.
6. Stage 4 wrap-up: README design and numbers, devlog, check stage 5.
