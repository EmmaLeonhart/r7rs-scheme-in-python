"""The core language the expander produces.

Every surface form expands into these nodes. Lexical variables are ``Var``
objects (unique per binding, so the core has no name clashes and no hygiene
left to do); globals are ``Cell`` objects from an ``Environment``. Both the
interpreter (interp.py) and the bytecode compiler work from this AST.
"""

from __future__ import annotations


class Frame:
    """The variables of one lambda: parameters first, then the body's
    internal definitions, in order."""
    __slots__ = ("vars",)

    def __init__(self):
        self.vars = []

    def new_var(self, name):
        v = Var(name, self, len(self.vars))
        self.vars.append(v)
        return v


class Var:
    __slots__ = ("name", "frame", "index", "assigned", "captured", "defined")

    def __init__(self, name, frame, index):
        self.name = name          # a Symbol, for error messages
        self.frame = frame
        self.index = index
        self.assigned = False     # set! anywhere (filled by the expander)
        self.captured = False     # reserved for compilers
        self.defined = False      # bound by an internal define (may be unassigned)

    def __repr__(self):
        return "<var %s>" % getattr(self.name, "name", self.name)


class Node:
    __slots__ = ()


class Const(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class LocalRef(Node):
    __slots__ = ("var",)

    def __init__(self, var):
        self.var = var


class GlobalRef(Node):
    __slots__ = ("cell",)

    def __init__(self, cell):
        self.cell = cell


class LocalSet(Node):
    __slots__ = ("var", "expr")

    def __init__(self, var, expr):
        self.var = var
        self.expr = expr


class GlobalSet(Node):
    __slots__ = ("cell", "expr")

    def __init__(self, cell, expr):
        self.cell = cell
        self.expr = expr


class LocalDefine(Node):
    """An internal definition: initialize a slot of the current frame."""
    __slots__ = ("var", "expr")

    def __init__(self, var, expr):
        self.var = var
        self.expr = expr


class GlobalDefine(Node):
    __slots__ = ("cell", "expr")

    def __init__(self, cell, expr):
        self.cell = cell
        self.expr = expr


class If(Node):
    __slots__ = ("test", "then", "else_")

    def __init__(self, test, then, else_):
        self.test = test
        self.then = then
        self.else_ = else_


class Lambda(Node):
    """``nreq`` required parameters, then a rest parameter if ``rest``.

    ``frame.vars`` holds the parameters followed by internal definitions.
    """
    __slots__ = ("frame", "nreq", "rest", "body", "name")

    def __init__(self, frame, nreq, rest, body, name=None):
        self.frame = frame
        self.nreq = nreq
        self.rest = rest
        self.body = body          # a single Node (Seq for several)
        self.name = name


class Seq(Node):
    __slots__ = ("exprs",)

    def __init__(self, exprs):
        self.exprs = exprs


class App(Node):
    __slots__ = ("fn", "args")

    def __init__(self, fn, args):
        self.fn = fn
        self.args = args


def seq(nodes):
    if not nodes:
        from .types import UNSPECIFIED
        return Const(UNSPECIFIED)
    if len(nodes) == 1:
        return nodes[0]
    return Seq(list(nodes))
