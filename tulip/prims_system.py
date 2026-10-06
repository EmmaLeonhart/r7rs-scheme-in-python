"""eval and environments, load, the process context, time, and the
real-number subset of (scheme complex)."""

from __future__ import annotations

import math
import os
import time

from .control import Continuation
from .interp import apply_procedure
from .registry import control, prim
from .types import (Environment, MString, Pair, SchemeError, UNSPECIFIED,
                    is_number, make_list, sym)


class SchemeExit(Exception):
    """Raised by exit / emergency-exit; not a Scheme condition, so no Scheme
    handler sees it."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _exit_code(args):
    if not args or args[0] is True:
        return 0
    if args[0] is False:
        return 1
    if type(args[0]) is int:
        return args[0]
    return 1


# --- eval and environments -------------------------------------------------------------

@control("eval", 1, 1)
def eval_(m, args):
    env = args[1] if len(args) > 1 else m.runtime.env
    if not isinstance(env, Environment):
        raise SchemeError("eval: not an environment", env)
    m.node = m.runtime.compile(args[0], env)
    m.env = None


@control("environment", 0, rest=True)
def environment(m, args):
    env = m.runtime.new_environment(args, "eval")
    env.immutable = True
    m.val = env
    m.node = None


@control("interaction-environment", 0)
def interaction_environment(m, args):
    m.val = m.runtime.env
    m.node = None


def _r5rs_environment(who):
    def make(m, args):
        if args[0] != 5:
            raise SchemeError("%s: only version 5 is supported" % who, args[0])
        m.val = m.runtime.new_environment(
            [make_list([sym("scheme"), sym("r5rs")])], "r5rs")
        m.node = None
    control(who, 1)(make)


_r5rs_environment("scheme-report-environment")
_r5rs_environment("null-environment")


@control("load", 1, 1)
def load(m, args):
    path = args[0]
    if type(path) is not MString:
        raise SchemeError("load: not a string", path)
    env = args[1] if len(args) > 1 else m.runtime.env
    full = os.path.join(m.runtime.current_dir(), path.s)
    if not os.path.isfile(full):
        raise SchemeError("load: no such file", path, kind="file")
    m.runtime.load_file(full, env)
    m.val = UNSPECIFIED
    m.node = None


# --- process context ---------------------------------------------------------------------

@control("command-line", 0)
def command_line(m, args):
    m.val = make_list([MString(a) for a in m.runtime.argv])
    m.node = None


class _ExitFrame:
    __slots__ = ("code", "next")

    def __init__(self, code):
        self.code = code
        self.next = None

    def resume(self, m):
        raise SchemeExit(self.code)


@control("exit", 0, 1)
def exit_(m, args):
    """Run the outstanding dynamic-wind after thunks, then exit: done by
    invoking a continuation whose dynamic state is empty."""
    cont = Continuation(_ExitFrame(_exit_code(args)), None, None, None)
    apply_procedure(m, cont, [UNSPECIFIED])


@prim("emergency-exit", 0, 1)
def emergency_exit(*args):
    raise SchemeExit(_exit_code(args))


@prim("get-environment-variable", 1)
def get_environment_variable(name):
    if type(name) is not MString:
        raise SchemeError("get-environment-variable: not a string", name)
    v = os.environ.get(name.s)
    return False if v is None else MString(v)


@prim("get-environment-variables", 0)
def get_environment_variables():
    return make_list([Pair(MString(k), MString(v)) for k, v in os.environ.items()])


# --- time ---------------------------------------------------------------------------------

@prim("current-second", 0)
def current_second():
    return time.time()


@prim("current-jiffy", 0)
def current_jiffy():
    return time.perf_counter_ns()


@prim("jiffies-per-second", 0)
def jiffies_per_second():
    return 1000000000


# --- (scheme complex), real numbers only -----------------------------------------------------

def _real(x, who):
    if not is_number(x):
        raise SchemeError("%s: not a number" % who, x)
    return x


@prim("real-part", 1)
def real_part(x):
    return _real(x, "real-part")


@prim("imag-part", 1)
def imag_part(x):
    _real(x, "imag-part")
    return 0


@prim("angle", 1)
def angle(x):
    _real(x, "angle")
    if x < 0 or (type(x) is float and math.copysign(1.0, x) < 0 and x == 0):
        return math.pi
    return 0 if type(x) is not float else 0.0


@prim("make-rectangular", 2)
def make_rectangular(re, im):
    _real(re, "make-rectangular")
    if _real(im, "make-rectangular") != 0:
        raise SchemeError("complex numbers are not supported", re, im)
    return re


@prim("make-polar", 2)
def make_polar(mag, ang):
    _real(mag, "make-polar")
    if _real(ang, "make-polar") == 0:
        return mag
    if type(ang) is float and abs(ang) == math.pi:
        return -mag if type(mag) is not float else -float(mag)
    raise SchemeError("complex numbers are not supported", mag, ang)
