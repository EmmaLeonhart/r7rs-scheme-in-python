"""The bytecode compiler and VM.

The compiler takes the core AST (ast.py, the same one the interpreter uses)
to ``VMCode``: parallel lists of opcodes and operands for a stack machine.
Runtime environments are the interpreter's: lists ``[parent, slot0, ...]``
with the same lexical addresses.

``run`` executes VM code in one Python loop, keeping ``code``, ``pc``,
``env`` and the operand ``stack`` in locals. Calls from VM code to VM
closures, and their returns, stay inside the loop. A non-tail call pushes a
``VMFrame`` onto the machine's continuation ``m.k``; a VMFrame is an ordinary
machine continuation frame (``resume(m)``, ``next``), so everything in
control.py (call/cc, dynamic-wind, handlers, parameters, values) works with
VM code unchanged, and VM and interpreter procedures can call each other:
calling anything that is not a VM closure or a plain primitive leaves the
loop through ``apply_procedure`` and comes back via ``VMFrame.resume``.

A frame saves the caller's pending operand stack as a tuple, so a frame
reached twice through a re-entered continuation starts from the same state.

Calls to hot built-ins (``+``, ``car``, ``<``...) compile to specialized
opcodes. At run time they check that the global still holds the built-in
(and, for arithmetic, that the operands are fixnums) and otherwise fall back
to an ordinary call, which is a tail call when the original call was one.
"""

from __future__ import annotations

from . import ast
from .interp import APPLIERS, apply_procedure, arity_error
from .registry import PRIMITIVES
from .types import (NIL, UNASSIGNED, UNBOUND, UNSPECIFIED, Pair, Primitive,
                    Procedure, SchemeError, make_list)

# --- opcodes ---------------------------------------------------------------------------

(LOCAL0, CONST, GLOBAL, LOCAL1, JUMPF, RETURN, CALL, TAILCALL,
 ADD, SUB, LT, GT, LE, GE, NUMEQ, CONS, EQ,          # two operands
 CAR, CDR, NULLP, PAIRP, NOT, ZEROP,                  # one operand
 PRIM,
 LOCAL, LOCALCHK, SETLOCAL, SETLOCALCHK, DEFLOCAL, SETGLOBAL, DEFGLOBAL,
 JUMP, CLOSURE, POP, ENTER, LEAVE) = range(36)

OPNAMES = """LOCAL0 CONST GLOBAL LOCAL1 JUMPF RETURN CALL TAILCALL ADD SUB LT GT
LE GE NUMEQ CONS EQ CAR CDR NULLP PAIRP NOT ZEROP PRIM LOCAL LOCALCHK SETLOCAL
SETLOCALCHK DEFLOCAL SETGLOBAL DEFGLOBAL JUMP CLOSURE POP ENTER LEAVE""".split()

_FAST2 = {"+": ADD, "-": SUB, "<": LT, ">": GT, "<=": LE, ">=": GE, "=": NUMEQ,
          "cons": CONS, "eq?": EQ}
_FAST1 = {"car": CAR, "cdr": CDR, "null?": NULLP, "pair?": PAIRP, "not": NOT,
          "zero?": ZEROP}


def _fast_tables():
    # import for registration side effects, then map primitive objects
    from . import prims_data, prims_numbers  # noqa: F401
    return ({PRIMITIVES[n]: op for n, op in _FAST2.items()},
            {PRIMITIVES[n]: op for n, op in _FAST1.items()})


FAST2, FAST1 = _fast_tables()


# --- runtime objects ---------------------------------------------------------------------

class VMCode:
    __slots__ = ("name", "nreq", "rest", "nslots", "ops", "args")

    def __init__(self, name, nreq, rest, nslots):
        self.name = name
        self.nreq = nreq
        self.rest = rest
        self.nslots = nslots
        self.ops = []
        self.args = []

    def disassemble(self):
        lines = []
        for i, (op, a) in enumerate(zip(self.ops, self.args)):
            if isinstance(a, VMCode):
                a = "<code %s>" % (a.name.name if a.name is not None else "lambda")
            lines.append("%4d %-12s %s" % (i, OPNAMES[op], "" if a is None else a))
        return "\n".join(lines)


