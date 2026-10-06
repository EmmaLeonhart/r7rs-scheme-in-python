"""Data primitives: equivalence, booleans, pairs and lists, symbols,
characters, strings, vectors and bytevectors (R7RS 6.1, 6.3-6.9).

Procedures that take a procedure argument (map, for-each, member with a
predicate, vector-map...) are written in Scheme in prelude.scm, so that
call/cc and tail calls work through them.
"""

from __future__ import annotations

import math
import unicodedata

from .registry import alias, prim
from .types import (NIL, Char, MString, Pair, SchemeError, Symbol,
                    UNSPECIFIED, is_number, list_to_python, make_list)


# --- equivalence ----------------------------------------------------------------

def eqv(a, b):
    if a is b:
        return True
    ta = type(a)
    if ta is not type(b):
        return False
    if ta is int:
        return a == b
    if ta is float:
        # 0.0 and -0.0 are = but not eqv? (they give different results,
        # e.g. under /); two NaNs are treated as eqv?
        if a == b:
            return a != 0.0 or math.copysign(1.0, a) == math.copysign(1.0, b)
        return a != a and b != b
    if is_number(a):
        return a == b
    if ta is Char:
        return a.ch == b.ch
    return False


def eq(a, b):
    if a is b:
        return True
    ta = type(a)
    # small exact integers and characters behave as immediates
    if ta is int and type(b) is int:
        return a == b
    if ta is Char and type(b) is Char:
        return a.ch == b.ch
    return False


def equal(a, b):
    """Structural equality that terminates on circular structure: each pair
    of nodes is compared at most once."""
    seen = set()
    stack = [(a, b)]
    while stack:
        x, y = stack.pop()
        if eqv(x, y):
            continue
        tx = type(x)
        if tx is not type(y):
            return False
        if tx is Pair:
            key = (id(x), id(y))
            if key in seen:
                continue
            seen.add(key)
            stack.append((x.cdr, y.cdr))
            stack.append((x.car, y.car))
        elif tx is MString:
            if x.s != y.s:
                return False
        elif tx is list:
            if len(x) != len(y):
                return False
            key = (id(x), id(y))
            if key in seen:
                continue
            seen.add(key)
            stack.extend(zip(reversed(x), reversed(y)))
        elif tx is bytearray:
            if x != y:
                return False
        else:
            return False
    return True


prim("eqv?", 2)(eqv)
prim("eq?", 2)(eq)
prim("equal?", 2)(equal)


# --- booleans ---------------------------------------------------------------------

@prim("not", 1)
def not_(x):
    return x is False


@prim("boolean?", 1)
def boolean_p(x):
    return x is True or x is False


@prim("boolean=?", 2, rest=True)
def boolean_eq(*args):
    for a in args:
        if not boolean_p(a):
            raise SchemeError("boolean=?: not a boolean", a)
    return all(a is args[0] for a in args)


# --- pairs and lists ----------------------------------------------------------------

def _pair(x, who):
    if type(x) is not Pair:
        raise SchemeError("%s: not a pair" % who, x)
    return x


@prim("pair?", 1)
def pair_p(x):
    return type(x) is Pair


@prim("cons", 2)
def cons(a, b):
    return Pair(a, b)


@prim("car", 1)
def car(x):
    return _pair(x, "car").car


@prim("cdr", 1)
def cdr(x):
    return _pair(x, "cdr").cdr


@prim("set-car!", 2)
def set_car(x, v):
    _pair(x, "set-car!").car = v
    return UNSPECIFIED


@prim("set-cdr!", 2)
def set_cdr(x, v):
    _pair(x, "set-cdr!").cdr = v
    return UNSPECIFIED


def _cxr(path):
    name = "c%sr" % path

    def cxr(x):
        orig = x
        for step in reversed(path):
            if type(x) is not Pair:
                raise SchemeError("%s: bad argument" % name, orig)
            x = x.car if step == "a" else x.cdr
        return x
    prim(name, 1)(cxr)


for _p in ["aa", "ad", "da", "dd", "aaa", "aad", "ada", "add", "daa", "dad",
           "dda", "ddd", "aaaa", "aaad", "aada", "aadd", "adaa", "adad", "adda",
           "addd", "daaa", "daad", "dada", "dadd", "ddaa", "ddad", "ddda",
           "dddd"]:
    _cxr(_p)


