"""Libraries: define-library, import, the standard R7RS-small libraries,
cond-expand and include.

A library is an ``Environment`` plus an export table mapping external names
to bindings. A binding is either a ``Cell`` (a variable: importers share the
very same cell, so imports are live and free at run time) or a syntactic
binding (core form, macro, auxiliary syntax). All built-ins live in the
runtime's system environment; each standard library exports a subset of it.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from . import ast
from .expander import (Alias, CoreForm, Macro, Scope, form_list, strip_syntax,
                       syntax_error)
from .reader import Reader
from .registry import prim
from .types import (UNSPECIFIED, Cell, Environment, MString, Pair,
                    SchemeError, Symbol, make_list, sym)


# --- standard library export lists (R7RS appendix A) --------------------------------

_BASE = """
* + - ... / < <= = => > >= _ abs and append apply assoc assq assv begin
binary-port? boolean=? boolean? bytevector bytevector-append bytevector-copy
bytevector-copy! bytevector-length bytevector-u8-ref bytevector-u8-set!
bytevector? caar cadr call-with-current-continuation call-with-port
call-with-values call/cc car case cdar cddr cdr ceiling char->integer
char-ready? char<=? char<? char=? char>=? char>? char? close-input-port
close-output-port close-port complex? cond cond-expand cons
current-error-port current-input-port current-output-port define
define-record-type define-syntax define-values denominator do dynamic-wind
else eof-object eof-object? eq? equal? eqv? error error-object-irritants
error-object-message error-object? even? exact exact-integer-sqrt
exact-integer? exact? expt features file-error? floor floor-quotient
floor-remainder floor/ flush-output-port for-each gcd get-output-bytevector
get-output-string guard if import include include-ci inexact inexact?
input-port-open? input-port? integer->char integer? lambda lcm length let let*
let*-values let-syntax let-values letrec letrec* letrec-syntax list
list->string list->vector list-copy list-ref list-set! list-tail list?
make-bytevector make-list make-parameter make-string make-vector map max
member memq memv min modulo negative? newline not null? number->string
number? numerator odd? open-input-bytevector open-input-string
open-output-bytevector open-output-string or output-port-open? output-port?
pair? parameterize peek-char peek-u8 positive? procedure? quasiquote quote
quotient raise raise-continuable rational? rationalize read-bytevector
read-bytevector! read-char read-error? read-line read-string read-u8 real?
remainder reverse round set! set-car! set-cdr! square string string->list
string->number string->symbol string->utf8 string->vector string-append
string-copy string-copy! string-fill! string-for-each string-length
string-map string-ref string-set! string<=? string<? string=? string>=?
string>? string? substring symbol->string symbol=? symbol? syntax-error
syntax-rules textual-port? truncate truncate-quotient truncate-remainder
truncate/ u8-ready? unless unquote unquote-splicing utf8->string values
vector vector->list vector->string vector-append vector-copy vector-copy!
vector-fill! vector-for-each vector-length vector-map vector-ref vector-set!
vector? when with-exception-handler write-bytevector write-char write-string
write-u8 zero?
"""

_CXR = " ".join("c%sr" % p for p in [
    "aaa", "aad", "ada", "add", "daa", "dad", "dda", "ddd", "aaaa", "aaad",
    "aada", "aadd", "adaa", "adad", "adda", "addd", "daaa", "daad", "dada",
    "dadd", "ddaa", "ddad", "ddda", "dddd"])

STANDARD_LIBRARIES = {
    ("scheme", "base"): _BASE,
    ("scheme", "case-lambda"): "case-lambda",
    ("scheme", "char"): """
        char-alphabetic? char-ci<=? char-ci<? char-ci=? char-ci>=? char-ci>?
        char-downcase char-foldcase char-lower-case? char-numeric? char-upcase
        char-upper-case? char-whitespace? digit-value string-ci<=? string-ci<?
        string-ci=? string-ci>=? string-ci>? string-downcase string-foldcase
        string-upcase""",
    ("scheme", "complex"): """
        angle imag-part magnitude make-polar make-rectangular real-part""",
    ("scheme", "cxr"): _CXR,
    ("scheme", "eval"): "environment eval",
    ("scheme", "file"): """
        call-with-input-file call-with-output-file delete-file file-exists?
        open-binary-input-file open-binary-output-file open-input-file
        open-output-file with-input-from-file with-output-to-file""",
    ("scheme", "inexact"): """
        acos asin atan cos exp finite? infinite? log nan? sin sqrt tan""",
    ("scheme", "lazy"): "delay delay-force force make-promise promise?",
    ("scheme", "load"): "load",
    ("scheme", "process-context"): """
        command-line emergency-exit exit get-environment-variable
        get-environment-variables""",
    ("scheme", "read"): "read",
    ("scheme", "repl"): "interaction-environment",
    ("scheme", "time"): "current-jiffy current-second jiffies-per-second",
    ("scheme", "write"): "display write write-shared write-simple",
    ("scheme", "r5rs"): """
        * + - / < <= = > >= abs acos and angle append apply asin assoc assq
        assv atan begin boolean? caar cadr call-with-current-continuation
        call-with-input-file call-with-output-file call-with-values car case
        cdar cddr cdr ceiling char->integer char-alphabetic? char-ci<=?
        char-ci<? char-ci=? char-ci>=? char-ci>? char-downcase
        char-lower-case? char-numeric? char-ready? char-upcase
        char-upper-case? char-whitespace? char<=? char<? char=? char>=? char>?
        char? close-input-port close-output-port complex? cond cons cos
        current-input-port current-output-port define define-syntax delay
        denominator display do dynamic-wind eof-object? eq? equal? eqv? eval
        even? exact->inexact exact? exp expt floor for-each force gcd if
        imag-part inexact->exact inexact? input-port? integer->char integer?
        interaction-environment lambda lcm length let let* let-syntax letrec
        letrec-syntax list list->string list->vector list-ref list-tail list?
        load log magnitude make-polar make-rectangular make-string make-vector
        map max member memq memv min modulo negative? newline not
        null-environment null? number->string number? numerator odd?
        open-input-file open-output-file or output-port? pair? peek-char
        positive? procedure? quasiquote quote quotient rational? rationalize
        read read-char real-part real? remainder reverse round
        scheme-report-environment set! set-car! set-cdr! sin sqrt string
        string->list string->number string->symbol string-append string-ci<=?
        string-ci<? string-ci=? string-ci>=? string-ci>? string-copy
        string-fill! string-length string-ref string-set! string<=? string<?
        string=? string>=? string>? string? substring symbol->string symbol?
        tan truncate values vector vector->list vector-fill! vector-length
        vector-ref vector-set! vector? with-input-from-file
        with-output-to-file write write-char zero? """ + _CXR,
}

FEATURES = ["r7rs", "exact-closed", "ratios", "full-unicode", "tulip",
            "tulip-0.1", "python", sys.platform,
            "windows" if os.name == "nt" else "posix",
            platform.machine().lower() or "unknown-machine"]


@prim("features", 0)
def features():
    return make_list([sym(f) for f in FEATURES])


class Library:
    def __init__(self, name, env, exports):
        self.name = name            # tuple of str / int
        self.env = env
        self.exports = exports      # Symbol -> binding

    def __repr__(self):
        return "#<library (%s)>" % " ".join(str(p) for p in self.name)


def library_name(spec):
    """A library name datum -> a hashable tuple."""
    parts = []
    for p in form_list(spec, "library name"):
        p = strip_syntax(p)
        if isinstance(p, Symbol):
            parts.append(p.name)
        elif type(p) is int and p >= 0:
            parts.append(p)
        else:
            raise syntax_error("bad library name", spec)
    if not parts:
        raise syntax_error("empty library name", spec)
    return tuple(parts)


def binding_of(env, symbol):
    """The binding ``symbol`` has in ``env`` (for export), or None."""
    b = env.syntax.get(symbol)
    if b is not None:
        return b
    return env.cells.get(symbol)


class LibraryManager:
    def __init__(self, runtime):
        self.runtime = runtime
        self.libraries = {}
        self.search_path = [Path.cwd()]
        self.missing = []           # standard names not implemented (dev aid)
        self._loading = set()

    # --- standard libraries --------------------------------------------------------

    def define_standard(self, system):
        for name, names in STANDARD_LIBRARIES.items():
            exports = {}
            for n in names.split():
                s = sym(n)
                b = binding_of(system, s)
                if b is None:
                    self.missing.append((name, n))
                    continue
                exports[s] = b
            self.libraries[name] = Library(name, system, exports)

    # --- finding libraries ------------------------------------------------------------

    def exists(self, name):
        return name in self.libraries or self._library_file(name) is not None

    def find(self, name):
        lib = self.libraries.get(name)
        if lib is not None:
            return lib
        path = self._library_file(name)
        if path is None:
            raise SchemeError("library not found", make_list(
                [sym(p) if isinstance(p, str) else p for p in name]))
        if name in self._loading:
            raise SchemeError("circular library import", make_list(
                [sym(p) if isinstance(p, str) else p for p in name]))
        self._loading.add(name)
        try:
            self.runtime.load_file(path, self.runtime.env)
        finally:
            self._loading.discard(name)
        lib = self.libraries.get(name)
        if lib is None:
            raise SchemeError("file did not define the library", MString(str(path)))
        return lib

    def _library_file(self, name):
        rel = os.path.join(*[str(p) for p in name])
        dirs = list(self.search_path)
        current = self.runtime.current_dir()
        if current not in dirs:
            dirs.insert(0, current)
        for d in dirs:
            for ext in (".sld", ".scm"):
                p = Path(d) / (rel + ext)
                if p.is_file():
                    return p
        return None

    # --- import sets ---------------------------------------------------------------------

    def resolve_import_set(self, spec):
        """An import set -> dict Symbol -> binding."""
        spec = strip_syntax(spec)
        if isinstance(spec, Pair) and isinstance(spec.car, Symbol) \
                and spec.car.name in ("only", "except", "prefix", "rename") \
                and isinstance(spec.cdr, Pair):
            kind = spec.car.name
            inner = self.resolve_import_set(spec.cdr.car)
            args = form_list(spec.cdr.cdr, kind)
            if kind == "only":
                out = {}
                for a in args:
                    if a not in inner:
                        raise syntax_error("only: name not exported", a)
                    out[a] = inner[a]
                return out
            if kind == "except":
                out = dict(inner)
                for a in args:
                    if a not in out:
                        raise syntax_error("except: name not exported", a)
                    del out[a]
                return out
            if kind == "prefix":
                if len(args) != 1 or not isinstance(args[0], Symbol):
                    raise syntax_error("bad prefix import set", spec)
                return {sym(args[0].name + k.name): v for k, v in inner.items()}
            out = dict(inner)
            for pair in args:
                old, new = form_list(pair, "rename")
                if old not in out:
                    raise syntax_error("rename: name not exported", old)
                out[new] = out.pop(old)
            return out
        return dict(self.find(library_name(spec)).exports)

    def import_into(self, env, spec):
        for name, b in self.resolve_import_set(spec).items():
            import_binding(env, name, b)


def import_binding(env, name, b):
    if isinstance(b, Cell):
        env.syntax.pop(name, None)
        env.cells[name] = b
        env.imported.add(name)
    else:
        env.syntax[name] = b
        env.imported.discard(name)


# --- cond-expand requirements --------------------------------------------------------------

def requirement_holds(exp, req):
    req = strip_syntax(req)
    if isinstance(req, Symbol):
        return req.name in FEATURES or req.name == "else"
    if isinstance(req, Pair) and isinstance(req.car, Symbol):
        kind = req.car.name
        args = form_list(req.cdr, "cond-expand requirement")
        if kind == "and":
            return all(requirement_holds(exp, a) for a in args)
        if kind == "or":
            return any(requirement_holds(exp, a) for a in args)
        if kind == "not":
            if len(args) != 1:
                raise syntax_error("bad (not ...) requirement", req)
            return not requirement_holds(exp, args[0])
        if kind == "library":
            if len(args) != 1:
                raise syntax_error("bad (library ...) requirement", req)
            return exp.runtime.libraries.exists(library_name(args[0]))
    raise syntax_error("bad cond-expand requirement", req)


def cond_expand_select(exp, form):
    """The forms of the first cond-expand clause whose requirement holds."""
    for clause in form_list(form.cdr, "cond-expand"):
        if not isinstance(clause, Pair):
            raise syntax_error("bad cond-expand clause", clause)
        if requirement_holds(exp, clause.car):
            return form_list(clause.cdr, "cond-expand clause")
    return []


# --- include ---------------------------------------------------------------------------------

def read_include(exp, form, fold_case):
    forms = []
    for f in form_list(form.cdr, "include"):
        f = strip_syntax(f)
        if not isinstance(f, MString):
            raise syntax_error("include: file name must be a string", form)
        path = Path(f.s)
        if not path.is_absolute():
            path = Path(exp.runtime.current_dir()) / path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise SchemeError("include: cannot read file", MString(str(path)),
                              MString(e.strerror or str(e)), kind="file")
        forms.extend(Reader(text, fold_case=fold_case).read_all())
    return forms


# --- syntactic forms ---------------------------------------------------------------------------

def _k(env):
    return lambda name: Alias(sym(name), env)


def m_cond_expand(exp, form, use, env):
    return Pair(_k(env)("begin"), make_list(cond_expand_select(exp, form)))


def m_include(exp, form, use, env):
    return Pair(_k(env)("begin"), make_list(read_include(exp, form, False)))


def m_include_ci(exp, form, use, env):
    return Pair(_k(env)("begin"), make_list(read_include(exp, form, True)))


def _import(exp, form, scope):
    if isinstance(scope, Scope):
        raise syntax_error("import is only allowed at top level", form)
    for spec in form_list(form.cdr, "import"):
        exp.runtime.libraries.import_into(scope, spec)
    return ast.Const(UNSPECIFIED)


def _define_library(exp, form, scope):
    if isinstance(scope, Scope):
        raise syntax_error("define-library is only allowed at top level", form)
    args = form_list(form.cdr, "define-library")
    if not args:
        raise syntax_error("bad define-library", form)
    rt = exp.runtime
    name = library_name(args[0])
    env = Environment("library " + " ".join(str(p) for p in name))
    exports = []        # (internal Symbol, external Symbol)

    def declare(decls):
        for d in decls:
            d = strip_syntax(d)
            if not isinstance(d, Pair) or not isinstance(d.car, Symbol):
                raise syntax_error("bad library declaration", d)
            kind = d.car.name
            if kind == "export":
                for spec in form_list(d.cdr, "export"):
                    if isinstance(spec, Symbol):
                        exports.append((spec, spec))
                    else:
                        parts = form_list(spec, "export spec")
                        if len(parts) != 3 or parts[0] is not sym("rename"):
                            raise syntax_error("bad export spec", spec)
                        exports.append((parts[1], parts[2]))
            elif kind == "import":
                for spec in form_list(d.cdr, "import"):
                    rt.libraries.import_into(env, spec)
            elif kind == "begin":
                for f in form_list(d.cdr, "begin"):
                    rt.eval(f, env)
            elif kind in ("include", "include-ci"):
                for f in read_include(exp, d, kind == "include-ci"):
                    rt.eval(f, env)
            elif kind == "include-library-declarations":
                declare(read_include(exp, d, False))
            elif kind == "cond-expand":
                declare(cond_expand_select(exp, d))
            else:
                raise syntax_error("unknown library declaration", d)

    declare(args[1:])
    table = {}
    for internal, external in exports:
        b = binding_of(env, internal)
        if b is None:
            b = env.cell(internal)      # exported but not (yet) defined
        table[external] = b
    rt.libraries.libraries[name] = Library(name, env, table)
    return ast.Const(UNSPECIFIED)


def _syntax_error(exp, form, scope):
    args = form_list(form.cdr, "syntax-error")
    if not args:
        raise syntax_error("syntax-error needs a message", form)
    msg = strip_syntax(args[0])
    text = msg.s if isinstance(msg, MString) else str(msg)
    raise SchemeError(text, *[strip_syntax(a) for a in args[1:]])


def install(system):
    system.syntax[sym("import")] = CoreForm("import", _import)
    system.syntax[sym("define-library")] = CoreForm("define-library", _define_library)
    system.syntax[sym("syntax-error")] = CoreForm("syntax-error", _syntax_error)
    for name, fn in [("cond-expand", m_cond_expand), ("include", m_include),
                     ("include-ci", m_include_ci)]:
        system.syntax[sym(name)] = Macro(name, fn, system)

