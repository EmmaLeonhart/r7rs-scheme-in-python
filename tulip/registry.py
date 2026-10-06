"""Where primitive procedures are registered before a runtime installs them."""

from __future__ import annotations

from .types import ControlPrimitive, Primitive

PRIMITIVES: dict = {}


def prim(name, nreq, nopt=0, rest=False):
    """Register a Python function as a Scheme primitive."""
    def deco(fn):
        PRIMITIVES[name] = Primitive(fn, name, nreq, nopt, rest)
        return fn
    return deco


def control(name, nreq, nopt=0, rest=False):
    """Register a machine-level primitive: ``fn(machine, args)``."""
    def deco(fn):
        PRIMITIVES[name] = ControlPrimitive(fn, name, nreq, nopt, rest)
        return fn
    return deco


def alias(new, old):
    PRIMITIVES[new] = PRIMITIVES[old]