class VMClosure(Procedure):
    __slots__ = ("code", "env")

    def __init__(self, code, env):
        self.code = code
        self.env = env

    @property
    def name(self):
        return self.code.name

    def __repr__(self):
        name = self.code.name
        return "#<procedure %s>" % (name.name if name is not None else "anonymous")


class VMFrame:
    """A suspended VM activation, waiting for the value of a call."""
    __slots__ = ("code", "pc", "env", "stack", "next")

    def __init__(self, code, pc, env, stack, next):
        self.code = code
        self.pc = pc
        self.env = env
        self.stack = stack      # tuple
        self.next = next

    def resume(self, m):
        stack = list(self.stack)
        stack.append(m.val)
        run(m, self.code, self.pc, self.env, stack)


class VMStart:
    """A machine node that starts VM code (a top-level form or a VM closure
    entered from outside the VM)."""
    __slots__ = ("code", "env")
    simple = False

    def __init__(self, code, env):
        self.code = code
        self.env = env

    def ev(self, m):
        run(m, self.code, 0, self.env, [])


def _enter_closure(f, args):
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
    return env


def _apply_vm_closure(m, f, args):
    m.node = VMStart(f.code, _enter_closure(f, args))


APPLIERS[VMClosure] = _apply_vm_closure


# --- the VM loop ----------------------------------------------------------------------------

