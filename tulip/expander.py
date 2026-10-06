"""The expander: surface syntax to the core AST (ast.py).

Identifiers are either ``Symbol``s written by the user or ``Alias``es
introduced by a macro. An alias remembers the environment of the macro that
introduced it (explicit renaming): if a binding form inside the expansion
binds the alias, references to that same alias object see that binding;
otherwise the alias resolves in the macro's definition environment. That makes
both the built-in derived forms here and (stage 2) ``syntax-rules`` hygienic:
``(let ((if list)) (cond (#t 1)))`` still expands ``cond`` to the real ``if``.

Scopes: a ``Scope`` maps identifiers to bindings and chains to its parent;
the chain ends at a global ``Environment`` whose ``syntax`` dict holds keyword
bindings and whose ``cells`` hold global variables. Every lexical variable
becomes a unique ``Var`` in the ``Frame`` of its enclosing lambda.
"""

from __future__ import annotations

from collections import deque

from . import ast
from .types import (NIL, UNSPECIFIED, Cell, Environment, Pair, SchemeError,
                    Symbol, make_list, sym)


# --- identifiers and bindings ---------------------------------------------------

class Alias:
    __slots__ = ("name", "env")

    def __init__(self, name, env):
        self.name = name     # Symbol or Alias
        self.env = env       # Scope or Environment the macro was defined in

    def base(self):
        x = self
        while isinstance(x, Alias):
            x = x.name
        return x

    def __repr__(self):
        return "#<alias %s>" % self.base().name


def is_identifier(x):
    return isinstance(x, (Symbol, Alias))


def base_symbol(x):
    return x.base() if isinstance(x, Alias) else x


class Scope:
    __slots__ = ("parent", "frame", "bindings")

    def __init__(self, parent, frame):
        self.parent = parent
        self.frame = frame
        self.bindings = {}


class CoreForm:
    __slots__ = ("name", "handler")

    def __init__(self, name, handler):
        self.name = name
        self.handler = handler      # handler(expander, form, scope) -> Node

    def __repr__(self):
        return "#<syntax %s>" % self.name


class Macro:
    """A macro. ``transformer(expander, form, use_scope, macro_env)`` returns
    the expansion as surface syntax."""
    __slots__ = ("name", "transformer", "env")

    def __init__(self, name, transformer, env):
        self.name = name
        self.transformer = transformer
        self.env = env

    def expand(self, expander, form, use_scope):
        return self.transformer(expander, form, use_scope, self.env)

    def __repr__(self):
        return "#<macro %s>" % self.name


class Aux:
    """Auxiliary syntax (``else``, ``=>``, ``...``, ``_``, ``unquote``...):
    a keyword that only means something inside another form."""
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "#<aux-syntax %s>" % self.name


class GlobalBinding:
    __slots__ = ("env", "symbol")

    def __init__(self, env, symbol):
        self.env = env
        self.symbol = symbol


def lookup(ident, scope):
    while True:
        s = scope
        while isinstance(s, Scope):
            b = s.bindings.get(ident)
            if b is not None:
                return b
            s = s.parent
        if isinstance(ident, Alias):
            ident, scope = ident.name, ident.env
            continue
        b = s.syntax.get(ident)
        if b is not None:
            return b
        return GlobalBinding(s, ident)


def same_binding(a, b):
    if isinstance(a, GlobalBinding) and isinstance(b, GlobalBinding):
        return a.env is b.env and a.symbol is b.symbol
    return a is b


def global_env(scope):
    while isinstance(scope, Scope):
        scope = scope.parent
    return scope


def strip_syntax(x):
    """Remove aliases from quoted data. Data without aliases (anything the
    reader produced) is returned as is; otherwise it is copied. Both walks
    follow list spines iteratively and handle shared and circular structure
    (datum labels), so long and circular literals are fine."""
    if not _has_alias(x):
        return x
    return _strip_copy(x, {})


def _has_alias(x):
    stack = [x]
    seen = set()
    while stack:
        x = stack.pop()
        while True:
            if isinstance(x, Alias):
                return True
            if isinstance(x, Pair):
                if id(x) in seen:
                    break
                seen.add(id(x))
                stack.append(x.car)
                x = x.cdr
            elif isinstance(x, list):
                if id(x) not in seen:
                    seen.add(id(x))
                    stack.extend(x)
                break
            else:
                break
    return False