@prim("null?", 1)
def null_p(x):
    return x is NIL


@prim("list?", 1)
def list_p(x):
    slow = x
    while True:
        if x is NIL:
            return True
        if type(x) is not Pair:
            return False
        x = x.cdr
        if x is NIL:
            return True
        if type(x) is not Pair:
            return False
        x = x.cdr
        slow = slow.cdr
        if x is slow:
            return False


@prim("make-list", 1, 1)
def make_list_(k, fill=UNSPECIFIED):
    _index(k, "make-list")
    result = NIL
    for _ in range(k):
        result = Pair(fill, result)
    return result


@prim("list", 0, rest=True)
def list_(*items):
    return make_list(items)


@prim("length", 1)
def length(x):
    if not list_p(x):
        raise SchemeError("length: not a proper list", x)
    n = 0
    while x is not NIL:
        n += 1
        x = x.cdr
    return n


@prim("append", 0, rest=True)
def append(*lists):
    if not lists:
        return NIL
    result = lists[-1]
    for lst in reversed(lists[:-1]):
        result = make_list(list_to_python(lst, "append"), result)
    return result


@prim("reverse", 1)
def reverse(lst):
    result = NIL
    for item in list_to_python(lst, "reverse"):
        result = Pair(item, result)
    return result


def _index(k, who):
    if type(k) is not int or k < 0:
        raise SchemeError("%s: not a valid index" % who, k)
    return k


@prim("list-tail", 2)
def list_tail(lst, k):
    _index(k, "list-tail")
    for _ in range(k):
        lst = _pair(lst, "list-tail").cdr
    return lst


@prim("list-ref", 2)
def list_ref(lst, k):
    return _pair(list_tail(lst, k), "list-ref").car


@prim("list-set!", 3)
def list_set(lst, k, v):
    _pair(list_tail(lst, k), "list-set!").car = v
    return UNSPECIFIED


@prim("list-copy", 1)
def list_copy(obj):
    if type(obj) is not Pair:
        return obj
    items = []
    p = obj
    while type(p) is Pair:
        items.append(p.car)
        p = p.cdr
    return make_list(items, p)


def _mem(name, test):
    def mem(x, lst):
        p = lst
        while type(p) is Pair:
            if test(x, p.car):
                return p
            p = p.cdr
        if p is not NIL:
            raise SchemeError("%s: not a proper list" % name, lst)
        return False
    prim(name, 2)(mem)
    return mem


memq = _mem("memq", eq)
memv = _mem("memv", eqv)
_mem("%member", equal)


def _ass(name, test):
    def ass(x, alist):
        p = alist
        while type(p) is Pair:
            entry = p.car
            if type(entry) is not Pair:
                raise SchemeError("%s: not an association list" % name, alist)
            if test(x, entry.car):
                return entry
            p = p.cdr
        return False
    prim(name, 2)(ass)


_ass("assq", eq)
_ass("assv", eqv)
_ass("%assoc", equal)


# --- symbols -------------------------------------------------------------------------

@prim("symbol?", 1)
def symbol_p(x):
    return type(x) is Symbol


@prim("symbol=?", 2, rest=True)
def symbol_eq(*args):
    for a in args:
        if type(a) is not Symbol:
            raise SchemeError("symbol=?: not a symbol", a)
    return all(a is args[0] for a in args)


@prim("symbol->string", 1)
def symbol_to_string(s):
    if type(s) is not Symbol:
        raise SchemeError("symbol->string: not a symbol", s)
    return MString(s.name, immutable=True)


@prim("string->symbol", 1)
def string_to_symbol(s):
    return Symbol.intern(_str(s, "string->symbol").s)


# --- characters -------------------------------------------------------------------------

def _char(c, who):
    if type(c) is not Char:
        raise SchemeError("%s: not a character" % who, c)
    return c.ch


@prim("char?", 1)
def char_p(x):
    return type(x) is Char


def _char_compare(name, op, fold=False):
    def compare(*args):
        chars = [_char(a, name) for a in args]
        if fold:
            chars = [_fold_char(c) for c in chars]
        return all(op(a, b) for a, b in zip(chars, chars[1:]))
    prim(name, 1, rest=True)(compare)