def run(m, code, pc, env, stack):
    ops = code.ops
    oargs = code.args
    while True:
        op = ops[pc]
        a = oargs[pc]
        pc += 1
        if op == LOCAL0:
            stack.append(env[a])
            continue
        if op == CONST:
            stack.append(a)
            continue
        if op == GLOBAL:
            v = a.value
            if v is UNBOUND:
                raise SchemeError("unbound variable", a.symbol)
            stack.append(v)
            continue
        if op == LOCAL1:
            stack.append(env[0][a])
            continue
        if op == JUMPF:
            if stack.pop() is False:
                pc = a
            continue
        if op == RETURN:
            v = stack[-1]
            k = m.k
            if type(k) is VMFrame:
                m.k = k.next
                code = k.code
                ops = code.ops
                oargs = code.args
                pc = k.pc
                env = k.env
                stack = list(k.stack)
                stack.append(v)
                continue
            m.val = v
            m.node = None
            return
        if op == CALL or op == TAILCALL:
            n = a
            f = stack[-n - 1]
            args = stack[-n:] if n else []
            del stack[-n - 1:]
            tail = op == TAILCALL
        elif op <= ZEROP:
            # specialized primitive calls: operand is (cell, primitive, tail)
            if op <= EQ:
                y = stack.pop()
                x = stack[-1]
                if a[0].value is a[1]:
                    if type(x) is int and type(y) is int:
                        if op == ADD:
                            stack[-1] = x + y
                        elif op == SUB:
                            stack[-1] = x - y
                        elif op == LT:
                            stack[-1] = x < y
                        elif op == GT:
                            stack[-1] = x > y
                        elif op == LE:
                            stack[-1] = x <= y
                        elif op == GE:
                            stack[-1] = x >= y
                        elif op == NUMEQ:
                            stack[-1] = x == y
                        elif op == CONS:
                            stack[-1] = Pair(x, y)
                        else:
                            stack[-1] = x == y
                        continue
                    if op == CONS:
                        stack[-1] = Pair(x, y)
                        continue
                    if op == EQ and x is y:
                        stack[-1] = True
                        continue
                    stack[-1] = a[1].fn(x, y)
                    continue
                stack.pop()
                args = [x, y]
            else:
                x = stack[-1]
                if a[0].value is a[1]:
                    if op == CAR:
                        if type(x) is Pair:
                            stack[-1] = x.car
                            continue
                    elif op == CDR:
                        if type(x) is Pair:
                            stack[-1] = x.cdr
                            continue
                    elif op == NULLP:
                        stack[-1] = x is NIL
                        continue
                    elif op == PAIRP:
                        stack[-1] = type(x) is Pair
                        continue
                    elif op == NOT:
                        stack[-1] = x is False
                        continue
                    elif type(x) is int:          # ZEROP
                        stack[-1] = x == 0
                        continue
                    stack[-1] = a[1].fn(x)
                    continue
                stack.pop()
                args = [x]
            f = a[0].value
            tail = a[2]
        elif op == PRIM:
            cell, p, n, tail = a
            args = stack[-n:] if n else []
            if n:
                del stack[-n:]
            if cell.value is p:
                stack.append(p.fn(*args))
                continue
            f = cell.value
        else:
            if op == LOCAL:
                e = env
                for _ in range(a[0]):
                    e = e[0]
                stack.append(e[a[1]])
            elif op == LOCALCHK:
                e = env
                for _ in range(a[0]):
                    e = e[0]
                v = e[a[1]]
                if v is UNASSIGNED:
                    raise SchemeError("variable used before its definition", a[2])
                stack.append(v)
            elif op == CLOSURE:
                stack.append(VMClosure(a, env))
            elif op == POP:
                stack.pop()
            elif op == JUMP:
                pc = a
            elif op == ENTER:
                n, nslots = a
                new = [env]
                if n:
                    new.extend(stack[-n:])
                    del stack[-n:]
                if nslots:
                    new.extend([UNASSIGNED] * nslots)
                env = new
            elif op == LEAVE:
                env = env[0]
            elif op == SETLOCAL or op == SETLOCALCHK:
                e = env
                for _ in range(a[0]):
                    e = e[0]
                if op == SETLOCALCHK and e[a[1]] is UNASSIGNED:
                    raise SchemeError("set! of a variable before its definition", a[2])
                e[a[1]] = stack[-1]
                stack[-1] = UNSPECIFIED
            elif op == DEFLOCAL:
                env[a] = stack[-1]
                stack[-1] = UNSPECIFIED
            elif op == SETGLOBAL:
                if a.value is UNBOUND:
                    raise SchemeError("set! of an unbound variable", a.symbol)
                a.value = stack[-1]
                stack[-1] = UNSPECIFIED
            elif op == DEFGLOBAL:
                a.value = stack[-1]
                stack[-1] = UNSPECIFIED
            else:
                raise SchemeError("internal error: bad opcode", op)
            continue

        # --- a call: f applied to args, as a tail call if ``tail`` ---------------------
        tf = type(f)
        if tf is VMClosure:
            c = f.code
            n = len(args)
            new = [f.env]
            if c.rest:
                if n < c.nreq:
                    raise arity_error(f, n)
                new.extend(args[:c.nreq])
                new.append(make_list(args[c.nreq:]))
            else:
                if n != c.nreq:
                    raise arity_error(f, n)
                new.extend(args)
            if c.nslots:
                new.extend([UNASSIGNED] * c.nslots)
            if not tail:
                m.k = VMFrame(code, pc, env, tuple(stack), m.k)
            code = c
            ops = c.ops
            oargs = c.args
            pc = 0
            env = new
            stack = []
            continue
        if tf is Primitive:
            n = len(args)
            if n < f.nreq or (n > f.nreq + f.nopt and not f.rest):
                raise arity_error(f, n)
            v = f.fn(*args)
            if not tail:
                stack.append(v)
                continue
            k = m.k
            if type(k) is VMFrame:
                m.k = k.next
                code = k.code
                ops = code.ops
                oargs = code.args
                pc = k.pc
                env = k.env
                stack = list(k.stack)
                stack.append(v)
                continue
            m.val = v
            m.node = None
            return
        # anything else goes through the machine
        if not tail:
            m.k = VMFrame(code, pc, env, tuple(stack), m.k)
        apply_procedure(m, f, args)
        return


# --- the compiler -------------------------------------------------------------------------------

def compile_toplevel(node):
    code = VMCode(None, 0, False, 0)
    _Compiler(code).comp(node, (), True)
    return code


def compile_lambda(lam, frames):
    nparams = lam.nreq + (1 if lam.rest else 0)
    code = VMCode(lam.name, lam.nreq, lam.rest, len(lam.frame.vars) - nparams)
    _Compiler(code).comp(lam.body, (lam.frame,) + frames, True)
    return code


