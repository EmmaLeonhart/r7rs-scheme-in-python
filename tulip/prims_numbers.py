"""Numeric primitives (R7RS 6.2) and the (scheme inexact) procedures."""

from __future__ import annotations

import math
from fractions import Fraction

from .numbers import (check_integer, is_exact, is_integer_value,
                      normalize, number_to_string, parse_number, to_exact,
                      to_inexact)
from .registry import alias, prim
from .types import MString, SchemeError, is_number, values

NO_COMPLEX = "complex numbers are not supported"


def _real(x, who):
    if not is_number(x):
        raise SchemeError("%s: not a number" % who, x)
    return x


# --- predicates --------------------------------------------------------------

@prim("number?", 1)
def number_p(x):
    return is_number(x)


alias("complex?", "number?")
alias("real?", "number?")


@prim("rational?", 1)
def rational_p(x):
    if type(x) is float:
        return math.isfinite(x)
    return is_exact(x)


@prim("integer?", 1)
def integer_p(x):
    return is_integer_value(x)


@prim("exact?", 1)
def exact_p(x):
    return is_exact(_real(x, "exact?"))


@prim("inexact?", 1)
def inexact_p(x):
    return type(_real(x, "inexact?")) is float


@prim("exact-integer?", 1)
def exact_integer_p(x):
    return type(x) is int


@prim("finite?", 1)
def finite_p(x):
    _real(x, "finite?")
    return type(x) is not float or math.isfinite(x)


@prim("infinite?", 1)
def infinite_p(x):
    _real(x, "infinite?")
    return type(x) is float and math.isinf(x)


@prim("nan?", 1)
def nan_p(x):
    _real(x, "nan?")
    return type(x) is float and math.isnan(x)


@prim("zero?", 1)
def zero_p(x):
    return _real(x, "zero?") == 0


@prim("positive?", 1)
def positive_p(x):
    return _real(x, "positive?") > 0


@prim("negative?", 1)
def negative_p(x):
    return _real(x, "negative?") < 0


@prim("odd?", 1)
def odd_p(x):
    check_integer(x, "odd?")
    return int(x) % 2 == 1


@prim("even?", 1)
def even_p(x):
    check_integer(x, "even?")
    return int(x) % 2 == 0


# --- comparison ----------------------------------------------------------------

def _comparison(name, op):
    def compare(*args):
        for a in args:
            _real(a, name)
        for a, b in zip(args, args[1:]):
            if not op(a, b):
                return False
        return True
    prim(name, 1, rest=True)(compare)


_comparison("=", lambda a, b: a == b)
_comparison("<", lambda a, b: a < b)
_comparison(">", lambda a, b: a > b)
_comparison("<=", lambda a, b: a <= b)
_comparison(">=", lambda a, b: a >= b)


@prim("max", 1, rest=True)
def max_(*args):
    for a in args:
        _real(a, "max")
    result = args[0]
    for a in args[1:]:
        if a > result or (type(a) is float and math.isnan(a)):
            result = a
    if any(type(a) is float for a in args):
        return to_inexact(result)
    return result


@prim("min", 1, rest=True)
def min_(*args):
    for a in args:
        _real(a, "min")
    result = args[0]
    for a in args[1:]:
        if a < result or (type(a) is float and math.isnan(a)):
            result = a
    if any(type(a) is float for a in args):
        return to_inexact(result)
    return result


# --- arithmetic ------------------------------------------------------------------

@prim("+", 0, rest=True)
def add(*args):
    total = 0
    for a in args:
        total = total + _real(a, "+")
    return normalize(total)


@prim("*", 0, rest=True)
def mul(*args):
    total = 1
    for a in args:
        total = total * _real(a, "*")
    return normalize(total)


@prim("-", 1, rest=True)
def sub(first, *rest):
    _real(first, "-")
    if not rest:
        return -first
    total = first
    for a in rest:
        total = total - _real(a, "-")
    return normalize(total)


def div2(a, b):
    if type(a) is float or type(b) is float:
        if b == 0:
            a = float(a)
            if a == 0 or math.isnan(a):
                return math.nan
            return math.copysign(math.inf, a) * math.copysign(1.0, float(b))
        return a / b
    if b == 0:
        raise SchemeError("/: division by zero")
    return normalize(Fraction(a) / b)


@prim("/", 1, rest=True)
def div(first, *rest):
    _real(first, "/")
    if not rest:
        return div2(1, first)
    total = first
    for a in rest:
        total = div2(total, _real(a, "/"))
    return total