def _fold_char(c):
    f = c.casefold()
    return f if len(f) == 1 else c


for _name, _op in [("=?", lambda a, b: a == b), ("<?", lambda a, b: a < b),
                   (">?", lambda a, b: a > b), ("<=?", lambda a, b: a <= b),
                   (">=?", lambda a, b: a >= b)]:
    _char_compare("char" + _name, _op)
    _char_compare("char-ci" + _name, _op, fold=True)


@prim("char-alphabetic?", 1)
def char_alphabetic(c):
    return _char(c, "char-alphabetic?").isalpha()


@prim("char-numeric?", 1)
def char_numeric(c):
    return unicodedata.category(_char(c, "char-numeric?")) == "Nd"


@prim("char-whitespace?", 1)
def char_whitespace(c):
    return _char(c, "char-whitespace?").isspace()


@prim("char-upper-case?", 1)
def char_upper_case(c):
    return _char(c, "char-upper-case?").isupper()


@prim("char-lower-case?", 1)
def char_lower_case(c):
    return _char(c, "char-lower-case?").islower()


@prim("digit-value", 1)
def digit_value(c):
    ch = _char(c, "digit-value")
    if unicodedata.category(ch) != "Nd":
        return False
    return unicodedata.decimal(ch)


@prim("char->integer", 1)
def char_to_integer(c):
    return ord(_char(c, "char->integer"))


@prim("integer->char", 1)
def integer_to_char(n):
    if type(n) is not int or not (0 <= n <= 0x10FFFF) or 0xD800 <= n <= 0xDFFF:
        raise SchemeError("integer->char: not a Unicode scalar value", n)
    return Char(chr(n))


def _single(f, c):
    return f if len(f) == 1 else c


@prim("char-upcase", 1)
def char_upcase(c):
    ch = _char(c, "char-upcase")
    return Char(_single(ch.upper(), ch))


@prim("char-downcase", 1)
def char_downcase(c):
    ch = _char(c, "char-downcase")
    return Char(_single(ch.lower(), ch))


@prim("char-foldcase", 1)
def char_foldcase(c):
    ch = _char(c, "char-foldcase")
    return Char(_fold_char(ch))


# --- strings --------------------------------------------------------------------------

def _str(s, who):
    if type(s) is not MString:
        raise SchemeError("%s: not a string" % who, s)
    return s


def _mutable(s, who):
    _str(s, who)
    if s.immutable:
        raise SchemeError("%s: string is immutable (a literal)" % who, s)
    return s


def _range(n, start, end, who):
    """Validate optional start/end against length n; return (start, end)."""
    if start is None:
        start = 0
    if end is None:
        end = n
    if type(start) is not int or type(end) is not int \
            or not (0 <= start <= end <= n):
        raise SchemeError("%s: bad range" % who, start, end)
    return start, end


@prim("string?", 1)
def string_p(x):
    return type(x) is MString


@prim("make-string", 1, 1)
def make_string(k, c=None):
    _index(k, "make-string")
    ch = " " if c is None else _char(c, "make-string")
    return MString(ch * k)


@prim("string", 0, rest=True)
def string(*chars):
    return MString("".join(_char(c, "string") for c in chars))


@prim("string-length", 1)
def string_length(s):
    return len(_str(s, "string-length").s)


@prim("string-ref", 2)
def string_ref(s, k):
    _str(s, "string-ref")
    if type(k) is not int or not 0 <= k < len(s.s):
        raise SchemeError("string-ref: index out of range", k)
    return Char(s.s[k])


@prim("string-set!", 3)
def string_set(s, k, c):
    _mutable(s, "string-set!")
    ch = _char(c, "string-set!")
    if type(k) is not int or not 0 <= k < len(s.s):
        raise SchemeError("string-set!: index out of range", k)
    s.s = s.s[:k] + ch + s.s[k + 1:]
    return UNSPECIFIED


def _string_compare(name, op, fold=False):
    def compare(*args):
        strs = [_str(a, name).s for a in args]
        if fold:
            strs = [s.casefold() for s in strs]
        return all(op(a, b) for a, b in zip(strs, strs[1:]))
    prim(name, 1, rest=True)(compare)