def _strip_copy(x, memo):
    if isinstance(x, Alias):
        return x.base()
    if isinstance(x, Pair):
        if id(x) in memo:
            return memo[id(x)]
        head = new = Pair(None, NIL)
        memo[id(x)] = head
        while True:
            new.car = _strip_copy(x.car, memo)
            x = x.cdr
            if not isinstance(x, Pair):
                new.cdr = _strip_copy(x, memo)
                return head
            if id(x) in memo:
                new.cdr = memo[id(x)]
                return head
            new.cdr = new = Pair(None, NIL)
            memo[id(x)] = new
    if isinstance(x, list):
        if id(x) in memo:
            return memo[id(x)]
        out = []
        memo[id(x)] = out
        out.extend(_strip_copy(i, memo) for i in x)
        return out
    return x


def syntax_error(message, form=None):
    if form is None:
        return SchemeError("syntax error: " + message)
    return SchemeError("syntax error: " + message, strip_syntax(form))


def form_list(form, who):
    """The elements of a form that must be a proper list."""
    out = []
    p = form
    while isinstance(p, Pair):
        out.append(p.car)
        p = p.cdr
    if p is not NIL:
        raise syntax_error("bad %s form (improper list)" % who, form)
    return out


def L(*items):
    return make_list(items)


# --- the expander ---------------------------------------------------------------

class Expander:
    def __init__(self, env: Environment, runtime=None):
        self.env = env
        self.runtime = runtime

    def expand_toplevel(self, form):
        return self.expand(form, self.env)

    # --- generic -------------------------------------------------------------

    def expand(self, x, scope):
        while True:
            if is_identifier(x):
                return self.expand_ref(x, scope)
            if isinstance(x, Pair):
                head = x.car
                if isinstance(head, CoreForm):     # embedded by a derived form
                    return head.handler(self, x, scope)
                if is_identifier(head):
                    b = lookup(head, scope)
                    if isinstance(b, CoreForm):
                        return b.handler(self, x, scope)
                    if isinstance(b, Macro):
                        x = b.expand(self, x, scope)
                        continue
                    if isinstance(b, Aux):
                        raise syntax_error("misplaced %s" % b.name, x)
                fn = self.expand(head, scope)
                args = [self.expand(a, scope) for a in form_list(x.cdr, "call")]
                return ast.App(fn, args)
            if x is NIL:
                raise syntax_error("empty combination ()")
            return ast.Const(strip_syntax(x))

    def expand_ref(self, ident, scope):
        b = lookup(ident, scope)
        if isinstance(b, ast.Var):
            return ast.LocalRef(b)
        if isinstance(b, GlobalBinding):
            return ast.GlobalRef(b.env.cell(b.symbol))
        raise syntax_error("keyword used as a variable", ident)

    def is_kw(self, x, use_scope, name, macro_env):
        """Is ``x`` (in ``use_scope``) the keyword ``name`` of ``macro_env``?"""
        if not is_identifier(x):
            return False
        return same_binding(lookup(x, use_scope),
                            lookup(sym(name), macro_env))

    def expand_body(self, forms, scope, who="body"):
        """Expand a lambda body in ``scope`` (a fresh Scope sharing the
        lambda's frame). Internal definitions become LocalDefine nodes; their
        names are bound before any right-hand side is expanded (letrec*)."""
        items = []
        queue = deque(forms)
        while queue:
            f = queue.popleft()
            while True:
                if isinstance(f, Pair) and is_identifier(f.car):
                    b = lookup(f.car, scope)
                    if b is DEFINE:
                        name, rhs = parse_define(f)
                        if name in scope.bindings:
                            raise syntax_error("duplicate definition", f)
                        var = scope.frame.new_var(base_symbol(name))
                        var.defined = True
                        scope.bindings[name] = var
                        items.append((var, rhs))
                        break
                    if b is BEGIN:
                        queue.extendleft(reversed(form_list(f.cdr, "begin")))
                        break
                    if isinstance(b, CoreForm) and b.name in BODY_DEFINERS:
                        BODY_DEFINERS[b.name](self, f, scope, items)
                        break
                    if isinstance(b, Macro):
                        f = b.expand(self, f, scope)
                        continue
                items.append((None, f))
                break
        nodes = []
        for var, f in items:
            if var is None:
                nodes.append(self.expand(f, scope))
            elif f is _SYNTAX_DEFINED:
                continue
            else:
                e = self.expand(f, scope)
                name_lambda(e, var.name)
                nodes.append(ast.LocalDefine(var, e))
        if not nodes or isinstance(nodes[-1], ast.LocalDefine):
            nodes.append(ast.Const(UNSPECIFIED))
        _mark_safe_definitions(nodes)
        return nodes

    def make_lambda(self, formals, body, scope, name=None):
        frame = ast.Frame()
        pscope = Scope(scope, frame)
        nreq = 0
        rest = False
        p = formals
        while isinstance(p, Pair):
            self._bind_param(p.car, pscope, formals)
            nreq += 1
            p = p.cdr
        if p is not NIL:
            self._bind_param(p, pscope, formals)
            rest = True
        bscope = Scope(pscope, frame)
        nodes = self.expand_body(body, bscope)
        return ast.Lambda(frame, nreq, rest, ast.seq(nodes), name)

    @staticmethod
    def _bind_param(ident, pscope, formals):
        if not is_identifier(ident):
            raise syntax_error("bad parameter", formals)
        if ident in pscope.bindings:
            raise syntax_error("duplicate parameter", formals)
        pscope.bindings[ident] = pscope.frame.new_var(base_symbol(ident))


