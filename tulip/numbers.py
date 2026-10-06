"""The numeric tower: parsing, printing and exactness helpers.

Exact integers are ``int``, exact rationals ``Fraction`` (normalized so a
whole number is always an ``int``), inexact reals ``float``. Complex numbers
are not supported: their syntax is rejected by the reader with an error that
says so.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

from .types import SchemeError, is_number


def normalize(x):
    """Turn a whole-number Fraction into an int."""
    if type(x) is Fraction and x.denominator == 1:
        return x.numerator
    return x


def is_exact(x):
    return type(x) is int or type(x) is Fraction


def is_integer_value(x):
    if type(x) is int:
        return True
    if type(x) is float:
        return math.isfinite(x) and x == math.floor(x)
    return False


def check_number(x, who):
    if not is_number(x):
        raise SchemeError("%s: not a number" % who, x)
    return x


def check_integer(x, who):
    if not is_integer_value(x):
        raise SchemeError("%s: not an integer" % who, x)
    return x


def to_exact(x, who="exact"):
    if type(x) is float:
        if not math.isfinite(x):
            raise SchemeError("%s: no exact representation" % who, x)
        return normalize(Fraction(x))
    check_number(x, who)
    return x


def to_inexact(x, who="inexact"):
    if type(x) is float:
        return x
    check_number(x, who)
    try:
        return float(x)
    except OverflowError:
        return math.inf if x > 0 else -math.inf


# --- parsing ------------------------------------------------------------------

_DIGITS = {2: "01", 8: "01234567", 10: "0123456789", 16: "0123456789abcdef"}


def parse_number(text: str, default_radix: int = 10):
    """Parse R7RS number syntax. Returns a number, or None if ``text`` is not
    number syntax at all. Raises SchemeError for complex-number syntax."""
    s = text.lower()
    radix = default_radix
    exactness = None
    while len(s) >= 2 and s[0] == "#":
        p = s[1]
        if p in "xbod":
            radix = {"x": 16, "b": 2, "o": 8, "d": 10}[p]
        elif p in "ei":
            if exactness is not None:
                return None
            exactness = p
        else:
            return None
        s = s[2:]
    if not s:
        return None
    value = _parse_real(s, radix)
    if value is None:
        if _looks_complex(s, radix):
            raise SchemeError("complex numbers are not supported", text)
        return None
    if exactness == "e":
        if type(value) is float:
            if not math.isfinite(value):
                raise SchemeError("no exact representation", text)
            # #e1.5 must be read exactly from the decimal text, not via float
            exact = _parse_real(s, radix, exact_decimals=True)
            return normalize(exact)
        return value
    if exactness == "i":
        return to_inexact(value)
    return value


def _parse_real(s, radix, exact_decimals=False):
    if s in ("+inf.0", "-inf.0"):
        return math.inf if s[0] == "+" else -math.inf
    if s in ("+nan.0", "-nan.0"):
        return math.nan
    sign = 1
    body = s
    if body and body[0] in "+-":
        sign = -1 if body[0] == "-" else 1
        body = body[1:]
    if not body:
        return None
    digits = _DIGITS[radix]
    if "/" in body:
        num, _, den = body.partition("/")
        if not num or not den or not all(c in digits for c in num) \
                or not all(c in digits for c in den):
            return None
        d = int(den, radix)
        if d == 0:
            raise SchemeError("division by zero in number literal", s)
        return normalize(Fraction(sign * int(num, radix), d))
    if all(c in digits for c in body):
        return sign * int(body, radix)
    if radix != 10:
        return None
    if not _DECIMAL.fullmatch(body):
        return None
    if exact_decimals:
        return normalize(sign * Fraction(body))
    return sign * float(body)


_DECIMAL = re.compile(r"(\d+\.?\d*|\.\d+)(e[+-]?\d+)?")


def _looks_complex(s, radix):
    if not s.endswith("i") and "@" not in s:
        return False
    digits = _DIGITS[radix] + ".+-/e@infa"
    return all(c in digits for c in s) and any(c in _DIGITS[radix] for c in s)


# --- printing -----------------------------------------------------------------

def number_to_string(x, radix=10):
    if type(x) is int:
        return _int_to_string(x, radix)
    if type(x) is Fraction:
        return "%s/%s" % (_int_to_string(x.numerator, radix),
                          _int_to_string(x.denominator, radix))
    if type(x) is float:
        if radix != 10:
            raise SchemeError("number->string: inexact numbers only in radix 10", x)
        if math.isnan(x):
            return "+nan.0"
        if math.isinf(x):
            return "+inf.0" if x > 0 else "-inf.0"
        r = repr(x)
        if "e" in r and "." not in r.split("e")[0]:
            mant, _, exp = r.partition("e")
            r = mant + ".0e" + exp
        return r
    raise SchemeError("number->string: not a number", x)


def _int_to_string(n, radix):
    if radix == 10:
        return str(n)
    if n == 0:
        return "0"
    neg = n < 0
    n = abs(n)
    out = []
    digits = _DIGITS[radix]
    while n:
        n, r = divmod(n, radix)
        out.append(digits[r])
    return ("-" if neg else "") + "".join(reversed(out))
