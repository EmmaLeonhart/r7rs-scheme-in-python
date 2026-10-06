"""External representations: ``write``, ``write-shared``, ``write-simple``
and ``display``.

``write`` labels only structure that is part of a cycle (``#0=(a . #0#)``),
``write-shared`` labels every pair or vector reached more than once, and
``write-simple`` never labels (and loops on cyclic data, as R7RS allows).
``display`` labels cycles as ``write`` does, so it always terminates.
"""

from __future__ import annotations

from .numbers import number_to_string
from .types import (NIL, Char, ErrorObject, MString, Pair, Symbol,
                    UNSPECIFIED, is_number)

CHAR_WRITE_NAMES = {
    "\x07": "alarm", "\x08": "backspace", "\x7f": "delete", "\x1b": "escape",
    "\n": "newline", "\x00": "null", "\r": "return", " ": "space",
    "\t": "tab",
}

_STRING_ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\t": "\\t",
                   "\r": "\\r", "\x07": "\\a", "\x08": "\\b"}

_SYMBOL_BAD = set(" \t\n\r\f\v()\";'`,|[]{}")


def write_string(obj, mode="write"):
    out = []
    # display labels cycles like write: it must not loop forever (6.13.3)
    labels = _find_labels(obj, mode) if mode != "simple" else {}
    _Printer(out, mode != "display", labels).emit(obj)
    return "".join(out)


def display_string(obj):
    return write_string(obj, "display")


def _find_labels(root, mode):
    """Return {id(node): None} for nodes that need a datum label."""
    if not isinstance(root, (Pair, list)):
        return {}
    need = {}
    if mode == "shared":
        seen = set()
        stack = [root]
        while stack:
            x = stack.pop()
            if not isinstance(x, (Pair, list)):
                continue
            if id(x) in seen:
                need[id(x)] = None
                continue
            seen.add(id(x))
            if isinstance(x, Pair):
                stack.append(x.cdr)
                stack.append(x.car)
            else:
                stack.extend(reversed(x))
        return need
    # mode "write": label only nodes on a cycle (reached again while on the
    # DFS stack). Iterative DFS with explicit enter/exit.
    state = {}  # id -> 1 on stack, 2 done
    stack = [(root, False)]
    while stack:
        x, leaving = stack.pop()
        if leaving:
            state[id(x)] = 2
            continue
        if not isinstance(x, (Pair, list)):
            continue
        s = state.get(id(x))
        if s == 1:
            need[id(x)] = None
            continue
        if s == 2:
            continue
        state[id(x)] = 1
        stack.append((x, True))
        if isinstance(x, Pair):
            stack.append((x.cdr, False))
            stack.append((x.car, False))
        else:
            for item in reversed(x):
                stack.append((item, False))
    return need


class _Printer:
    def __init__(self, out, write, labels):
        self.out = out
        self.write = write
        self.labels = labels       # id -> None (unassigned) or int
        self.counter = 0

    def _label(self, x):
        """Emit a label prefix or reference. Returns True if a reference was
        written (and the object must not be printed again)."""
        if id(x) not in self.labels:
            return False
        n = self.labels[id(x)]
        if n is not None:
            self.out.append("#%d#" % n)
            return True
        n = self.counter
        self.counter += 1
        self.labels[id(x)] = n
        self.out.append("#%d=" % n)
        return False

    def emit(self, x):
        out = self.out
        if x is True:
            out.append("#t")
        elif x is False:
            out.append("#f")
        elif is_number(x):
            out.append(number_to_string(x))
        elif isinstance(x, Symbol):
            out.append(write_symbol(x.name) if self.write else x.name)
        elif isinstance(x, MString):
            out.append(write_string_literal(x.s) if self.write else x.s)
        elif isinstance(x, Char):
            out.append(write_char(x.ch) if self.write else x.ch)
        elif isinstance(x, str):          # Python strings used as irritants
            out.append(write_string_literal(x) if self.write else x)
        elif x is NIL:
            out.append("()")
        elif isinstance(x, Pair):
            self._emit_pair(x)
        elif isinstance(x, list):
            if self.labels and self._label(x):
                return
            out.append("#(")
            for i, item in enumerate(x):
                if i:
                    out.append(" ")
                self.emit(item)
            out.append(")")
        elif isinstance(x, bytearray):
            out.append("#u8(" + " ".join(str(b) for b in x) + ")")
        elif x is UNSPECIFIED:
            out.append("")
        elif isinstance(x, ErrorObject):
            out.append("#<error " + format_condition(x) + ">")
        else:
            out.append(repr(x))

    def _emit_pair(self, x):
        out = self.out
        if self.labels and self._label(x):
            return
        # quote abbreviations
        if isinstance(x.car, Symbol) and isinstance(x.cdr, Pair) \
                and x.cdr.cdr is NIL and id(x.cdr) not in self.labels:
            prefix = _ABBREV.get(x.car.name)
            if prefix:
                out.append(prefix)
                self.emit(x.cdr.car)
                return
        out.append("(")
        self.emit(x.car)
        p = x.cdr
        while True:
            if p is NIL:
                break
            if isinstance(p, Pair) and not (self.labels and id(p) in self.labels):
                out.append(" ")
                self.emit(p.car)
                p = p.cdr
                continue
            out.append(" . ")
            self.emit(p)
            break
        out.append(")")


_ABBREV = {"quote": "'", "quasiquote": "`", "unquote": ",",
           "unquote-splicing": ",@"}


def write_symbol(name):
    from .numbers import parse_number
    if name == "" or any(c in _SYMBOL_BAD for c in name) or name == "." \
            or name[0] == "#" or _parses_as_number(name, parse_number) \
            or any(ord(c) < 32 or ord(c) > 126 for c in name):
        # R7RS 6.13.3: symbols with non-ASCII characters are written with
        # vertical lines
        return "|" + "".join(_symbol_escape(c) for c in name) + "|"
    return name


def _parses_as_number(name, parse_number):
    try:
        return parse_number(name) is not None
    except Exception:
        return True


def _symbol_escape(c):
    if c == "|":
        return "\\|"
    if c == "\\":
        return "\\\\"
    if ord(c) < 32 or ord(c) == 127:
        return "\\x%x;" % ord(c)
    return c


def write_string_literal(s):
    parts = ['"']
    for c in s:
        e = _STRING_ESCAPES.get(c)
        if e is not None:
            parts.append(e)
        elif ord(c) < 32 or ord(c) == 127:
            parts.append("\\x%x;" % ord(c))
        else:
            parts.append(c)
    parts.append('"')
    return "".join(parts)


def write_char(ch):
    name = CHAR_WRITE_NAMES.get(ch)
    if name:
        return "#\\" + name
    if ord(ch) < 32 or not ch.isprintable():
        return "#\\x%x" % ord(ch)
    return "#\\" + ch


def format_condition(payload):
    """Human-readable text for a raised object (used in error messages)."""
    if isinstance(payload, ErrorObject):
        msg = payload.message
        if isinstance(msg, MString):
            msg = msg.s
        parts = [str(msg)]
        for irritant in payload.irritants:
            parts.append(write_string(irritant))
        return " ".join(parts)
    return "non-condition object raised: " + write_string(payload)
