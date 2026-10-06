"""Scheme data types.

Representation choices:

- booleans are Python ``True``/``False`` (number predicates exclude ``bool``);
- exact integers are ``int``, exact rationals ``fractions.Fraction`` (always
  normalized: a whole-number rational is an ``int``), inexact reals ``float``;
- symbols are interned ``Symbol`` objects (``Symbol.uninterned`` makes fresh
  ones, which the expander uses for renamed variables);
- the empty list is the singleton ``NIL``; pairs are ``Pair``;
- strings are mutable ``MString`` (Python ``str`` is immutable);
- characters are ``Char``;
- vectors are Python ``list``; bytevectors are ``bytearray``.
"""

from __future__ import annotations


class Symbol:
    __slots__ = ("name", "interned")
    table: dict = {}

    def __init__(self, name: str, interned: bool = True):
        self.name = name
        self.interned = interned

    @classmethod
    def intern(cls, name: str) -> "Symbol":
        sym = cls.table.get(name)
        if sym is None:
            sym = cls(name)
            cls.table[name] = sym
        return sym

    @classmethod
    def uninterned(cls, name: str) -> "Symbol":
        return cls(name, interned=False)

    def __repr__(self):
        return self.name if self.interned else "#<uninterned %s>" % self.name


def sym(name: str) -> Symbol:
    return Symbol.intern(name)


class Nil:
    __slots__ = ()

    def __repr__(self):
        return "()"

    def __iter__(self):
        return iter(())

    def __bool__(self):  # never used as a Scheme boolean; guards Python mistakes
        return True


NIL = Nil()


class Pair:
    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __iter__(self):
        """Iterate the cars of a proper (or improper: the tail is dropped) list."""
        p = self
        while isinstance(p, Pair):
            yield p.car
            p = p.cdr

    def __repr__(self):
        from .printer import write_string
        return write_string(self)


def make_list(items, tail=NIL):
    result = tail
    for item in reversed(list(items)):
        result = Pair(item, result)
    return result


def list_to_python(lst, who="list"):
    """Convert a proper Scheme list to a Python list, or raise."""
    out = []
    p = lst
    while isinstance(p, Pair):
        out.append(p.car)
        p = p.cdr
    if p is not NIL:
        raise SchemeError("%s: not a proper list" % who, lst)
    return out


class Char:
    __slots__ = ("ch",)
    _cache: dict = {}

    def __new__(cls, ch: str):
        c = cls._cache.get(ch)
        if c is None:
            c = object.__new__(cls)
            c.ch = ch
            if len(cls._cache) < 4096:
                cls._cache[ch] = c
        return c

    def __eq__(self, other):
        return isinstance(other, Char) and other.ch == self.ch

    def __hash__(self):
        return hash(("char", self.ch))

    def __repr__(self):
        from .printer import write_string
        return write_string(self)


class MString:
    """A mutable Scheme string. ``s`` holds the current contents."""
    __slots__ = ("s", "immutable")

    def __init__(self, s: str, immutable: bool = False):
        self.s = s
        self.immutable = immutable

    def __repr__(self):
        from .printer import write_string
        return write_string(self)


class Unspecified:
    __slots__ = ()

    def __repr__(self):
        return "#<unspecified>"


UNSPECIFIED = Unspecified()


class Eof:
    __slots__ = ()

    def __repr__(self):
        return "#<eof>"


EOF = Eof()


class DefaultObject:
    """Marks an unassigned variable (letrec semantics) internally."""
    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return "#<%s>" % self.label


UNASSIGNED = DefaultObject("unassigned")


# --- procedures --------------------------------------------------------------

class Procedure:
    __slots__ = ()
    name = None


class Primitive(Procedure):
    """A Python function that needs no access to the machine.

    ``nreq`` required args, ``nopt`` optional ones; ``rest`` allows any number
    more.
    """
    __slots__ = ("fn", "name", "nreq", "nopt", "rest")

    def __init__(self, fn, name, nreq, nopt=0, rest=False):
        self.fn = fn
        self.name = name
        self.nreq = nreq
        self.nopt = nopt
        self.rest = rest

    def __repr__(self):
        return "#<procedure %s>" % self.name


class ControlPrimitive(Procedure):
    """A primitive that manipulates the machine (apply, call/cc, values...).

    ``fn(machine, args)`` must leave the machine in a valid state: either set
    ``machine.val`` (with ``machine.node = None``) or set up a tail call.
    """
    __slots__ = ("fn", "name", "nreq", "nopt", "rest")

    def __init__(self, fn, name, nreq, nopt=0, rest=False):
        self.fn = fn
        self.name = name
        self.nreq = nreq
        self.nopt = nopt
        self.rest = rest

    def __repr__(self):
        return "#<procedure %s>" % self.name


