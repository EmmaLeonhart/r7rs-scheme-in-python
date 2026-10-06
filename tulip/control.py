"""First-class control: continuations, dynamic-wind, exceptions, parameters.

The machine's dynamic state is three immutable linked lists:

- ``winders``: the active dynamic-wind entries (``Winder``), innermost first;
- ``handlers``: the exception-handler stack (``HandlerNode``);
- ``params``: parameterize bindings (``ParamBinding``).

A continuation captures ``k`` and all three. Invoking it runs the ``after``
thunks of the winders being left (innermost first) and the ``before`` thunks
of those being entered (outermost first), each as an ordinary Scheme call in
the dynamic state of its dynamic-wind, then restores the captured state and
delivers the values. Everything happens through continuation frames, so the
thunks may themselves capture or invoke continuations.
"""

from __future__ import annotations

from .interp import APPLIERS, apply_procedure
from .registry import PRIMITIVES, control, prim
from .types import Procedure, SchemeError, list_to_python, values


class Winder:
    __slots__ = ("before", "after", "next", "depth", "handlers", "params")

    def __init__(self, before, after, next, handlers, params):
        self.before = before
        self.after = after
        self.next = next
        self.depth = next.depth + 1 if next is not None else 1
        self.handlers = handlers
        self.params = params


class HandlerNode:
    __slots__ = ("handler", "next")

    def __init__(self, handler, next):
        self.handler = handler
        self.next = next


class ParamBinding:
    __slots__ = ("param", "value", "next")

    def __init__(self, param, value, next):
        self.param = param
        self.value = value
        self.next = next


class Continuation(Procedure):
    __slots__ = ("k", "winders", "handlers", "params")

    def __init__(self, k, winders, handlers, params):
        self.k = k
        self.winders = winders
        self.handlers = handlers
        self.params = params

    name = "continuation"

    def __repr__(self):
        return "#<continuation>"


class Parameter(Procedure):
    __slots__ = ("value", "converter")

    def __init__(self, value, converter):
        self.value = value
        self.converter = converter

    name = "parameter"

    def __repr__(self):
        return "#<parameter>"


# --- small frames ------------------------------------------------------------------

class ReturnFrame:
    """Deliver a saved value (after running an ``after`` thunk)."""
    __slots__ = ("val", "next")

    def __init__(self, val, next):
        self.val = val
        self.next = next

    def resume(self, m):
        m.val = self.val


class RestoreHandlersFrame:
    __slots__ = ("handlers", "next")

    def __init__(self, handlers, next):
        self.handlers = handlers
        self.next = next

    def resume(self, m):
        m.handlers = self.handlers


class RestoreParamsFrame:
    __slots__ = ("params", "next")

    def __init__(self, params, next):
        self.params = params
        self.next = next

    def resume(self, m):
        m.params = self.params


# --- call/cc --------------------------------------------------------------------------

@control("call-with-current-continuation", 1)
def call_cc(m, args):
    cont = Continuation(m.k, m.winders, m.handlers, m.params)
    apply_procedure(m, args[0], [cont])


PRIMITIVES["call/cc"] = PRIMITIVES["call-with-current-continuation"]


def _apply_continuation(m, cont, args):
    val = values(*args)
    steps = _wind_steps(m.winders, cont.winders)
    if not steps:
        _deliver(m, cont, val)
        return
    WindFrame(steps, 0, cont, val, None).resume(m)


APPLIERS[Continuation] = _apply_continuation


def _deliver(m, cont, val):
    m.k = cont.k
    m.winders = cont.winders
    m.handlers = cont.handlers
    m.params = cont.params
    m.val = val
    m.node = None


def _wind_steps(cur, target):
    """The thunk calls needed to go from winders ``cur`` to ``target``:
    a list of (winder, thunk, winders-during-the-call)."""
    leave, enter = [], []
    a, b = cur, target
    while _depth(a) > _depth(b):
        leave.append(a)
        a = a.next
    while _depth(b) > _depth(a):
        enter.append(b)
        b = b.next
    while a is not b:
        leave.append(a)
        enter.append(b)
        a, b = a.next, b.next
    steps = [(w, w.after, w.next) for w in leave]
    steps += [(w, w.before, w.next) for w in reversed(enter)]
    return steps


def _depth(w):
    return 0 if w is None else w.depth