for _name, _op in [("=?", lambda a, b: a == b), ("<?", lambda a, b: a < b),
                   (">?", lambda a, b: a > b), ("<=?", lambda a, b: a <= b),
                   (">=?", lambda a, b: a >= b)]:
    _string_compare("string" + _name, _op)
    _string_compare("string-ci" + _name, _op, fold=True)


@prim("string-upcase", 1)
def string_upcase(s):
    return MString(_str(s, "string-upcase").s.upper())


@prim("string-downcase", 1)
def string_downcase(s):
    return MString(_str(s, "string-downcase").s.lower())


@prim("string-foldcase", 1)
def string_foldcase(s):
    return MString(_str(s, "string-foldcase").s.casefold())


@prim("substring", 3)
def substring(s, start, end):
    _str(s, "substring")
    start, end = _range(len(s.s), start, end, "substring")
    return MString(s.s[start:end])


@prim("string-append", 0, rest=True)
def string_append(*strs):
    return MString("".join(_str(s, "string-append").s for s in strs))


@prim("string->list", 1, 2)
def string_to_list(s, start=None, end=None):
    _str(s, "string->list")
    start, end = _range(len(s.s), start, end, "string->list")
    return make_list([Char(c) for c in s.s[start:end]])


@prim("list->string", 1)
def list_to_string(lst):
    return MString("".join(_char(c, "list->string")
                           for c in list_to_python(lst, "list->string")))


@prim("string-copy", 1, 2)
def string_copy(s, start=None, end=None):
    _str(s, "string-copy")
    start, end = _range(len(s.s), start, end, "string-copy")
    return MString(s.s[start:end])


@prim("string-copy!", 3, 2)
def string_copy_bang(to, at, frm, start=None, end=None):
    _mutable(to, "string-copy!")
    _str(frm, "string-copy!")
    start, end = _range(len(frm.s), start, end, "string-copy!")
    piece = frm.s[start:end]
    if type(at) is not int or not 0 <= at <= len(to.s) - len(piece):
        raise SchemeError("string-copy!: bad destination index", at)
    to.s = to.s[:at] + piece + to.s[at + len(piece):]
    return UNSPECIFIED


@prim("string-fill!", 2, 2)
def string_fill(s, c, start=None, end=None):
    _mutable(s, "string-fill!")
    ch = _char(c, "string-fill!")
    start, end = _range(len(s.s), start, end, "string-fill!")
    s.s = s.s[:start] + ch * (end - start) + s.s[end:]
    return UNSPECIFIED


# --- vectors ------------------------------------------------------------------------------

def _vec(v, who):
    if type(v) is not list:
        raise SchemeError("%s: not a vector" % who, v)
    return v


@prim("vector?", 1)
def vector_p(x):
    return type(x) is list


@prim("make-vector", 1, 1)
def make_vector(k, fill=UNSPECIFIED):
    _index(k, "make-vector")
    return [fill] * k


@prim("vector", 0, rest=True)
def vector(*items):
    return list(items)


@prim("vector-length", 1)
def vector_length(v):
    return len(_vec(v, "vector-length"))


@prim("vector-ref", 2)
def vector_ref(v, k):
    _vec(v, "vector-ref")
    if type(k) is not int or not 0 <= k < len(v):
        raise SchemeError("vector-ref: index out of range", k)
    return v[k]


@prim("vector-set!", 3)
def vector_set(v, k, x):
    _vec(v, "vector-set!")
    if type(k) is not int or not 0 <= k < len(v):
        raise SchemeError("vector-set!: index out of range", k)
    v[k] = x
    return UNSPECIFIED


@prim("vector->list", 1, 2)
def vector_to_list(v, start=None, end=None):
    _vec(v, "vector->list")
    start, end = _range(len(v), start, end, "vector->list")
    return make_list(v[start:end])


@prim("list->vector", 1)
def list_to_vector(lst):
    return list_to_python(lst, "list->vector")


@prim("vector->string", 1, 2)
def vector_to_string(v, start=None, end=None):
    _vec(v, "vector->string")
    start, end = _range(len(v), start, end, "vector->string")
    return MString("".join(_char(c, "vector->string") for c in v[start:end]))


@prim("string->vector", 1, 2)
def string_to_vector(s, start=None, end=None):
    _str(s, "string->vector")
    start, end = _range(len(s.s), start, end, "string->vector")
    return [Char(c) for c in s.s[start:end]]


