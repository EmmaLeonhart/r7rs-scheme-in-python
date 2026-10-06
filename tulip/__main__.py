"""``python -m tulip [FILE]``: run a program, or start a simple REPL."""

from __future__ import annotations

import sys

from .printer import write_string
from .reader import Reader
from .runtime import Runtime
from .types import EOF, UNSPECIFIED, SchemeError


def repl(rt):
    buffer = ""
    while True:
        try:
            line = input("tulip> " if not buffer else "  ... ")
        except EOFError:
            print()
            return 0
        buffer += line + "\n"
        reader = Reader(buffer)
        forms = []
        try:
            while True:
                datum = reader.read()
                if datum is EOF:
                    break
                forms.append(datum)
        except SchemeError as e:
            if "end of input" in str(e):
                continue        # incomplete form: read another line
            print("read error: %s" % e)
            buffer = ""
            continue
        buffer = ""
        for datum in forms:
            try:
                value = rt.eval(datum)
            except SchemeError as e:
                print("error: %s" % e)
                break
            if value is not UNSPECIFIED:
                print(write_string(value))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rt = Runtime()
    if not argv:
        return repl(rt)
    try:
        rt.load(argv[0])
    except SchemeError as e:
        sys.stdout.flush()
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
