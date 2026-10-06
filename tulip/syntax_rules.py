"""syntax-rules (R7RS 4.3.2) and the forms that bind macros: define-syntax,
let-syntax, letrec-syntax.

Hygiene comes from the expander's aliases: every identifier a template
introduces is replaced by an ``Alias`` of itself closed over the macro's
definition environment (one alias per identifier per expansion). So a binding
the template introduces cannot capture the user's identifiers, and a free
identifier in the template means what it meant where the macro was defined.
"""

from __future__ import annotations

from . import ast
from .expander import (Alias, CoreForm, Macro, Scope, base_symbol, check_mutable,
                       form_list, is_identifier, lookup, same_binding, syntax_error,
                       BODY_DEFINERS)
from .prims_data import equal
from .types import NIL, UNSPECIFIED, Pair, make_list, sym

ELLIPSIS = sym("...")
UNDERSCORE = sym("_")


class Multi:
    """The matches of a pattern variable under an ellipsis."""
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items


class SyntaxRules:
    def __init__(self, ellipsis, literals, rules, env, name=None):
        self.ellipsis = ellipsis      # a Symbol (compared by base symbol)
        self.literals = literals      # identifiers
        self.rules = rules            # [(pattern, template)]
        self.env = env
        self.name = name

    # --- the transformer --------------------------------------------------------

    def __call__(self, exp, form, use_scope, macro_env):
        for pattern, template in self.rules:
            b = {}
            if not isinstance(pattern, Pair):
                continue
            if self._match(pattern.cdr, form.cdr, b, exp, use_scope):
                renames = {}
                return self._instantiate(template, b, renames, True)
        raise syntax_error("no syntax-rules pattern matches", form)

    # --- matching -----------------------------------------------------------------

    def _is_ellipsis(self, x):
        return is_identifier(x) and base_symbol(x) is self.ellipsis \
            and x not in self.literals

    def _match(self, pat, form, b, exp, use):
        if is_identifier(pat):
            if pat in self.literals:
                return is_identifier(form) and same_binding(
                    lookup(form, use), lookup(pat, self.env))
            if base_symbol(pat) is UNDERSCORE:
                return True
            b[pat] = form
            return True
        if isinstance(pat, Pair):
            if isinstance(pat.cdr, Pair) and self._is_ellipsis(pat.cdr.car):
                return self._match_ellipsis(pat, form, b, exp, use)
            return isinstance(form, Pair) \
                and self._match(pat.car, form.car, b, exp, use) \
                and self._match(pat.cdr, form.cdr, b, exp, use)
        if pat is NIL:
            return form is NIL
        if isinstance(pat, list):
            return isinstance(form, list) and \
                self._match(make_list(pat), make_list(form), b, exp, use)
        return equal(pat, form)

    def _match_ellipsis(self, pat, form, b, exp, use):
        sub = pat.car
        tail = pat.cdr.cdr
        min_tail = 0
        p = tail
        while isinstance(p, Pair):
            min_tail += 1
            p = p.cdr
        items = []
        f = form
        while isinstance(f, Pair):
            items.append(f)
            f = f.cdr
        n = len(items) - min_tail
        if n < 0:
            return False
        matches = []
        f = form
        for _ in range(n):
            sb = {}
            if not self._match(sub, f.car, sb, exp, use):
                return False
            matches.append(sb)
            f = f.cdr
        for var in self._pattern_vars(sub):
            b[var] = Multi([m[var] for m in matches])
        return self._match(tail, f, b, exp, use)

    def _pattern_vars(self, pat):
        out = []
        stack = [pat]
        while stack:
            x = stack.pop()
            if is_identifier(x):
                if x not in self.literals and not self._is_ellipsis(x) \
                        and base_symbol(x) is not UNDERSCORE:
                    out.append(x)
            elif isinstance(x, Pair):
                stack.append(x.cdr)
                stack.append(x.car)
            elif isinstance(x, list):
                stack.extend(x)
        return out

    # --- templates --------------------------------------------------------------------

    def _rename(self, ident, renames):
        a = renames.get(ident)
        if a is None:
            a = Alias(ident, self.env)
            renames[ident] = a
        return a

    def _instantiate(self, t, b, renames, ellipsis_active):
        if is_identifier(t):
            if t in b:
                v = b[t]
                if isinstance(v, Multi):
                    raise syntax_error("pattern variable used without ellipsis",
                                       base_symbol(t))
                return v
            return self._rename(t, renames)
        if isinstance(t, Pair):
            if ellipsis_active and self._is_ellipsis(t.car) \
                    and isinstance(t.cdr, Pair) and t.cdr.cdr is NIL:
                # (... template): ellipses inside are literal
                return self._instantiate(t.cdr.car, b, renames, False)
            # walk the list spine iteratively, so long templates don't
            # exhaust the Python stack
            items = []
            while isinstance(t, Pair):
                if ellipsis_active and isinstance(t.cdr, Pair) \
                        and self._is_ellipsis(t.cdr.car):
                    depth = 0
                    rest = t.cdr
                    while isinstance(rest, Pair) and self._is_ellipsis(rest.car):
                        depth += 1
                        rest = rest.cdr
                    items.extend(self._expand_ellipsis(t.car, b, renames, depth))
                    t = rest
                else:
                    items.append(self._instantiate(t.car, b, renames, ellipsis_active))
                    t = t.cdr
            return make_list(items, self._instantiate(t, b, renames, ellipsis_active))
        if isinstance(t, list):
            return list(self._instantiate(make_list(t), b, renames, ellipsis_active))
        return t

    def _expand_ellipsis(self, sub, b, renames, depth):
        vars_ = [v for v in self._template_vars(sub, b) if isinstance(b[v], Multi)]
        if not vars_:
            raise syntax_error("ellipsis template has no pattern variable "
                               "with matches to repeat")
        n = len(b[vars_[0]].items)
        for v in vars_:
            if len(b[v].items) != n:
                raise syntax_error("pattern variables under one ellipsis "
                                   "matched different lengths")
        out = []
        for i in range(n):
            b2 = dict(b)
            for v in vars_:
                b2[v] = b[v].items[i]
            if depth > 1:
                out.extend(self._expand_ellipsis(sub, b2, renames, depth - 1))
            else:
                out.append(self._instantiate(sub, b2, renames, True))
        return out

    def _template_vars(self, t, b):
        out = []
        stack = [t]
        while stack:
            x = stack.pop()
            if is_identifier(x):
                if x in b:
                    out.append(x)
            elif isinstance(x, Pair):
                stack.append(x.cdr)
                stack.append(x.car)
            elif isinstance(x, list):
                stack.extend(x)
        return out


