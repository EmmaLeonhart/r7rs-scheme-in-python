# Benchmark results

Produced by `python bench/run.py --markdown` (the programs are in
`bench/programs/`; each defines `(run)`). Times are for `(run)` alone, after
the runtime has started and the program has loaded. Both engines must
produce the same result; the runner exits 1 if they don't.

Python 3.13.14 on Windows (win32), best of 3 runs, 2026-10-06.

| program | interpreter (s) | VM (s) | speed-up | results agree |
|---|---:|---:|---:|---|
| callcc | 0.492 | 0.450 | 1.09x | yes |
| closures | 0.769 | 0.567 | 1.36x | yes |
| fib | 0.485 | 0.244 | 1.99x | yes |
| lists | 0.418 | 0.248 | 1.69x | yes |
| loop | 1.639 | 0.661 | 2.48x | yes |
| queens | 0.596 | 0.236 | 2.52x | yes |
| sort | 0.491 | 0.284 | 1.73x | yes |
| strings | 0.436 | 0.229 | 1.91x | yes |
| tak | 0.557 | 0.257 | 2.16x | yes |
| **total** | 5.883 | 3.176 | 1.85x | |

## Reading the numbers

- The VM is about 2 to 2.5 times faster on code made of calls, conditionals
  and fixnum arithmetic (`loop`, `queens`, `tak`, `fib`): these spend their
  time in the VM loop and the specialized opcodes.
- `lists`, `sort` and `strings` gain less (1.7 to 1.9 times), probably because
  more of their time is spent in the built-in procedures themselves, which are the same
  Python functions on both engines.
- `closures` (1.36 times) and `callcc` (1.09 times) gain least. Not profiled
  yet: the likely costs are `apply` and rest arguments in `closures`, and
  continuation capture and re-entry in `callcc`, all of which use the same
  machinery on both engines. A profile is a queue item.
- Single machine, single run of the suite; differences of a few percent are
  noise.