class Closure(Procedure):
    __slots__ = ("code", "env")

    def __init__(self, code, env):
        self.code = code      # interp.LambdaCode
        self.env = env

    @property
    def name(self):
        return self.code.name

    def __repr__(self):
        return "#<procedure %s>" % (self.code.name or "anonymous")


class CaseLambda(Procedure):
    __slots__ = ("clauses", "name")

    def __init__(self, clauses, name=None):
        self.clauses = clauses  # list of Closure
        self.name = name

    def __repr__(self):
        return "#<procedure %s>" % (self.name or "case-lambda")


# --- other runtime objects ----------------------------------------------------

class MultipleValues:
    """Zero or several values, as returned by ``values`` (one value is just
    the value itself)."""
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = list(items)

    def __repr__(self):
        return "#<values %d>" % len(self.items)


def values(*items):
    return items[0] if len(items) == 1 else MultipleValues(items)


class Promise:
    """R7RS promise. ``box`` is shared between promises chained by delay-force."""
    __slots__ = ("box",)

    def __init__(self, done, value):
        self.box = [done, value]

    def __repr__(self):
        return "#<promise>"


class RecordType:
    __slots__ = ("name", "fields")

    def __init__(self, name, fields):
        self.name = name
        self.fields = fields  # list of Symbol

    def __repr__(self):
        return "#<record-type %s>" % self.name


class Record:
    __slots__ = ("rtype", "values")

    def __init__(self, rtype, values):
        self.rtype = rtype
        self.values = values

    def __repr__(self):
        return "#<%s>" % self.rtype.name


class Environment:
    """A global (top-level) environment: values plus syntactic bindings.

    An imported variable's cell is the exporting library's own cell. A
    top-level ``define`` of an imported name gives this environment a fresh
    cell instead (REPL-style shadowing); ``set!`` of one is an error."""

    def __init__(self, name="user"):
        self.name = name
        self.cells: dict = {}     # Symbol -> Cell
        self.syntax: dict = {}    # Symbol -> expander binding (keywords, macros)
        self.imported: set = set()  # variables imported from a library
        self.expander = None      # set by the runtime

    def cell(self, symbol: Symbol) -> "Cell":
        c = self.cells.get(symbol)
        if c is None:
            c = Cell(symbol)
            self.cells[symbol] = c
        return c

    def define(self, name, value):
        if isinstance(name, str):
            name = sym(name)
        self.syntax.pop(name, None)
        if name in self.imported:
            self.imported.discard(name)
            self.cells[name] = Cell(name)
        self.cell(name).value = value

    def lookup(self, name):
        if isinstance(name, str):
            name = sym(name)
        c = self.cells.get(name)
        if c is None or c.value is UNBOUND:
            raise SchemeError("unbound variable", name)
        return c.value


class Unbound:
    __slots__ = ()

    def __repr__(self):
        return "#<unbound>"


UNBOUND = Unbound()


class Cell:
    __slots__ = ("symbol", "value")

    def __init__(self, symbol, value=UNBOUND):
        self.symbol = symbol
        self.value = value


# --- errors -------------------------------------------------------------------

class ErrorObject:
    """What ``error`` raises: a message and a list of irritants.

    ``kind`` distinguishes the R7RS predicates: None, "read" or "file".
    """
    __slots__ = ("message", "irritants", "kind")

    def __init__(self, message, irritants=(), kind=None):
        self.message = message
        self.irritants = list(irritants)
        self.kind = kind

    def __repr__(self):
        return "#<error %s>" % self.message


class SchemeError(Exception):
    """A Scheme-level error raised from Python code.

    ``payload`` is the raised Scheme object: an ``ErrorObject`` for errors
    signalled by the implementation or by ``error``, any object for ``raise``.
    """

    def __init__(self, message, *irritants, payload=None, kind=None):
        if payload is None:
            payload = ErrorObject(message, irritants, kind)
        self.payload = payload
        super().__init__(message)

    def __str__(self):
        from .printer import format_condition
        return format_condition(self.payload)


def is_true(x):
    return x is not False


def is_number(x):
    return (type(x) in (int, float)) or isinstance(x, _Fraction)


from fractions import Fraction as _Fraction  # noqa: E402