# --- parsing transformer specs --------------------------------------------------------

def make_transformer(exp, spec, scope, name):
    """Turn a transformer spec, evaluated in ``scope``, into a Macro."""
    if isinstance(spec, Pair) and is_identifier(spec.car):
        b = lookup(spec.car, scope)
        if b is SYNTAX_RULES:
            return Macro(base_symbol(name).name, parse_syntax_rules(spec, scope), scope)
        if b is ER_MACRO:
            raise syntax_error("er-macro-transformer is not supported", spec)
    if is_identifier(spec):
        b = lookup(spec, scope)
        if isinstance(b, Macro):
            return b
    raise syntax_error("bad transformer (only syntax-rules is supported)", spec)


def parse_syntax_rules(spec, scope):
    args = form_list(spec.cdr, "syntax-rules")
    ellipsis = ELLIPSIS
    if args and is_identifier(args[0]):
        ellipsis = base_symbol(args[0])
        args = args[1:]
    if not args:
        raise syntax_error("bad syntax-rules", spec)
    literals = form_list(args[0], "syntax-rules literals")
    if not all(is_identifier(x) for x in literals):
        raise syntax_error("bad syntax-rules literals", spec)
    rules = []
    for r in args[1:]:
        parts = form_list(r, "syntax rule") if isinstance(r, Pair) else None
        if not parts or len(parts) != 2:
            raise syntax_error("bad syntax rule", r)
        rules.append((parts[0], parts[1]))
    return SyntaxRules(ellipsis, literals, rules, scope)


# --- binding forms ---------------------------------------------------------------------

def _define_syntax(exp, form, scope):
    args = form_list(form.cdr, "define-syntax")
    if len(args) != 2 or not is_identifier(args[0]):
        raise syntax_error("bad define-syntax", form)
    if isinstance(scope, Scope):
        raise syntax_error("define-syntax in expression context", form)
    check_mutable(scope, form)
    macro = make_transformer(exp, args[1], scope, args[0])
    scope.syntax[base_symbol(args[0])] = macro
    return ast.Const(UNSPECIFIED)


def _body_define_syntax(exp, form, scope, items):
    args = form_list(form.cdr, "define-syntax")
    if len(args) != 2 or not is_identifier(args[0]):
        raise syntax_error("bad define-syntax", form)
    scope.bindings[args[0]] = make_transformer(exp, args[1], scope, args[0])


def _let_syntax(recursive):
    def handler(exp, form, scope):
        who = "letrec-syntax" if recursive else "let-syntax"
        args = form_list(form.cdr, who)
        if len(args) < 2:
            raise syntax_error("bad " + who, form)
        frame = ast.Frame()
        inner = Scope(scope, frame)
        for b in form_list(args[0], who + " bindings"):
            parts = form_list(b, who + " binding") if isinstance(b, Pair) else None
            if not parts or len(parts) != 2 or not is_identifier(parts[0]):
                raise syntax_error("bad %s binding" % who, form)
            spec_scope = inner if recursive else scope
            inner.bindings[parts[0]] = make_transformer(exp, parts[1], spec_scope,
                                                        parts[0])
        nodes = exp.expand_body(args[1:], inner)
        return ast.App(ast.Lambda(frame, 0, False, ast.seq(nodes)), [])
    return handler


def _syntax_rules_misplaced(exp, form, scope):
    raise syntax_error("syntax-rules outside a macro definition", form)


SYNTAX_RULES = CoreForm("syntax-rules", _syntax_rules_misplaced)
ER_MACRO = CoreForm("er-macro-transformer", _syntax_rules_misplaced)

CORE_FORMS = [
    CoreForm("define-syntax", _define_syntax),
    CoreForm("let-syntax", _let_syntax(False)),
    CoreForm("letrec-syntax", _let_syntax(True)),
    SYNTAX_RULES,
]

BODY_DEFINERS["define-syntax"] = _body_define_syntax


def install(env):
    for cf in CORE_FORMS:
        env.syntax[sym(cf.name)] = cf