def _address(var, frames):
    for depth, f in enumerate(frames):
        if f is var.frame:
            return depth, var.index + 1
    raise SchemeError("internal error: variable out of scope", var.name)


class _Compiler:
    def __init__(self, code):
        self.code = code

    def emit(self, op, arg=None):
        self.code.ops.append(op)
        self.code.args.append(arg)
        return len(self.code.ops) - 1

    def here(self):
        return len(self.code.ops)

    def patch(self, i, target):
        self.code.args[i] = target

    def ret(self, tail):
        if tail:
            self.emit(RETURN)

    def comp(self, node, frames, tail):
        t = type(node)
        if t is ast.Const:
            self.emit(CONST, node.value)
            self.ret(tail)
        elif t is ast.LocalRef:
            var = node.var
            d, i = _address(var, frames)
            if var.defined:
                self.emit(LOCALCHK, (d, i, var.name))
            elif d == 0:
                self.emit(LOCAL0, i)
            elif d == 1:
                self.emit(LOCAL1, i)
            else:
                self.emit(LOCAL, (d, i))
            self.ret(tail)
        elif t is ast.GlobalRef:
            self.emit(GLOBAL, node.cell)
            self.ret(tail)
        elif t is ast.If:
            self.comp(node.test, frames, False)
            jf = self.emit(JUMPF, None)
            self.comp(node.then, frames, tail)
            if tail:
                self.patch(jf, self.here())
                self.comp(node.else_, frames, True)
            else:
                j = self.emit(JUMP, None)
                self.patch(jf, self.here())
                self.comp(node.else_, frames, False)
                self.patch(j, self.here())
        elif t is ast.Seq:
            for e in node.exprs[:-1]:
                self.comp(e, frames, False)
                self.emit(POP)
            self.comp(node.exprs[-1], frames, tail)
        elif t is ast.Lambda:
            self.emit(CLOSURE, compile_lambda(node, frames))
            self.ret(tail)
        elif t is ast.LocalSet:
            self.comp(node.expr, frames, False)
            d, i = _address(node.var, frames)
            if node.var.defined:
                self.emit(SETLOCALCHK, (d, i, node.var.name))
            else:
                self.emit(SETLOCAL, (d, i))
            self.ret(tail)
        elif t is ast.LocalDefine:
            self.comp(node.expr, frames, False)
            d, i = _address(node.var, frames)
            assert d == 0
            self.emit(DEFLOCAL, i)
            self.ret(tail)
        elif t is ast.GlobalSet:
            self.comp(node.expr, frames, False)
            self.emit(SETGLOBAL, node.cell)
            self.ret(tail)
        elif t is ast.GlobalDefine:
            self.comp(node.expr, frames, False)
            self.emit(DEFGLOBAL, node.cell)
            self.ret(tail)
        elif t is ast.App:
            self.comp_app(node, frames, tail)
        else:
            raise TypeError("unknown AST node %r" % node)

    def comp_app(self, node, frames, tail):
        fn = node.fn
        args = node.args
        n = len(args)
        if type(fn) is ast.Lambda and not fn.rest and n == fn.nreq:
            # ((lambda (x ...) body) arg ...): bind in place, no closure
            for x in args:
                self.comp(x, frames, False)
            nparams = fn.nreq
            self.emit(ENTER, (n, len(fn.frame.vars) - nparams))
            self.comp(fn.body, (fn.frame,) + frames, tail)
            if not tail:
                self.emit(LEAVE)
            return
        if type(fn) is ast.GlobalRef and type(fn.cell.value) is Primitive:
            p = fn.cell.value
            if n >= p.nreq and (p.rest or n <= p.nreq + p.nopt):
                for x in args:
                    self.comp(x, frames, False)
                op = FAST2.get(p) if n == 2 else FAST1.get(p) if n == 1 else None
                if op is not None:
                    self.emit(op, (fn.cell, p, tail))
                else:
                    self.emit(PRIM, (fn.cell, p, n, tail))
                self.ret(tail)
                return
        self.comp(fn, frames, False)
        for x in args:
            self.comp(x, frames, False)
        self.emit(TAILCALL if tail else CALL, n)