@prim("vector-copy", 1, 2)
def vector_copy(v, start=None, end=None):
    _vec(v, "vector-copy")
    start, end = _range(len(v), start, end, "vector-copy")
    return v[start:end]


@prim("vector-copy!", 3, 2)
def vector_copy_bang(to, at, frm, start=None, end=None):
    _vec(to, "vector-copy!")
    _vec(frm, "vector-copy!")
    start, end = _range(len(frm), start, end, "vector-copy!")
    if type(at) is not int or not 0 <= at <= len(to) - (end - start):
        raise SchemeError("vector-copy!: bad destination index", at)
    to[at:at + end - start] = frm[start:end]
    return UNSPECIFIED


@prim("vector-append", 0, rest=True)
def vector_append(*vs):
    out = []
    for v in vs:
        out.extend(_vec(v, "vector-append"))
    return out


@prim("vector-fill!", 2, 2)
def vector_fill(v, x, start=None, end=None):
    _vec(v, "vector-fill!")
    start, end = _range(len(v), start, end, "vector-fill!")
    for i in range(start, end):
        v[i] = x
    return UNSPECIFIED


# --- bytevectors ------------------------------------------------------------------------

def _bv(b, who):
    if type(b) is not bytearray:
        raise SchemeError("%s: not a bytevector" % who, b)
    return b


def _byte(x, who):
    if type(x) is not int or not 0 <= x <= 255:
        raise SchemeError("%s: not a byte" % who, x)
    return x


@prim("bytevector?", 1)
def bytevector_p(x):
    return type(x) is bytearray


@prim("make-bytevector", 1, 1)
def make_bytevector(k, fill=0):
    _index(k, "make-bytevector")
    return bytearray([_byte(fill, "make-bytevector")]) * k


@prim("bytevector", 0, rest=True)
def bytevector(*bytes_):
    return bytearray(_byte(b, "bytevector") for b in bytes_)


@prim("bytevector-length", 1)
def bytevector_length(b):
    return len(_bv(b, "bytevector-length"))


@prim("bytevector-u8-ref", 2)
def bytevector_u8_ref(b, k):
    _bv(b, "bytevector-u8-ref")
    if type(k) is not int or not 0 <= k < len(b):
        raise SchemeError("bytevector-u8-ref: index out of range", k)
    return b[k]


@prim("bytevector-u8-set!", 3)
def bytevector_u8_set(b, k, x):
    _bv(b, "bytevector-u8-set!")
    if type(k) is not int or not 0 <= k < len(b):
        raise SchemeError("bytevector-u8-set!: index out of range", k)
    b[k] = _byte(x, "bytevector-u8-set!")
    return UNSPECIFIED


@prim("bytevector-copy", 1, 2)
def bytevector_copy(b, start=None, end=None):
    _bv(b, "bytevector-copy")
    start, end = _range(len(b), start, end, "bytevector-copy")
    return b[start:end]


@prim("bytevector-copy!", 3, 2)
def bytevector_copy_bang(to, at, frm, start=None, end=None):
    _bv(to, "bytevector-copy!")
    _bv(frm, "bytevector-copy!")
    start, end = _range(len(frm), start, end, "bytevector-copy!")
    if type(at) is not int or not 0 <= at <= len(to) - (end - start):
        raise SchemeError("bytevector-copy!: bad destination index", at)
    to[at:at + end - start] = frm[start:end]
    return UNSPECIFIED


@prim("bytevector-append", 0, rest=True)
def bytevector_append(*bs):
    out = bytearray()
    for b in bs:
        out += _bv(b, "bytevector-append")
    return out


@prim("utf8->string", 1, 2)
def utf8_to_string(b, start=None, end=None):
    _bv(b, "utf8->string")
    start, end = _range(len(b), start, end, "utf8->string")
    try:
        return MString(bytes(b[start:end]).decode("utf-8"))
    except UnicodeDecodeError:
        raise SchemeError("utf8->string: invalid UTF-8", b)


@prim("string->utf8", 1, 2)
def string_to_utf8(s, start=None, end=None):
    _str(s, "string->utf8")
    start, end = _range(len(s.s), start, end, "string->utf8")
    return bytearray(s.s[start:end].encode("utf-8", "surrogatepass"))