_SYNTAX_DEFINED = object()


def _mark_safe_definitions(nodes):
    """If a body starts with definitions whose values are all lambda
    expressions, and no definition follows an expression, then no code runs
    before every one of them is assigned: making the closures runs nothing.
    References to those variables then need no "used before definition"
    check (this is what makes named-let loops cheap)."""
    defs = []
    seen_expression = False
    for n in nodes:
        if isinstance(n, ast.LocalDefine):
            if seen_expression or not isinstance(n.expr, ast.Lambda):
                return
            defs.append(n)
        else:
            seen_expression = True
    for n in defs:
        n.var.defined = False

# Core forms whose body-level behavior is special besides define/begin
# (filled in by stage 2: define-syntax, define-values, ...).
BODY_DEFINERS: dict = {}


def name_lambda(node, name):
    if isinstance(node, ast.Lambda) and node.name is None:
        node.name = name


def parse_define(form):
    """(define id expr) / (define id) / (define (id . formals) body...)
    -> (identifier, rhs surface form)."""
    if not isinstance(form.cdr, Pair):
        raise syntax_error("bad define", form)
    target = form.cdr.car
    rest = form.cdr.cdr
    if is_identifier(target):
        if rest is NIL:
            return target, UNSPECIFIED
        if not isinstance(rest, Pair) or rest.cdr is not NIL:
            raise syntax_error("bad define", form)
        return target, rest.car
    if isinstance(target, Pair):
        # (define (name . formals) body...) and curried (define ((f a) b) ...)
        name, formals = target.car, target.cdr
        rhs = Pair(_LAMBDA_ALIAS, Pair(formals, rest))
        while isinstance(name, Pair):
            rhs = L(_LAMBDA_ALIAS, name.cdr, rhs)
            name = name.car
        if not is_identifier(name):
            raise syntax_error("bad define", form)
        return name, rhs
    raise syntax_error("bad define", form)


# --- core forms -------------------------------------------------------------------

def _quote(exp, form, scope):
    args = form_list(form.cdr, "quote")
    if len(args) != 1:
        raise syntax_error("bad quote", form)
    return ast.Const(strip_syntax(args[0]))


def _if(exp, form, scope):
    args = form_list(form.cdr, "if")
    if len(args) == 2:
        return ast.If(exp.expand(args[0], scope), exp.expand(args[1], scope),
                      ast.Const(UNSPECIFIED))
    if len(args) == 3:
        return ast.If(*(exp.expand(a, scope) for a in args))
    raise syntax_error("bad if", form)


def check_mutable(env, form):
    if env.immutable:
        raise syntax_error("definition in an immutable environment", form)