class WindFrame:
    """Run the wind steps one by one, then deliver to the continuation."""
    __slots__ = ("steps", "i", "cont", "val", "next")

    def __init__(self, steps, i, cont, val, next):
        self.steps = steps
        self.i = i
        self.cont = cont
        self.val = val
        self.next = next

    def resume(self, m):
        if self.i == len(self.steps):
            _deliver(m, self.cont, self.val)
            return
        winder, thunk, during = self.steps[self.i]
        m.winders = during
        m.handlers = winder.handlers
        m.params = winder.params
        m.k = WindFrame(self.steps, self.i + 1, self.cont, self.val, None)
        apply_procedure(m, thunk, [])


# --- dynamic-wind ------------------------------------------------------------------

@control("dynamic-wind", 3)
def dynamic_wind(m, args):
    before, thunk, after = args
    m.k = AfterBeforeFrame(before, thunk, after, m.k)
    apply_procedure(m, before, [])


class AfterBeforeFrame:
    __slots__ = ("before", "thunk", "after", "next")

    def __init__(self, before, thunk, after, next):
        self.before = before
        self.thunk = thunk
        self.after = after
        self.next = next

    def resume(self, m):
        w = Winder(self.before, self.after, m.winders, m.handlers, m.params)
        m.winders = w
        m.k = AfterThunkFrame(w, self.next)
        apply_procedure(m, self.thunk, [])


class AfterThunkFrame:
    __slots__ = ("winder", "next")

    def __init__(self, winder, next):
        self.winder = winder
        self.next = next

    def resume(self, m):
        m.winders = self.winder.next
        m.k = ReturnFrame(m.val, self.next)
        apply_procedure(m, self.winder.after, [])


# --- exceptions ---------------------------------------------------------------------

@control("with-exception-handler", 2)
def with_exception_handler(m, args):
    handler, thunk = args
    if not isinstance(handler, Procedure) and type(handler) not in APPLIERS:
        raise SchemeError("with-exception-handler: not a procedure", handler)
    m.k = RestoreHandlersFrame(m.handlers, m.k)
    m.handlers = HandlerNode(handler, m.handlers)
    apply_procedure(m, thunk, [])


@control("raise", 1)
def raise_(m, args):
    raise SchemeError(None, payload=args[0])


@control("raise-continuable", 1)
def raise_continuable(m, args):
    h = m.handlers
    if h is None:
        raise SchemeError(None, payload=args[0])
    m.k = RestoreHandlersFrame(h, m.k)
    m.handlers = h.next
    apply_procedure(m, h.handler, [args[0]])


class AfterRaiseFrame:
    """A handler returned from a non-continuable raise: that is an error."""
    __slots__ = ("payload", "next")

    def __init__(self, payload, next):
        self.payload = payload
        self.next = next

    def resume(self, m):
        raise SchemeError("exception handler returned from non-continuable raise",
                          self.payload)


def signal(m, error):
    """Deliver ``error`` (a SchemeError) to the current handler. Returns False
    when there is no handler, so the caller re-raises it to Python."""
    h = m.handlers
    if h is None:
        return False
    m.k = AfterRaiseFrame(error.payload, m.k)
    m.handlers = h.next
    apply_procedure(m, h.handler, [error.payload])
    return True


# --- parameters ----------------------------------------------------------------------

@prim("%make-parameter", 2)
def make_parameter(value, converter):
    return Parameter(value, converter)


@prim("%parameter-converter", 1)
def parameter_converter(p):
    if type(p) is not Parameter:
        raise SchemeError("parameterize: not a parameter", p)
    return p.converter


def _apply_parameter(m, p, args):
    if args:
        raise SchemeError("parameter: takes no arguments", p)
    b = m.params
    while b is not None:
        if b.param is p:
            m.val = b.value
            m.node = None
            return
        b = b.next
    m.val = p.value
    m.node = None


APPLIERS[Parameter] = _apply_parameter


@control("%with-parameters", 3)
def with_parameters(m, args):
    params, vals, thunk = args
    params = list_to_python(params)
    vals = list_to_python(vals)
    for p in params:
        if type(p) is not Parameter:
            raise SchemeError("parameterize: not a parameter", p)
    m.k = RestoreParamsFrame(m.params, m.k)
    b = m.params
    for p, v in zip(params, vals):
        b = ParamBinding(p, v, b)
    m.params = b
    apply_procedure(m, thunk, [])