@prim("abs", 1)
def abs_(x):
    return abs(_real(x, "abs"))


alias("magnitude", "abs")


# --- integer division ---------------------------------------------------------------

def _int_args(who, n, d):
    check_integer(n, who)
    check_integer(d, who)
    if d == 0:
        raise SchemeError("%s: division by zero" % who)
    inexact = type(n) is float or type(d) is float
    return int(n), int(d), inexact


def _result(x, inexact):
    return float(x) if inexact else x


def _floor_div(who, n, d):
    n, d, inexact = _int_args(who, n, d)
    q, r = divmod(n, d)
    return _result(q, inexact), _result(r, inexact)


def _trunc_div(who, n, d):
    n, d, inexact = _int_args(who, n, d)
    q = abs(n) // abs(d)
    if (n < 0) != (d < 0):
        q = -q
    r = n - q * d
    return _result(q, inexact), _result(r, inexact)


@prim("floor/", 2)
def floor_div(n, d):
    return values(*_floor_div("floor/", n, d))


@prim("floor-quotient", 2)
def floor_quotient(n, d):
    return _floor_div("floor-quotient", n, d)[0]


@prim("floor-remainder", 2)
def floor_remainder(n, d):
    return _floor_div("floor-remainder", n, d)[1]


@prim("truncate/", 2)
def truncate_div(n, d):
    return values(*_trunc_div("truncate/", n, d))


@prim("truncate-quotient", 2)
def truncate_quotient(n, d):
    return _trunc_div("truncate-quotient", n, d)[0]


@prim("truncate-remainder", 2)
def truncate_remainder(n, d):
    return _trunc_div("truncate-remainder", n, d)[1]


alias("quotient", "truncate-quotient")
alias("remainder", "truncate-remainder")
alias("modulo", "floor-remainder")


@prim("gcd", 0, rest=True)
def gcd(*args):
    result = 0
    inexact = False
    for a in args:
        check_integer(a, "gcd")
        inexact = inexact or type(a) is float
        result = math.gcd(result, int(a))
    return _result(result, inexact)


@prim("lcm", 0, rest=True)
def lcm(*args):
    result = 1
    inexact = False
    for a in args:
        check_integer(a, "lcm")
        inexact = inexact or type(a) is float
        a = abs(int(a))
        if a == 0:
            return _result(0, inexact)
        result = result * a // math.gcd(result, a)
    return _result(result, inexact)


@prim("numerator", 1)
def numerator(x):
    _real(x, "numerator")
    if type(x) is float:
        return float(Fraction(to_exact(x, "numerator")).numerator)
    return Fraction(x).numerator


@prim("denominator", 1)
def denominator(x):
    _real(x, "denominator")
    if type(x) is float:
        return float(Fraction(to_exact(x, "denominator")).denominator)
    return Fraction(x).denominator


# --- rounding -----------------------------------------------------------------------

def _rounder(name, fn):
    def rounding(x):
        _real(x, name)
        if type(x) is float:
            if not math.isfinite(x):
                return x
            return float(fn(x))
        if type(x) is int:
            return x
        return fn(x)
    prim(name, 1)(rounding)


_rounder("floor", math.floor)
_rounder("ceiling", math.ceil)
_rounder("truncate", math.trunc)
_rounder("round", round)        # Python rounds half to even, as R7RS requires


@prim("rationalize", 2)
def rationalize(x, y):
    _real(x, "rationalize")
    _real(y, "rationalize")
    inexact = type(x) is float or type(y) is float
    if inexact:
        if math.isnan(x) or math.isnan(y):
            return math.nan
        if math.isinf(y):
            return 0.0 if math.isfinite(x) else math.nan
        if math.isinf(x):
            return x
    fx, fy = Fraction(x), abs(Fraction(y))
    r = _simplest_between(fx - fy, fx + fy)
    return float(r) if inexact else normalize(r)


def _simplest_between(lo, hi):
    if lo > 0:
        return _simplest_positive(lo, hi)
    if hi < 0:
        return -_simplest_positive(-hi, -lo)
    return Fraction(0)


def _simplest_positive(lo, hi):
    fl = math.floor(lo)
    if fl == lo:
        return Fraction(fl)
    if fl < math.floor(hi):
        return Fraction(fl + 1)
    return fl + 1 / _simplest_positive(1 / (hi - fl), 1 / (lo - fl))


