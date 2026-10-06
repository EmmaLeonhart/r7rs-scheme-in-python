"""The reference interpreter: an explicit-continuation machine.

``compile_node`` turns the core AST into executable nodes with lexical
addresses. The machine has four registers (``node``, ``env``, ``val``, ``k``)
and runs a loop: while there is a node to evaluate, step it; otherwise pop the
continuation frame ``k`` and resume it with ``val``. Nothing recurses on the
Python stack, so tail calls are proper, deep non-tail recursion only grows the
heap-allocated continuation chain, and continuations are just that chain
(captured in O(1), resumable any number of times: frames are immutable).

Runtime environments are Python lists ``[parent, slot0, slot1, ...]``.

"Simple" nodes (constants, variable references, lambda) have a ``get(env)``
method and are evaluated inline by their parent, which avoids most frames.
"""

from __future__ import annotations

from . import ast
from .types import (NIL, UNASSIGNED, UNBOUND, UNSPECIFIED, CaseLambda,
                    MultipleValues,
                    Closure, ControlPrimitive, Pair, Primitive, SchemeError,
                    make_list)


class LambdaCode:
    __slots__ = ("name", "nreq", "rest", "nslots", "body")

    def __init__(self, name, nreq, rest, nslots, body):
        self.name = name
        self.nreq = nreq
        self.rest = rest
        self.nslots = nslots      # internal-define slots after the params
        self.body = body


# --- executable nodes ---------------------------------------------------------------

class X:
    __slots__ = ()
    simple = False


class XConst(X):
    __slots__ = ("value",)
    simple = True

    def __init__(self, value):
        self.value = value

    def get(self, env):
        return self.value

    def ev(self, m):
        m.val = self.value
        m.node = None


class XLocal0(X):
    __slots__ = ("i",)
    simple = True

    def __init__(self, i):
        self.i = i

    def get(self, env):
        return env[self.i]

    def ev(self, m):
        m.val = m.env[self.i]
        m.node = None


class XLocal1(X):
    __slots__ = ("i",)
    simple = True

    def __init__(self, i):
        self.i = i

    def get(self, env):
        return env[0][self.i]

    def ev(self, m):
        m.val = m.env[0][self.i]
        m.node = None


class XLocalN(X):
    __slots__ = ("depth", "i")
    simple = True

    def __init__(self, depth, i):
        self.depth = depth
        self.i = i

    def get(self, env):
        for _ in range(self.depth):
            env = env[0]
        return env[self.i]

    def ev(self, m):
        m.val = self.get(m.env)
        m.node = None


class XLocalChecked(X):
    """A reference to an internal definition, which may not be initialized."""
    __slots__ = ("depth", "i", "name")
    simple = True

    def __init__(self, depth, i, name):
        self.depth = depth
        self.i = i
        self.name = name

    def get(self, env):
        for _ in range(self.depth):
            env = env[0]
        v = env[self.i]
        if v is UNASSIGNED:
            raise SchemeError("variable used before its definition", self.name)
        return v

    def ev(self, m):
        m.val = self.get(m.env)
        m.node = None


class XGlobal(X):
    __slots__ = ("cell",)
    simple = True

    def __init__(self, cell):
        self.cell = cell

    def get(self, env):
        v = self.cell.value
        if v is UNBOUND:
            raise SchemeError("unbound variable", self.cell.symbol)
        return v

    def ev(self, m):
        v = self.cell.value
        if v is UNBOUND:
            raise SchemeError("unbound variable", self.cell.symbol)
        m.val = v
        m.node = None


class XLambda(X):
    __slots__ = ("code",)
    simple = True

    def __init__(self, code):
        self.code = code

    def get(self, env):
        return Closure(self.code, env)

    def ev(self, m):
        m.val = Closure(self.code, m.env)
        m.node = None


class XIf(X):
    __slots__ = ("test", "then", "else_")

    def __init__(self, test, then, else_):
        self.test = test
        self.then = then
        self.else_ = else_

    def ev(self, m):
        test = self.test
        if test.simple:
            m.node = self.then if test.get(m.env) is not False else self.else_
        else:
            m.k = IfFrame(self, m.env, m.k)
            m.node = test