def _define(exp, form, scope):
    if isinstance(scope, Scope):
        raise syntax_error("definition in expression context", form)
    check_mutable(scope, form)
    name, rhs = parse_define(form)
    symbol = base_symbol(name)
    scope.syntax.pop(symbol, None)
    if symbol in scope.imported:
        scope.imported.discard(symbol)
        scope.cells[symbol] = Cell(symbol)
    cell = scope.cell(symbol)
    e = exp.expand(rhs, scope)
    name_lambda(e, symbol)
    return ast.GlobalDefine(cell, e)


def _set(exp, form, scope):
    args = form_list(form.cdr, "set!")
    if len(args) != 2 or not is_identifier(args[0]):
        raise syntax_error("bad set!", form)
    b = lookup(args[0], scope)
    e = exp.expand(args[1], scope)
    if isinstance(b, ast.Var):
        b.assigned = True
        return ast.LocalSet(b, e)
    if isinstance(b, GlobalBinding):
        if b.symbol in b.env.imported:
            raise syntax_error("set! of an imported variable", form)
        return ast.GlobalSet(b.env.cell(b.symbol), e)
    raise syntax_error("set! of a keyword", form)


def _lambda(exp, form, scope):
    if not isinstance(form.cdr, Pair):
        raise syntax_error("bad lambda", form)
    formals = form.cdr.car
    body = form_list(form.cdr.cdr, "lambda")
    if not body:
        raise syntax_error("lambda with empty body", form)
    return exp.make_lambda(formals, body, scope)


def _begin(exp, form, scope):
    forms = form_list(form.cdr, "begin")
    return ast.seq([exp.expand(f, scope) for f in forms])


DEFINE = CoreForm("define", _define)
BEGIN = CoreForm("begin", _begin)

CORE_FORMS = [
    CoreForm("quote", _quote),
    CoreForm("if", _if),
    DEFINE,
    CoreForm("set!", _set),
    CoreForm("lambda", _lambda),
    BEGIN,
]

AUX_NAMES = ["else", "=>", "...", "_", "unquote", "unquote-splicing"]

_LAMBDA_ALIAS = CORE_FORMS[4]  # the lambda core form, embedded in expansions


# --- built-in derived forms (Python macros) ----------------------------------------

_counter = [0]


def fresh(name, env):
    """A fresh identifier no user code can refer to."""
    _counter[0] += 1
    return Alias(Symbol.uninterned("%s.%d" % (name, _counter[0])), env)


def _kw(env):
    return lambda name: Alias(sym(name), env)


def _bindings(x, form):
    names, inits = [], []
    for b in form_list(x, "binding list"):
        parts = form_list(b, "binding") if isinstance(b, Pair) else None
        if not parts or not is_identifier(parts[0]) or len(parts) > 2:
            raise syntax_error("bad binding", form)
        names.append(parts[0])
        inits.append(parts[1] if len(parts) == 2 else UNSPECIFIED)
    return names, inits


def m_let(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "let")
    if args and is_identifier(args[0]):
        if len(args) < 3:
            raise syntax_error("bad named let", form)
        name = args[0]
        names, inits = _bindings(args[1], form)
        lam = Pair(k("lambda"), Pair(make_list(names), make_list(args[2:])))
        return Pair(L(k("letrec"), L(L(name, lam)), name), make_list(inits))
    if len(args) < 2:
        raise syntax_error("bad let", form)
    names, inits = _bindings(args[0], form)
    lam = Pair(k("lambda"), Pair(make_list(names), make_list(args[1:])))
    return Pair(lam, make_list(inits))


def m_let_star(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "let*")
    if len(args) < 2:
        raise syntax_error("bad let*", form)
    bindings = form_list(args[0], "let*")
    body = make_list(args[1:])
    if len(bindings) <= 1:
        return Pair(k("let"), Pair(make_list(bindings), body))
    return L(k("let"), L(bindings[0]),
             Pair(k("let*"), Pair(make_list(bindings[1:]), body)))


def m_letrec(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "letrec")
    if len(args) < 2:
        raise syntax_error("bad letrec", form)
    names, inits = _bindings(args[0], form)
    defs = [L(k("define"), n, i) for n, i in zip(names, inits)]
    inner = Pair(k("let"), Pair(NIL, make_list(args[1:])))
    return Pair(k("let"), Pair(NIL, make_list(defs + [inner])))


