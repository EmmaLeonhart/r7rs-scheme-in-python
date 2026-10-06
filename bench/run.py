"""Time the benchmark programs on both engines and check they agree.

    python bench/run.py [--repeat N] [--markdown] [NAME ...]

Each program in ``bench/programs/`` defines ``(run)``. For each engine the
program is loaded into a fresh runtime (start-up and loading are not timed),
then ``(run)`` is called ``N`` times (default 3) and the best time is kept.
The two engines' results must print the same; a mismatch is reported and the
exit status is 1. ``--markdown`` prints a table for ``bench/RESULTS.md``.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from tulip.printer import write_string  # noqa: E402
from tulip.runtime import ENGINES, Runtime  # noqa: E402

PROGRAMS = HERE / "programs"


def time_program(path, engine, repeat):
    rt = Runtime(engine=engine)
    rt.load_file(path)
    best = None
    result = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = rt.eval_string("(run)")
        elapsed = time.perf_counter() - start
        best = elapsed if best is None else min(best, elapsed)
    return best, write_string(result)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("names", nargs="*", help="programs to run (default: all)")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--markdown", action="store_true")
    opts = ap.parse_args(argv)

    paths = sorted(PROGRAMS.glob("*.scm"))
    if opts.names:
        paths = [p for p in paths if p.stem in opts.names]
    rows = []
    mismatches = 0
    for path in paths:
        times, results = {}, {}
        for engine in ENGINES:
            times[engine], results[engine] = time_program(path, engine, opts.repeat)
        agree = len(set(results.values())) == 1
        mismatches += not agree
        rows.append((path.stem, times["interp"], times["vm"], agree, results))
        if not opts.markdown:
            print("%-10s interp %7.3f s   vm %7.3f s   x%.2f%s" % (
                path.stem, times["interp"], times["vm"], times["interp"] / times["vm"],
                "" if agree else "   MISMATCH %r" % results), flush=True)

    if opts.markdown:
        print("Python %s on %s (%s), best of %d runs, %s.\n" % (
            platform.python_version(), platform.system(), sys.platform,
            opts.repeat, time.strftime("%Y-%m-%d")))
        print("| program | interpreter (s) | VM (s) | speed-up | results agree |")
        print("|---|---:|---:|---:|---|")
        for name, ti, tv, agree, _ in rows:
            print("| %s | %.3f | %.3f | %.2fx | %s |" % (name, ti, tv, ti / tv,
                                                        "yes" if agree else "NO"))
        ti = sum(r[1] for r in rows)
        tv = sum(r[2] for r in rows)
        print("| **total** | %.3f | %.3f | %.2fx | |" % (ti, tv, ti / tv))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
