"""The reader: R7RS external representations to Scheme data.

Supports lists and dotted pairs, the quote / quasiquote / unquote /
unquote-splicing abbreviations, vectors ``#(``, bytevectors ``#u8(``,
characters (``#\\a``, named, ``#\\x41``), strings with escapes (including
line continuations), numbers (see numbers.py), ``|symbols|``, booleans
(``#t #f #true #false``), line comments, nested block comments ``#| |#``,
datum comments ``#;``, the ``#!fold-case`` / ``#!no-fold-case`` directives,
and datum labels ``#n=`` / ``#n#`` for shared and circular structure.
"""

from __future__ import annotations

from .numbers import parse_number
from .types import (NIL, Char, MString, Pair, SchemeError, Symbol, sym)

DELIMITERS = set(" \t\n\r\f\v()[]\";|")

CHAR_NAMES = {
    "alarm": "\x07", "backspace": "\x08", "delete": "\x7f", "escape": "\x1b",
    "newline": "\n", "null": "\x00", "return": "\r", "space": " ",
    "tab": "\t",
}

STRING_ESCAPES = {"a": "\x07", "b": "\x08", "t": "\t", "n": "\n", "r": "\r",
                  '"': '"', "\\": "\\", "|": "|"}

QUOTE = sym("quote")
QUASIQUOTE = sym("quasiquote")
UNQUOTE = sym("unquote")
UNQUOTE_SPLICING = sym("unquote-splicing")


class ReadError(SchemeError):
    def __init__(self, message, *irritants):
        super().__init__(message, *irritants, kind="read")


class _Close:
    def __init__(self, ch):
        self.ch = ch


class _Dot:
    pass


_DOT = _Dot()


class _Placeholder:
    """Stands in for a datum label whose datum is still being read."""
    __slots__ = ("label", "value", "resolved")

    def __init__(self, label):
        self.label = label
        self.value = None
        self.resolved = False


