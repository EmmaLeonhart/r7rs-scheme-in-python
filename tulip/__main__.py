"""``python -m tulip [--engine interp|vm] [FILE [ARG...]]``: run a program,
or start the REPL.

``--engine`` picks the reference interpreter (the default) or the bytecode
VM. Options are only recognized before FILE. The program's ``(command-line)`` is ``(FILE ARG...)``. ``(exit n)`` ends the
process with status n; an uncaught error prints a message to stderr and
exits with status 70.
"""

from __future__ import annotations

import sys

from .printer import write_string
from .prims_system import SchemeExit
from .reader import Reader
from .runtime import ENGINES, Runtime
from .types import EOF, UNSPECIFIED, MultipleValues, SchemeError

BANNER = "tulip %s: R7RS-small Scheme in Python. (exit) or end of input to leave."

ERROR_STATUS = 70   # EX_SOFTWARE


def print_result(value):
    if value is UNSPECIFIED:
        return
    if isinstance(value, MultipleValues):
        for v in value.items:
            print(write_string(v))
    else:
        print(write_string(value))


def repl(rt, out=None, prompt=True):
    """Read-eval-print until end of input. Errors are reported and the loop
    carries on; a datum may span several lines."""
    from . import __version__
    if prompt:
        print(BANNER % __version__)
    buffer = ""
    while True:
        try:
            line = input(("tulip> " if not buffer else "  ... ") if prompt else "")
        except EOFError:
            if prompt:
                print()
            return 0
        except KeyboardInterrupt:
            print("\n(interrupted)")
            buffer = ""
            continue
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
                continue        # incomplete datum: read another line
            print("read error: %s" % e)
            buffer = ""
            continue
        buffer = ""
        for datum in forms:
            try:
                print_result(rt.eval(datum))
            except SchemeError as e:
                sys.stdout.flush()
                print("error: %s" % e)
                break
            except KeyboardInterrupt:
                print("\n(interrupted)")
                break
        sys.stdout.flush()


USAGE = "usage: python -m tulip [--engine interp|vm] [FILE [ARG...]]"


def parse_options(argv):
    """Split leading options off ``argv``; return (engine, rest)."""
    engine = "interp"
    argv = list(argv)
    while argv and argv[0].startswith("--"):
        opt = argv.pop(0)
        if opt == "--":
            break
        if opt == "--engine" and argv:
            engine = argv.pop(0)
        elif opt.startswith("--engine="):
            engine = opt[len("--engine="):]
        else:
            raise ValueError("unknown option %s" % opt)
        if engine not in ENGINES:
            raise ValueError("unknown engine %r (choose from %s)"
                             % (engine, ", ".join(ENGINES)))
    return engine, argv


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        engine, argv = parse_options(argv)
    except ValueError as e:
        print("error: %s\n%s" % (e, USAGE), file=sys.stderr)
        return 2
    try:
        if not argv:
            rt = Runtime(["tulip"], engine=engine)
            return repl(rt, prompt=sys.stdin.isatty())
        rt = Runtime(argv, engine=engine)
        try:
            rt.load_file(argv[0])
        except SchemeError as e:
            sys.stdout.flush()
            print("error: %s" % e, file=sys.stderr)
            return ERROR_STATUS
        except OSError as e:
            print("error: cannot read %s: %s" % (argv[0], e.strerror), file=sys.stderr)
            return ERROR_STATUS
        return 0
    except SchemeExit as e:
        return e.code
    finally:
        sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
