"""Run the R7RS conformance suite on tulip's engines.

    python conformance/run.py [--engine interp|vm|both] [--verbose] [FILE ...]

Each ``conformance/*.scm`` file is a program for one section of the
R7RS-small report, using the ``(conformance test)`` library. It is run as
``python -m tulip --engine E FILE`` and its output parsed (see
``conformance/conformance/test.sld``). A file passes when it prints a
SUMMARY with no FAIL and no XPASS and exits 0. With both engines, the two
outputs must also be identical. Exit status 1 if anything is unexpected.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINES = ("interp", "vm")
TIMEOUT = 180   # seconds per file and engine; a hang is reported, not waited out


def section_files():
    def key(p):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)]
    return sorted(HERE.glob("*.scm"), key=key)


def run_file(path, engine):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, "-m", "tulip", "--engine", engine, str(path)],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=str(HERE), timeout=TIMEOUT)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return -1, out, "timed out after %d s" % TIMEOUT
    return r.returncode, r.stdout, r.stderr


class Result:
    def __init__(self, path, engine, code, out, err):
        self.path, self.engine = path, engine
        self.out, self.err, self.code = out, err, code
        self.lines = {"FAIL": [], "XFAIL": [], "XPASS": []}
        self.summary = None
        for line in out.splitlines():
            kind = line.split("\t", 1)[0]
            if kind in self.lines:
                self.lines[kind].append(line)
            elif kind == "SUMMARY":
                self.summary = [int(x) for x in line.split("\t")[1:]]

    @property
    def ok(self):
        return (self.code == 0 and self.summary is not None
                and not self.lines["FAIL"] and not self.lines["XPASS"])

    def describe(self):
        if self.summary is None:
            return "no summary (exit %d): %s" % (self.code, self.err.strip()[-300:])
        p, f, xf, xp = self.summary
        return "%4d pass %3d fail %3d xfail %3d xpass" % (p, f, xf, xp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--engine", choices=ENGINES + ("both",), default="both")
    ap.add_argument("--verbose", action="store_true", help="also list XFAIL lines")
    opts = ap.parse_args(argv)

    engines = ENGINES if opts.engine == "both" else (opts.engine,)
    paths = [Path(f).resolve() for f in opts.files] if opts.files else section_files()
    bad = 0
    totals = [0, 0, 0, 0]
    for path in paths:
        results = [Result(path, e, *run_file(path, e)) for e in engines]
        for r in results:
            print("%-28s %-6s %s%s" % (path.name, r.engine, r.describe(),
                                       "" if r.ok else "   <-- UNEXPECTED"), flush=True)
            for line in r.lines["FAIL"] + r.lines["XPASS"]:
                print("    " + line.replace("\t", " | "))
            if opts.verbose:
                for line in r.lines["XFAIL"]:
                    print("    " + line.replace("\t", " | "))
            bad += not r.ok
            if r.summary:
                totals = [a + b for a, b in zip(totals, r.summary)]
        if len(results) == 2 and results[0].out != results[1].out:
            bad += 1
            print("    the engines' outputs differ   <-- UNEXPECTED")
    print("total: %d pass, %d fail, %d xfail, %d xpass (over %s)" % (
        tuple(totals) + (" and ".join(engines),)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