class Reader:
    def __init__(self, text: str, fold_case: bool = False):
        self.text = text
        self.pos = 0
        self.fold_case = fold_case
        self.labels: dict = {}

    # --- public -----------------------------------------------------------

    def read(self):
        """Read one datum; return the EOF object at end of input."""
        from .types import EOF
        self.labels = {}
        while True:
            obj = self._read()
            if obj is None:
                return EOF
            if isinstance(obj, _Close):
                raise ReadError("unexpected '%s'" % obj.ch)
            if obj is _DOT:
                raise ReadError("unexpected '.'")
            if self._has_placeholders:
                obj = self._patch(obj)
            return obj

    def read_all(self):
        from .types import EOF
        out = []
        while True:
            obj = self.read()
            if obj is EOF:
                return out
            out.append(obj)

    # --- internals --------------------------------------------------------

    _has_placeholders = False

    def _peek(self):
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _skip_atmosphere(self):
        text = self.text
        n = len(text)
        while self.pos < n:
            c = text[self.pos]
            if c in " \t\n\r\f\v":
                self.pos += 1
            elif c == ";":
                while self.pos < n and text[self.pos] != "\n":
                    self.pos += 1
            elif c == "#" and self.pos + 1 < n and text[self.pos + 1] == "|":
                self._skip_block_comment()
            elif c == "#" and self.pos + 1 < n and text[self.pos + 1] == ";":
                self.pos += 2
                obj = self._read()
                if obj is None or isinstance(obj, _Close) or obj is _DOT:
                    raise ReadError("datum comment without a datum")
            elif c == "#" and text.startswith("#!", self.pos):
                end = self.pos + 2
                while end < n and text[end] not in DELIMITERS:
                    end += 1
                directive = text[self.pos + 2:end]
                if directive == "fold-case":
                    self.fold_case = True
                elif directive == "no-fold-case":
                    self.fold_case = False
                else:
                    return  # not a directive we skip; let _read report it
                self.pos = end
            else:
                return

    def _skip_block_comment(self):
        depth = 0
        text = self.text
        while True:
            if self.pos >= len(text):
                raise ReadError("end of input in block comment")
            if text.startswith("#|", self.pos):
                depth += 1
                self.pos += 2
            elif text.startswith("|#", self.pos):
                depth -= 1
                self.pos += 2
                if depth == 0:
                    return
            else:
                self.pos += 1

    def _read(self):
        self._skip_atmosphere()
        if self.pos >= len(self.text):
            return None
        c = self.text[self.pos]
        if c in "([":
            self.pos += 1
            return self._read_list(")" if c == "(" else "]")
        if c in ")]":
            self.pos += 1
            return _Close(c)
        if c == "'":
            self.pos += 1
            return self._abbrev(QUOTE)
        if c == "`":
            self.pos += 1
            return self._abbrev(QUASIQUOTE)
        if c == ",":
            self.pos += 1
            if self._peek() == "@":
                self.pos += 1
                return self._abbrev(UNQUOTE_SPLICING)
            return self._abbrev(UNQUOTE)
        if c == '"':
            self.pos += 1
            return MString(self._read_string_body('"'), immutable=True)
        if c == "|":
            self.pos += 1
            return Symbol.intern(self._read_string_body("|"))
        if c == "#":
            return self._read_hash()
        return self._read_atom()

    def _abbrev(self, symbol):
        obj = self._read()
        if obj is None or isinstance(obj, _Close) or obj is _DOT:
            raise ReadError("expected a datum after %s" % symbol.name)
        return Pair(symbol, Pair(obj, NIL))

    def _read_list(self, close):
        items = []
        tail = NIL
        while True:
            obj = self._read()
            if obj is None:
                raise ReadError("end of input in list")
            if isinstance(obj, _Close):
                if obj.ch != close:
                    raise ReadError("mismatched '%s'" % obj.ch)
                break
            if obj is _DOT:
                if not items:
                    raise ReadError("'.' at start of list")
                tail = self._read()
                if tail is None or isinstance(tail, _Close) or tail is _DOT:
                    raise ReadError("bad dotted list")
                end = self._read()
                if not isinstance(end, _Close) or end.ch != close:
                    raise ReadError("more than one datum after '.'")
                break
            items.append(obj)
        result = tail
        for item in reversed(items):
            result = Pair(item, result)
        return result

    def _read_string_body(self, quote):
        text = self.text
        out = []
        while True:
            if self.pos >= len(text):
                raise ReadError("end of input in string")
            c = text[self.pos]
            self.pos += 1
            if c == quote:
                return "".join(out)
            if c != "\\":
                out.append(c)
                continue
            if self.pos >= len(text):
                raise ReadError("end of input in string")
            e = text[self.pos]
            self.pos += 1
            if e in STRING_ESCAPES:
                out.append(STRING_ESCAPES[e])
            elif e == "x" or e == "X":
                end = text.find(";", self.pos)
                if end < 0:
                    raise ReadError("unterminated \\x escape")
                out.append(self._hex_char(text[self.pos:end]))
                self.pos = end + 1
            elif e in " \t\n\r":
                # \<intraline whitespace>*<newline><intraline whitespace>*
                p = self.pos - 1
                while p < len(text) and text[p] in " \t":
                    p += 1
                if p < len(text) and text[p] == "\r":
                    p += 1
                if p < len(text) and text[p] == "\n":
                    p += 1
                else:
                    raise ReadError("bad line continuation in string")
                while p < len(text) and text[p] in " \t":
                    p += 1
                self.pos = p
            else:
                raise ReadError("unknown string escape \\%s" % e)

    @staticmethod
    def _hex_char(digits):
        try:
            return chr(int(digits, 16))
        except (ValueError, OverflowError):
            raise ReadError("bad hex escape", digits)

    def _token(self):
        start = self.pos
        text = self.text
        while self.pos < len(text) and text[self.pos] not in DELIMITERS:
            self.pos += 1
        return text[start:self.pos]

    def _read_atom(self):
        tok = self._token()
        if tok == ".":
            return _DOT
        num = parse_number(tok)
        if num is not None:
            return num
        if self.fold_case:
            tok = tok.casefold()
        return Symbol.intern(tok)

    def _read_hash(self):
        text = self.text
        nxt = text[self.pos + 1] if self.pos + 1 < len(text) else ""
        if nxt == "(":
            self.pos += 2
            return list(self._list_items(")"))
        if nxt == "\\":
            self.pos += 2
            return self._read_char()
        if nxt.isdigit():
            return self._read_label()
        if text.startswith("#u8(", self.pos) or text.startswith("#U8(", self.pos):
            self.pos += 4
            items = self._list_items(")")
            for b in items:
                if type(b) is not int or not 0 <= b <= 255:
                    raise ReadError("bad byte in bytevector", b)
            return bytearray(items)
        tok = self._token()
        low = tok.lower()
        if low in ("#t", "#true"):
            return True
        if low in ("#f", "#false"):
            return False
        num = parse_number(tok)
        if num is not None:
            return num
        raise ReadError("unknown # syntax", tok)

    def _list_items(self, close):
        items = []
        while True:
            obj = self._read()
            if obj is None:
                raise ReadError("end of input in vector")
            if isinstance(obj, _Close):
                if obj.ch != close:
                    raise ReadError("mismatched '%s'" % obj.ch)
                return items
            if obj is _DOT:
                raise ReadError("'.' in vector")
            items.append(obj)

    def _read_char(self):
        text = self.text
        if self.pos >= len(text):
            raise ReadError("end of input in character")
        # The first character is always part of the name, even a delimiter.
        start = self.pos
        self.pos += 1
        while self.pos < len(text) and text[self.pos] not in DELIMITERS:
            self.pos += 1
        name = text[start:self.pos]
        if len(name) == 1:
            return Char(name)
        if name[0] in "xX" and len(name) > 1:
            try:
                return Char(chr(int(name[1:], 16)))
            except (ValueError, OverflowError):
                pass
        key = name.lower() if self.fold_case else name
        if key in CHAR_NAMES:
            return Char(CHAR_NAMES[key])
        raise ReadError("unknown character name", name)

    def _read_label(self):
        text = self.text
        start = self.pos + 1
        end = start
        while end < len(text) and text[end].isdigit():
            end += 1
        label = int(text[start:end])
        marker = text[end] if end < len(text) else ""
        self.pos = end + 1
        if marker == "#":
            if label not in self.labels:
                raise ReadError("undefined datum label", label)
            return self.labels[label]
        if marker != "=":
            raise ReadError("bad datum label syntax")
        ph = _Placeholder(label)
        self.labels[label] = ph
        self._has_placeholders = True
        obj = self._read()
        if obj is None or isinstance(obj, _Close) or obj is _DOT:
            raise ReadError("datum label without a datum")
        if obj is ph:
            raise ReadError("datum label refers to itself")
        ph.value = obj
        ph.resolved = True
        self.labels[label] = obj
        return obj

    def _patch(self, root):
        """Replace placeholders (forward references to a label) in place."""
        seen = set()
        stack = [root]

        def fix(x):
            while isinstance(x, _Placeholder):
                x = x.value
            return x

        root = fix(root)
        stack = [root]
        while stack:
            x = stack.pop()
            if id(x) in seen:
                continue
            seen.add(id(x))
            if isinstance(x, Pair):
                x.car = fix(x.car)
                x.cdr = fix(x.cdr)
                stack.append(x.car)
                stack.append(x.cdr)
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    x[i] = fix(v)
                    stack.append(x[i])
        self._has_placeholders = False
        return root


def read_all(text: str):
    return Reader(text).read_all()


def read_one(text: str):
    return Reader(text).read()