def m_cond(exp, form, use, env):
    k = _kw(env)
    clauses = form_list(form.cdr, "cond")
    if not clauses:
        return UNSPECIFIED
    first = clauses[0]
    rest = Pair(k("cond"), make_list(clauses[1:]))
    if not isinstance(first, Pair):
        raise syntax_error("bad cond clause", first)
    test = first.car
    body = form_list(first.cdr, "cond clause")
    if exp.is_kw(test, use, "else", env):
        if len(clauses) != 1:
            raise syntax_error("else clause must be last", form)
        if not body:
            raise syntax_error("empty else clause", form)
        return Pair(k("begin"), make_list(body))
    if not body:
        t = fresh("t", env)
        return L(k("let"), L(L(t, test)), L(k("if"), t, t, rest))
    if exp.is_kw(body[0], use, "=>", env):
        if len(body) != 2:
            raise syntax_error("bad => clause", first)
        t = fresh("t", env)
        return L(k("let"), L(L(t, test)), L(k("if"), t, L(body[1], t), rest))
    return L(k("if"), test, Pair(k("begin"), make_list(body)), rest)


def m_case(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "case")
    if not args:
        raise syntax_error("bad case", form)
    key = args[0]
    t = fresh("key", env)
    result = UNSPECIFIED
    clauses = args[1:]
    for i in range(len(clauses) - 1, -1, -1):
        clause = clauses[i]
        if not isinstance(clause, Pair):
            raise syntax_error("bad case clause", clause)
        body = form_list(clause.cdr, "case clause")
        if not body:
            raise syntax_error("empty case clause", clause)
        if exp.is_kw(body[0], use, "=>", env):
            if len(body) != 2:
                raise syntax_error("bad => clause", clause)
            action = L(body[1], t)
        else:
            action = Pair(k("begin"), make_list(body))
        if exp.is_kw(clause.car, use, "else", env):
            if i != len(clauses) - 1:
                raise syntax_error("else clause must be last", form)
            result = action
        else:
            data = form_list(clause.car, "case data")
            test = L(_MEMV, t, L(k("quote"), make_list(data)))
            result = L(k("if"), test, action, result)
    return L(k("let"), L(L(t, key)), result)


def m_and(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "and")
    if not args:
        return True
    if len(args) == 1:
        return args[0]
    return L(k("if"), args[0], Pair(k("and"), make_list(args[1:])), False)


def m_or(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "or")
    if not args:
        return False
    if len(args) == 1:
        return args[0]
    t = fresh("t", env)
    return L(k("let"), L(L(t, args[0])),
             L(k("if"), t, t, Pair(k("or"), make_list(args[1:]))))


def m_when(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "when")
    if len(args) < 2:
        raise syntax_error("bad when", form)
    return L(k("if"), args[0], Pair(k("begin"), make_list(args[1:])))


def m_unless(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "unless")
    if len(args) < 2:
        raise syntax_error("bad unless", form)
    return L(k("if"), args[0], UNSPECIFIED,
             Pair(k("begin"), make_list(args[1:])))


def m_do(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "do")
    if len(args) < 2:
        raise syntax_error("bad do", form)
    specs = form_list(args[0], "do bindings")
    names, inits, steps = [], [], []
    for spec in specs:
        parts = form_list(spec, "do binding") if isinstance(spec, Pair) else None
        if not parts or not is_identifier(parts[0]) or len(parts) not in (2, 3):
            raise syntax_error("bad do binding", spec)
        names.append(parts[0])
        inits.append(parts[1])
        steps.append(parts[2] if len(parts) == 3 else parts[0])
    exit_clause = form_list(args[1], "do exit clause")
    if not exit_clause:
        raise syntax_error("bad do exit clause", form)
    test, results = exit_clause[0], exit_clause[1:]
    loop = fresh("do-loop", env)
    done = Pair(k("begin"), make_list(results)) if results else UNSPECIFIED
    again = Pair(k("begin"),
                 make_list(list(args[2:]) + [Pair(loop, make_list(steps))]))
    return L(k("let"), loop, make_list([L(n, i) for n, i in zip(names, inits)]),
             L(k("if"), test, done, again))