# --- transcendental (scheme inexact) ------------------------------------------------

def _float_fn(name, fn, domain=None):
    def f(x):
        _real(x, name)
        if domain is not None and not domain(x):
            raise SchemeError(NO_COMPLEX, name, x)
        try:
            return fn(to_inexact(x))
        except OverflowError:
            return math.inf
        except ValueError:
            return math.nan
    prim(name, 1)(f)


_float_fn("exp", math.exp)
_float_fn("sin", math.sin)
_float_fn("cos", math.cos)
_float_fn("tan", math.tan)
_float_fn("asin", math.asin, lambda x: math.isnan(x) or -1 <= x <= 1)
_float_fn("acos", math.acos, lambda x: math.isnan(x) or -1 <= x <= 1)


@prim("atan", 1, 1)
def atan(y, x=None):
    _real(y, "atan")
    if x is None:
        return math.atan(to_inexact(y))
    _real(x, "atan")
    if is_exact(x) and is_exact(y) and x == 0 and y == 0:
        raise SchemeError("atan: both arguments are exact zero")
    return math.atan2(to_inexact(y), to_inexact(x))


def _ln(x):
    _real(x, "log")
    if x < 0:
        raise SchemeError(NO_COMPLEX, "log", x)
    if x == 0:
        return -math.inf
    if type(x) is float:
        return math.log(x)
    if type(x) is int:
        return math.log(x)
    return math.log(x.numerator) - math.log(x.denominator)


@prim("log", 1, 1)
def log(x, base=None):
    if base is None:
        return _ln(x)
    return _ln(x) / _ln(base)


@prim("square", 1)
def square(x):
    return normalize(_real(x, "square") * x)


def _exact_sqrt(n):
    """The exact square root of a non-negative int, or None."""
    r = math.isqrt(n)
    return r if r * r == n else None


@prim("sqrt", 1)
def sqrt(x):
    _real(x, "sqrt")
    if x < 0:
        raise SchemeError(NO_COMPLEX, "sqrt", x)
    if type(x) is int:
        r = _exact_sqrt(x)
        if r is not None:
            return r
    elif type(x) is Fraction:
        n, d = _exact_sqrt(x.numerator), _exact_sqrt(x.denominator)
        if n is not None and d is not None:
            return Fraction(n, d)
    try:
        return math.sqrt(x)
    except OverflowError:
        return float(math.isqrt(int(x)))


@prim("exact-integer-sqrt", 1)
def exact_integer_sqrt(n):
    if type(n) is not int or n < 0:
        raise SchemeError("exact-integer-sqrt: not a non-negative exact integer", n)
    s = math.isqrt(n)
    return values(s, n - s * s)


@prim("expt", 2)
def expt(base, power):
    _real(base, "expt")
    _real(power, "expt")
    if type(power) is int:
        if is_exact(base):
            if power >= 0:
                return normalize(base ** power)
            if base == 0:
                raise SchemeError("expt: division by zero")
            return normalize(Fraction(base) ** power)
        try:
            return float(base) ** power
        except ZeroDivisionError:
            return math.inf
        except OverflowError:
            return math.inf
    b, p = to_inexact(base), to_inexact(power)
    if b < 0 and not is_integer_value(p):
        raise SchemeError(NO_COMPLEX, "expt", base, power)
    try:
        return b ** p
    except ZeroDivisionError:
        return math.inf
    except OverflowError:
        return math.inf


# --- exactness -------------------------------------------------------------------

@prim("exact", 1)
def exact(x):
    return to_exact(x, "exact")


@prim("inexact", 1)
def inexact(x):
    return to_inexact(x, "inexact")


alias("inexact->exact", "exact")
alias("exact->inexact", "inexact")


# --- conversion --------------------------------------------------------------------

@prim("number->string", 1, 1)
def number_to_string_(x, radix=10):
    _real(x, "number->string")
    if radix not in (2, 8, 10, 16):
        raise SchemeError("number->string: bad radix", radix)
    return MString(number_to_string(x, radix))


@prim("string->number", 1, 1)
def string_to_number(s, radix=10):
    if not isinstance(s, MString):
        raise SchemeError("string->number: not a string", s)
    if radix not in (2, 8, 10, 16):
        raise SchemeError("string->number: bad radix", radix)
    try:
        n = parse_number(s.s, radix)
    except SchemeError:
        return False
    return False if n is None else n

