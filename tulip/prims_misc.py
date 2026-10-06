"""Procedures, promises, records, errors and basic output."""

from __future__ import annotations

from . import interp
from .registry import PRIMITIVES, prim
from .types import (CaseLambda, ErrorObject, MString,
                    Pair, Primitive, Procedure, Promise, Record, RecordType,
                    SchemeError, Symbol, UNSPECIFIED, list_to_python,
                    make_list, values)

PRIMITIVES["apply"] = interp.APPLY
PRIMITIVES["call-with-values"] = interp.CALL_WITH_VALUES


@prim("values", 0, rest=True)
def values_(*items):
    return values(*items)


@prim("procedure?", 1)
def procedure_p(x):
    return isinstance(x, Procedure) or type(x) in interp.APPLIERS


@prim("%case-lambda", 0, rest=True)
def make_case_lambda(*closures):
    for c in closures:
        if getattr(c, "code", None) is None:     # Closure or vm.VMClosure
            raise SchemeError("case-lambda: clause is not a lambda", c)
    return CaseLambda(list(closures))


# --- promises (R7RS 4.2.5, reference implementation) -------------------------------

@prim("%make-promise", 2)
def make_promise_raw(done, value):
    return Promise(done, value)


@prim("make-promise", 1)
def make_promise(x):
    return x if type(x) is Promise else Promise(True, x)


@prim("promise?", 1)
def promise_p(x):
    return type(x) is Promise


def _promise(p):
    if type(p) is not Promise:
        raise SchemeError("force: not a promise", p)
    return p


@prim("%promise-done?", 1)
def promise_done(p):
    return _promise(p).box[0]


@prim("%promise-value", 1)
def promise_value(p):
    return _promise(p).box[1]


@prim("%promise-update!", 2)
def promise_update(new, old):
    _promise(new)
    _promise(old)
    old.box[0] = new.box[0]
    old.box[1] = new.box[1]
    new.box = old.box
    return UNSPECIFIED


# --- records -------------------------------------------------------------------------

@prim("%make-record-type", 2)
def make_record_type(name, fields):
    return RecordType(name.name if isinstance(name, Symbol) else str(name),
                      list_to_python(fields))


@prim("%record-constructor", 2)
def record_constructor(rtype, fields):
    indexes = [rtype.fields.index(f) for f in list_to_python(fields)]
    nfields = len(rtype.fields)

    def construct(*args):
        values = [UNSPECIFIED] * nfields
        for i, v in zip(indexes, args):
            values[i] = v
        return Record(rtype, values)
    return Primitive(construct, "make-" + rtype.name, len(indexes))


@prim("%record-predicate", 1)
def record_predicate(rtype):
    return Primitive(lambda x: type(x) is Record and x.rtype is rtype,
                     rtype.name + "?", 1)


@prim("%record-accessor", 2)
def record_accessor(rtype, field):
    i = rtype.fields.index(field)
    name = "%s-%s" % (rtype.name, field.name)

    def access(r):
        if type(r) is not Record or r.rtype is not rtype:
            raise SchemeError("%s: not a %s record" % (name, rtype.name), r)
        return r.values[i]
    return Primitive(access, name, 1)


@prim("%record-modifier", 2)
def record_modifier(rtype, field):
    i = rtype.fields.index(field)
    name = "set-%s-%s!" % (rtype.name, field.name)

    def modify(r, v):
        if type(r) is not Record or r.rtype is not rtype:
            raise SchemeError("%s: not a %s record" % (name, rtype.name), r)
        r.values[i] = v
        return UNSPECIFIED
    return Primitive(modify, name, 2)


# --- errors ----------------------------------------------------------------------------

@prim("error", 1, rest=True)
def error(message, *irritants):
    raise SchemeError(None, payload=ErrorObject(message, irritants))


@prim("error-object?", 1)
def error_object_p(x):
    return type(x) is ErrorObject


@prim("error-object-message", 1)
def error_object_message(e):
    if type(e) is not ErrorObject:
        raise SchemeError("error-object-message: not an error object", e)
    m = e.message
    return m if isinstance(m, MString) else MString(str(m))


@prim("error-object-irritants", 1)
def error_object_irritants(e):
    if type(e) is not ErrorObject:
        raise SchemeError("error-object-irritants: not an error object", e)
    return make_list(e.irritants)


@prim("read-error?", 1)
def read_error_p(x):
    return type(x) is ErrorObject and x.kind == "read"


@prim("file-error?", 1)
def file_error_p(x):
    return type(x) is ErrorObject and x.kind == "file"


# --- helpers for the prelude's multi-list map/for-each -----------------------------

@prim("%cars+cdrs", 1)
def cars_cdrs(lists):
    """((a1 . r1) (a2 . r2) ...) -> ((a1 a2 ...) . (r1 r2 ...)), or #f when
    any list has run out."""
    cars, cdrs = [], []
    p = lists
    while type(p) is Pair:
        lst = p.car
        if type(lst) is not Pair:
            return False
        cars.append(lst.car)
        cdrs.append(lst.cdr)
        p = p.cdr
    return Pair(make_list(cars), make_list(cdrs))