def m_quasiquote(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "quasiquote")
    if len(args) != 1:
        raise syntax_error("bad quasiquote", form)

    def is_(x, name):
        return exp.is_kw(x, use, name, env)

    def tagged(x, name):
        return isinstance(x, Pair) and is_(x.car, name) \
            and isinstance(x.cdr, Pair) and x.cdr.cdr is NIL

    def has_unquote(x, depth):
        if isinstance(x, Pair):
            if tagged(x, "unquote") or tagged(x, "unquote-splicing"):
                return True
            if tagged(x, "quasiquote"):
                return has_unquote(x.cdr.car, depth + 1)
            while isinstance(x, Pair):
                if has_unquote(x.car, depth):
                    return True
                x = x.cdr
                if tagged(x, "unquote"):
                    return True
            return has_unquote(x, depth)
        if isinstance(x, list):
            return any(has_unquote(i, depth) for i in x)
        return False

    def quote(x):
        return L(k("quote"), x)

    def qq(x, depth):
        if not has_unquote(x, depth):
            if isinstance(x, (Pair, list)) or is_identifier(x) or x is NIL:
                return quote(x)
            return x
        if isinstance(x, list):
            return L(_LIST_TO_VECTOR, qq(make_list(x), depth))
        if tagged(x, "unquote"):
            if depth == 1:
                return x.cdr.car
            return L(_LIST, quote(sym("unquote")), qq(x.cdr.car, depth - 1))
        if tagged(x, "quasiquote"):
            return L(_LIST, quote(sym("quasiquote")), qq(x.cdr.car, depth + 1))
        head = x.car
        if tagged(head, "unquote-splicing"):
            rest = qq(x.cdr, depth)
            if depth == 1:
                return L(_APPEND2, head.cdr.car, rest)
            return L(_CONS, L(_LIST, quote(sym("unquote-splicing")),
                              qq(head.cdr.car, depth - 1)), rest)
        return L(_CONS, qq(head, depth), qq(x.cdr, depth))

    return qq(args[0], 1)


def m_delay_force(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "delay-force")
    if len(args) != 1:
        raise syntax_error("bad delay-force", form)
    return L(_MAKE_PROMISE_RAW, False, L(k("lambda"), NIL, args[0]))


def m_delay(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "delay")
    if len(args) != 1:
        raise syntax_error("bad delay", form)
    return L(k("delay-force"), L(_MAKE_PROMISE_RAW, True, args[0]))


def m_case_lambda(exp, form, use, env):
    k = _kw(env)
    clauses = form_list(form.cdr, "case-lambda")
    lambdas = []
    for c in clauses:
        if not isinstance(c, Pair):
            raise syntax_error("bad case-lambda clause", c)
        lambdas.append(Pair(k("lambda"), c))
    return Pair(_MAKE_CASE_LAMBDA, make_list(lambdas))


def m_define_record_type(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "define-record-type")
    if len(args) < 2:
        raise syntax_error("bad define-record-type", form)
    tname, ctor, pred = args[0], args[1], args[2] if len(args) > 2 else False
    fspecs = [form_list(f, "record field") if isinstance(f, Pair) else [f]
              for f in args[3:]]
    fields = [f[0] for f in fspecs]
    if not all(is_identifier(f) for f in fields):
        raise syntax_error("bad record field", form)
    if isinstance(tname, Pair):          # (name parent...) from SRFI 136: unsupported
        raise syntax_error("record type name must be an identifier", form)
    rt = tname
    field_syms = make_list([base_symbol(f) for f in fields])
    out = [L(k("define"), rt, L(_MAKE_RECORD_TYPE, L(k("quote"), base_symbol(tname)),
                                L(k("quote"), field_syms)))]
    if ctor is not False:
        if is_identifier(ctor):
            cname, cfields = ctor, fields
        else:
            parts = form_list(ctor, "record constructor")
            cname, cfields = parts[0], parts[1:]
        cfield_syms = [base_symbol(f) for f in cfields]
        for f in cfield_syms:
            if f not in [base_symbol(x) for x in fields]:
                raise syntax_error("constructor field is not a field", f)
        out.append(L(k("define"), cname,
                     L(_RECORD_CONSTRUCTOR, rt, L(k("quote"), make_list(cfield_syms)))))
    if pred is not False:
        out.append(L(k("define"), pred, L(_RECORD_PREDICATE, rt)))
    for spec in fspecs:
        fsym = L(k("quote"), base_symbol(spec[0]))
        if len(spec) > 1:
            out.append(L(k("define"), spec[1], L(_RECORD_ACCESSOR, rt, fsym)))
        if len(spec) > 2:
            out.append(L(k("define"), spec[2], L(_RECORD_MODIFIER, rt, fsym)))
        if len(spec) > 3:
            raise syntax_error("bad record field spec", form)
    return Pair(k("begin"), make_list(out))