class IfFrame:
    __slots__ = ("x", "env", "next")

    def __init__(self, x, env, next):
        self.x = x
        self.env = env
        self.next = next

    def resume(self, m):
        m.env = self.env
        m.node = self.x.then if m.val is not False else self.x.else_


class XSeq(X):
    __slots__ = ("exprs", "last")

    def __init__(self, exprs):
        self.exprs = exprs[:-1]
        self.last = exprs[-1]

    def ev(self, m):
        self.run_from(m, 0)

    def run_from(self, m, i):
        exprs = self.exprs
        env = m.env
        n = len(exprs)
        while i < n:
            e = exprs[i]
            i += 1
            if e.simple:
                e.get(env)
            else:
                m.k = SeqFrame(self, i, env, m.k)
                m.node = e
                return
        m.node = self.last


class SeqFrame:
    __slots__ = ("x", "i", "env", "next")

    def __init__(self, x, i, env, next):
        self.x = x
        self.i = i
        self.env = env
        self.next = next

    def resume(self, m):
        m.env = self.env
        self.x.run_from(m, self.i)


class XAssign(X):
    """Base for set!/define: evaluate ``expr`` then ``store(env, value)``."""
    __slots__ = ("expr",)

    def ev(self, m):
        expr = self.expr
        if expr.simple:
            self.store(m.env, expr.get(m.env))
            m.val = UNSPECIFIED
            m.node = None
        else:
            m.k = AssignFrame(self, m.env, m.k)
            m.node = expr


class AssignFrame:
    __slots__ = ("x", "env", "next")

    def __init__(self, x, env, next):
        self.x = x
        self.env = env
        self.next = next

    def resume(self, m):
        m.env = self.env
        self.x.store(self.env, m.val)
        m.val = UNSPECIFIED


class XLocalSet(XAssign):
    __slots__ = ("depth", "i", "checked", "name")

    def __init__(self, depth, i, expr, checked, name):
        self.depth = depth
        self.i = i
        self.expr = expr
        self.checked = checked
        self.name = name

    def store(self, env, value):
        for _ in range(self.depth):
            env = env[0]
        if self.checked and env[self.i] is UNASSIGNED:
            raise SchemeError("set! of a variable before its definition", self.name)
        env[self.i] = value


class XLocalDefine(XAssign):
    __slots__ = ("i",)

    def __init__(self, i, expr):
        self.i = i
        self.expr = expr

    def store(self, env, value):
        env[self.i] = value


class XGlobalSet(XAssign):
    __slots__ = ("cell",)

    def __init__(self, cell, expr):
        self.cell = cell
        self.expr = expr

    def store(self, env, value):
        if self.cell.value is UNBOUND:
            raise SchemeError("set! of an unbound variable", self.cell.symbol)
        self.cell.value = value


class XGlobalDefine(XAssign):
    __slots__ = ("cell",)

    def __init__(self, cell, expr):
        self.cell = cell
        self.expr = expr

    def store(self, env, value):
        self.cell.value = value


class XApp(X):
    """A call. ``parts`` is the operator followed by the operands."""
    __slots__ = ("parts", "all_simple")

    def __init__(self, parts):
        self.parts = parts
        self.all_simple = all(p.simple for p in parts)

    def ev(self, m):
        if self.all_simple:
            env = m.env
            parts = self.parts
            f = parts[0].get(env)
            args = [p.get(env) for p in parts[1:]]
            apply_procedure(m, f, args)
        else:
            self.run_from(m, 0, ())

    def run_from(self, m, i, vals):
        parts = self.parts
        env = m.env
        n = len(parts)
        while i < n:
            p = parts[i]
            if p.simple:
                vals = vals + (p.get(env),)
                i += 1
            else:
                m.k = ArgFrame(self, i, vals, env, m.k)
                m.node = p
                return
        self.finish(m, vals)

    def finish(self, m, vals):
        apply_procedure(m, vals[0], list(vals[1:]))


