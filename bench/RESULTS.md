# Benchmark results

Produced by `python bench/run.py --markdown` (the programs are in
`bench/programs/`; each defines `(run)`). Times are for `(run)` alone, after
the runtime has started and the program has loaded. Both engines must
produce the same result; the runner exits 1 if they don't.

Python 3.13.14 on Windows (win32), best of 3 runs, 2026-10-06.

| program | interpreter (s) | VM (s) | speed-up | results agree |
|---|---:|---:|---:|---|
| callcc | 0.458 | 0.347 | 1.32x | yes |
| closures | 0.763 | 0.534 | 1.43x | yes |
| fib | 0.484 | 0.250 | 1.93x | yes |
| lists | 0.421 | 0.242 | 1.74x | yes |
| loop | 1.448 | 0.637 | 2.27x | yes |
| queens | 0.596 | 0.230 | 2.59x | yes |
| sort | 0.463 | 0.275 | 1.69x | yes |
| strings | 0.409 | 0.229 | 1.79x | yes |
| tak | 0.547 | 0.261 | 2.10x | yes |
| **total** | 5.589 | 3.004 | 1.86x | |

## Reading the numbers

- The VM is about 2 to 2.5 times faster on code made of calls, conditionals
  and fixnum arithmetic (`loop`, `queens`, `tak`, `fib`): these spend their
  time in the VM loop and the specialized opcodes.
- `lists`, `sort` and `strings` gain less (1.7 to 1.9 times), probably because
  more of their time is spent in the built-in procedures themselves, which are the same
  Python functions on both engines.
- `closures` (1.43 times) and `callcc` (1.32 times) gain least. Profiled
  on 2026-10-06: at first every `apply`, `call/cc` and continuation call left
  the VM loop through the machine and re-entered it (90,000 and 120,000
  entries to `run` per benchmark). Those three are now handled inside the
  loop (continuations only when no `dynamic-wind` steps are needed), which
  took `callcc` from 1.09 to 1.32 times and `closures` from 1.36 to 1.43
  times. What remains is ordinary dispatch: both programs are mostly calls
  to closures with few hot built-ins, where the VM's advantage over the
  interpreter is smallest. Cutting that further would mean a different
  dispatch design, not a local fix.
- Single machine, single run of the suite; differences of a few percent are
  noise.