def m_parameterize(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "parameterize")
    if len(args) < 2:
        raise syntax_error("bad parameterize", form)
    params, vals = [], []
    for b in form_list(args[0], "parameterize bindings"):
        parts = form_list(b, "parameterize binding") if isinstance(b, Pair) else None
        if not parts or len(parts) != 2:
            raise syntax_error("bad parameterize binding", form)
        params.append(parts[0])
        vals.append(parts[1])
    return L(k("%parameterize"), Pair(k("list"), make_list(params)),
             Pair(k("list"), make_list(vals)),
             Pair(k("lambda"), Pair(NIL, make_list(args[1:]))))


def m_guard(exp, form, use, env):
    """R7RS 4.2.7, following the report's reference expansion: the clauses
    run in the dynamic environment of the guard; with no matching clause the
    condition is re-raised with raise-continuable in the dynamic environment
    of the original raise."""
    k = _kw(env)
    args = form_list(form.cdr, "guard")
    if len(args) < 2 or not isinstance(args[0], Pair)             or not is_identifier(args[0].car):
        raise syntax_error("bad guard", form)
    var = args[0].car
    clauses = form_list(args[0].cdr, "guard clauses")
    body = make_list(args[1:])
    guard_k, handler_k = fresh("guard-k", env), fresh("handler-k", env)
    condition, vals = fresh("condition", env), fresh("args", env)
    reraise = L(handler_k, L(k("lambda"), NIL, L(k("raise-continuable"), condition)))
    has_else = clauses and isinstance(clauses[-1], Pair)         and exp.is_kw(clauses[-1].car, use, "else", env)
    if not has_else:
        clauses = clauses + [L(k("else"), reraise)]
    handler = L(k("lambda"), L(condition),
                L(L(k("call/cc"),
                    L(k("lambda"), L(handler_k),
                      L(guard_k,
                        L(k("lambda"), NIL,
                          L(k("let"), L(L(var, condition)),
                            Pair(k("cond"), make_list(clauses)))))))))
    thunk = L(k("lambda"), NIL,
              L(k("call-with-values"), Pair(k("lambda"), Pair(NIL, body)),
                L(k("lambda"), vals,
                  L(guard_k, L(k("lambda"), NIL,
                               L(k("apply"), k("values"), vals))))))
    return L(L(k("call/cc"),
               L(k("lambda"), L(guard_k),
                 L(k("with-exception-handler"), handler, thunk))))


def _values_formals(formals, env):
    """Fresh temporaries with the same shape as ``formals``; returns
    (temp formals, [(user identifier, temp)...])."""
    pairs = []
    temps = []
    p = formals
    while isinstance(p, Pair):
        if not is_identifier(p.car):
            raise syntax_error("bad formals", formals)
        t = fresh("v", env)
        temps.append(t)
        pairs.append((p.car, t))
        p = p.cdr
    tail = NIL
    if p is not NIL:
        if not is_identifier(p):
            raise syntax_error("bad formals", formals)
        tail = fresh("rest", env)
        pairs.append((p, tail))
    return make_list(temps, tail), pairs


def m_let_values(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "let-values")
    if len(args) < 2:
        raise syntax_error("bad let-values", form)
    bindings = form_list(args[0], "let-values bindings")
    all_pairs = []
    specs = []
    for b in bindings:
        parts = form_list(b, "let-values binding") if isinstance(b, Pair) else None
        if not parts or len(parts) != 2:
            raise syntax_error("bad let-values binding", form)
        temps, pairs = _values_formals(parts[0], env)
        specs.append((temps, parts[1]))
        all_pairs.extend(pairs)
    result = Pair(k("let"), Pair(make_list([L(u, t) for u, t in all_pairs]),
                                 make_list(args[1:])))
    for temps, expr in reversed(specs):
        result = L(k("call-with-values"), L(k("lambda"), NIL, expr),
                   L(k("lambda"), temps, result))
    return result