class ArgFrame:
    __slots__ = ("x", "i", "vals", "env", "next")

    def __init__(self, x, i, vals, env, next):
        self.x = x
        self.i = i
        self.vals = vals
        self.env = env
        self.next = next

    def resume(self, m):
        m.env = self.env
        self.x.run_from(m, self.i + 1, self.vals + (m.val,))


class XLet(XApp):
    """``((lambda (params) body) args)``: bind directly, no closure."""
    __slots__ = ("code",)

    def __init__(self, code, args):
        XApp.__init__(self, [XConst(None)] + args)
        self.code = code

    def ev(self, m):
        if self.all_simple:
            env = m.env
            vals = [p.get(env) for p in self.parts[1:]]
            self._enter(m, vals)
        else:
            self.run_from(m, 1, (None,))

    def finish(self, m, vals):
        self._enter(m, list(vals[1:]))

    def _enter(self, m, args):
        code = self.code
        env = [m.env]
        if code.rest:
            env.extend(args[:code.nreq])
            env.append(make_list(args[code.nreq:]))
        else:
            env.extend(args)
        if code.nslots:
            env.extend([UNASSIGNED] * code.nslots)
        m.env = env
        m.node = code.body


# --- applying procedures ---------------------------------------------------------------

def apply_procedure(m, f, args):
    t = type(f)
    if t is Closure:
        code = f.code
        n = len(args)
        env = [f.env]
        if code.rest:
            if n < code.nreq:
                raise arity_error(f, n)
            env.extend(args[:code.nreq])
            env.append(make_list(args[code.nreq:]))
        else:
            if n != code.nreq:
                raise arity_error(f, n)
            env.extend(args)
        if code.nslots:
            env.extend([UNASSIGNED] * code.nslots)
        m.env = env
        m.node = code.body
    elif t is Primitive:
        n = len(args)
        if n < f.nreq or (n > f.nreq + f.nopt and not f.rest):
            raise arity_error(f, n)
        m.val = f.fn(*args)
        m.node = None
    elif t is ControlPrimitive:
        n = len(args)
        if n < f.nreq or (n > f.nreq + f.nopt and not f.rest):
            raise arity_error(f, n)
        f.fn(m, args)
    elif t is CaseLambda:
        n = len(args)
        for clause in f.clauses:
            code = clause.code
            if n == code.nreq or (code.rest and n >= code.nreq):
                apply_procedure(m, clause, args)
                return
        raise arity_error(f, n)
    else:
        applier = APPLIERS.get(t)
        if applier is None:
            raise SchemeError("not a procedure", f)
        applier(m, f, args)


# Other applicable types (continuations, parameters...) register here.
APPLIERS: dict = {}


def arity_error(f, n):
    return SchemeError("%s: wrong number of arguments (%d)" % (
        getattr(f, "name", None) or "procedure", n), f)


# --- the machine ------------------------------------------------------------------

class Machine:
    """Registers plus the run loop. ``k is None`` means halt."""

    def __init__(self):
        self.node = None
        self.env = None
        self.val = None
        self.k = None

    def run(self, x, env=None):
        """Evaluate executable node ``x`` to a value."""
        saved = (self.node, self.env, self.val, self.k)
        self.node = x
        self.env = env
        self.k = None
        try:
            while True:
                try:
                    self._loop()
                    return self.val
                except SchemeError as e:
                    self.signal(e)
                except RecursionError:
                    self.signal(SchemeError("Python recursion limit reached"))
                except ZeroDivisionError:
                    self.signal(SchemeError("division by zero"))
                except (TypeError, ValueError, AttributeError, IndexError,
                        KeyError, OverflowError) as e:
                    self.signal(SchemeError("%s: %s" % (type(e).__name__, e)))
        finally:
            self.node, self.env, self.val, self.k = saved

    def _loop(self):
        while True:
            node = self.node
            if node is not None:
                node.ev(self)
            else:
                k = self.k
                if k is None:
                    return
                self.k = k.next
                k.resume(self)

    def signal(self, error):
        """Deliver a raised condition. Stage 1 has no handlers: re-raise."""
        raise error

    def apply(self, f, args):
        """Call a Scheme procedure from Python and return its value."""
        return self.run(XApp([XConst(f)] + [XConst(a) for a in args]))