def m_let_star_values(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "let*-values")
    if len(args) < 2:
        raise syntax_error("bad let*-values", form)
    bindings = form_list(args[0], "let*-values bindings")
    if len(bindings) <= 1:
        return Pair(k("let-values"), Pair(make_list(bindings), make_list(args[1:])))
    return L(k("let-values"), L(bindings[0]),
             Pair(k("let*-values"), Pair(make_list(bindings[1:]), make_list(args[1:]))))


def m_define_values(exp, form, use, env):
    k = _kw(env)
    args = form_list(form.cdr, "define-values")
    if len(args) != 2:
        raise syntax_error("bad define-values", form)
    temps, pairs = _values_formals(args[0], env)
    defs = [L(k("define"), u) for u, _ in pairs]
    sets = [L(k("set!"), u, t) for u, t in pairs]
    setter = Pair(k("lambda"), Pair(temps, make_list(sets + [UNSPECIFIED])))
    return Pair(k("begin"), make_list(
        defs + [L(k("call-with-values"), L(k("lambda"), NIL, args[1]), setter)]))


PYTHON_MACROS = {
    "let": m_let, "let*": m_let_star, "letrec": m_letrec, "letrec*": m_letrec,
    "cond": m_cond, "case": m_case, "and": m_and, "or": m_or,
    "when": m_when, "unless": m_unless, "do": m_do,
    "quasiquote": m_quasiquote, "delay": m_delay, "delay-force": m_delay_force,
    "case-lambda": m_case_lambda, "define-record-type": m_define_record_type,
    "parameterize": m_parameterize, "guard": m_guard,
    "let-values": m_let_values, "let*-values": m_let_star_values,
    "define-values": m_define_values,
}

# Procedures the derived forms call directly (embedded as constants, so user
# redefinition of e.g. ``cons`` can't break quasiquote). Set by install().
_MEMV = _CONS = _LIST = _APPEND2 = _LIST_TO_VECTOR = None
_MAKE_PROMISE_RAW = _MAKE_CASE_LAMBDA = None
_MAKE_RECORD_TYPE = _RECORD_CONSTRUCTOR = _RECORD_PREDICATE = None
_RECORD_ACCESSOR = _RECORD_MODIFIER = None


def install(env: Environment, helpers: dict):
    """Bind the core forms, derived forms and auxiliary syntax in ``env``.

    ``helpers`` maps the internal names above (``memv``, ``cons``...) to
    procedure objects.
    """
    global _MEMV, _CONS, _LIST, _APPEND2, _LIST_TO_VECTOR, \
        _MAKE_PROMISE_RAW, _MAKE_CASE_LAMBDA, _MAKE_RECORD_TYPE, \
        _RECORD_CONSTRUCTOR, _RECORD_PREDICATE, _RECORD_ACCESSOR, \
        _RECORD_MODIFIER
    for cf in CORE_FORMS:
        env.syntax[sym(cf.name)] = cf
    for name, fn in PYTHON_MACROS.items():
        env.syntax[sym(name)] = Macro(name, fn, env)
    for name in AUX_NAMES:
        env.syntax[sym(name)] = Aux(name)
    _MEMV = helpers["memv"]
    _CONS = helpers["cons"]
    _LIST = helpers["list"]
    _APPEND2 = helpers["append"]
    _LIST_TO_VECTOR = helpers["list->vector"]
    _MAKE_PROMISE_RAW = helpers["%make-promise"]
    _MAKE_CASE_LAMBDA = helpers["%case-lambda"]
    _MAKE_RECORD_TYPE = helpers["%make-record-type"]
    _RECORD_CONSTRUCTOR = helpers["%record-constructor"]
    _RECORD_PREDICATE = helpers["%record-predicate"]
    _RECORD_ACCESSOR = helpers["%record-accessor"]
    _RECORD_MODIFIER = helpers["%record-modifier"]