# --- compiling the AST -----------------------------------------------------------

def compile_node(node, frames=()):
    """Compile an AST node. ``frames`` lists ast.Frame objects, innermost
    first, for the lambdas enclosing ``node``."""
    t = type(node)
    if t is ast.Const:
        return XConst(node.value)
    if t is ast.LocalRef:
        depth, i = _address(node.var, frames)
        if node.var.defined:
            return XLocalChecked(depth, i, node.var.name)
        if depth == 0:
            return XLocal0(i)
        if depth == 1:
            return XLocal1(i)
        return XLocalN(depth, i)
    if t is ast.GlobalRef:
        return XGlobal(node.cell)
    if t is ast.If:
        return XIf(compile_node(node.test, frames), compile_node(node.then, frames),
                   compile_node(node.else_, frames))
    if t is ast.Seq:
        return XSeq([compile_node(e, frames) for e in node.exprs])
    if t is ast.Lambda:
        return XLambda(compile_lambda(node, frames))
    if t is ast.App:
        args = [compile_node(a, frames) for a in node.args]
        fn = node.fn
        if type(fn) is ast.Lambda and _arity_ok(fn, len(args)):
            return XLet(compile_lambda(fn, frames), args)
        return XApp([compile_node(fn, frames)] + args)
    if t is ast.LocalSet:
        depth, i = _address(node.var, frames)
        return XLocalSet(depth, i, compile_node(node.expr, frames),
                         node.var.defined, node.var.name)
    if t is ast.LocalDefine:
        depth, i = _address(node.var, frames)
        assert depth == 0
        return XLocalDefine(i, compile_node(node.expr, frames))
    if t is ast.GlobalSet:
        return XGlobalSet(node.cell, compile_node(node.expr, frames))
    if t is ast.GlobalDefine:
        return XGlobalDefine(node.cell, compile_node(node.expr, frames))
    raise TypeError("unknown AST node %r" % node)


def _arity_ok(lam, n):
    return n == lam.nreq or (lam.rest and n >= lam.nreq)


def compile_lambda(lam, frames):
    frames = (lam.frame,) + frames
    nparams = lam.nreq + (1 if lam.rest else 0)
    body = compile_node(lam.body, frames)
    return LambdaCode(lam.name, lam.nreq, lam.rest,
                      len(lam.frame.vars) - nparams, body)


def _address(var, frames):
    for depth, f in enumerate(frames):
        if f is var.frame:
            return depth, var.index + 1
    raise SchemeError("internal error: variable out of scope", var.name)


def spread_args(args, who="apply"):
    """``(apply f a b '(c d))`` argument list -> [a, b, c, d]."""
    out = list(args[:-1])
    p = args[-1]
    while isinstance(p, Pair):
        out.append(p.car)
        p = p.cdr
    if p is not NIL:
        raise SchemeError("%s: last argument is not a list" % who, args[-1])
    return out


def _apply(m, args):
    apply_procedure(m, args[0], spread_args(args[1:]))


APPLY = ControlPrimitive(_apply, "apply", 2, rest=True)


class ValuesFrame:
    """Continuation of the producer in call-with-values."""
    __slots__ = ("consumer", "next")

    def __init__(self, consumer, next):
        self.consumer = consumer
        self.next = next

    def resume(self, m):
        v = m.val
        args = list(v.items) if type(v) is MultipleValues else [v]
        apply_procedure(m, self.consumer, args)


def _call_with_values(m, args):
    producer, consumer = args
    m.k = ValuesFrame(consumer, m.k)
    apply_procedure(m, producer, [])


CALL_WITH_VALUES = ControlPrimitive(_call_with_values, "call-with-values", 2)
