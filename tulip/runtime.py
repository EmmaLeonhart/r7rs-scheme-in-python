"""A runtime: the system environment with every built-in, the standard
libraries over it, a user (interaction) environment, the library manager and
the machine. ``Runtime().eval_string("(+ 1 2)")`` returns 3."""

from __future__ import annotations

import os
from pathlib import Path

from . import expander, interp, libraries, syntax_rules
from . import (control, prims_data, prims_misc, prims_numbers,  # noqa: F401
               prims_ports, prims_system)
from .reader import Reader
from .registry import PRIMITIVES
from .types import EOF, UNSPECIFIED, Environment, make_list, sym

PRELUDE = Path(__file__).with_name("prelude.scm")

_HELPERS = ["memv", "cons", "list", "append", "list->vector", "%make-promise",
            "%case-lambda", "%make-record-type", "%record-constructor",
            "%record-predicate", "%record-accessor", "%record-modifier"]


class Runtime:
    def __init__(self, argv=()):
        self.argv = list(argv)
        self.machine = interp.Machine()
        self.machine.runtime = self
        self._dirs = [os.getcwd()]

        self.system = Environment("system")
        for name, proc in PRIMITIVES.items():
            self.system.define(name, proc)
        expander.install(self.system, {n: PRIMITIVES[n] for n in _HELPERS})
        syntax_rules.install(self.system)
        libraries.install(self.system)
        self.libraries = libraries.LibraryManager(self)
        self.eval_string(PRELUDE.read_text(encoding="utf-8"), self.system)

        self.libraries.define_standard(self.system)
        self.env = self.new_environment(
            [make_list([sym(p) for p in name])
             for name in libraries.STANDARD_LIBRARIES])
        # programs and the REPL may also define libraries
        name = sym("define-library")
        self.env.syntax[name] = self.system.syntax[name]

    # --- environments ------------------------------------------------------------

    def new_environment(self, import_specs, name="user"):
        env = Environment(name)
        for spec in import_specs:
            self.libraries.import_into(env, spec)
        return env

    def expander_for(self, env):
        if env.expander is None:
            env.expander = expander.Expander(env, self)
        return env.expander

    # --- evaluation ----------------------------------------------------------------

    def compile(self, datum, env=None):
        env = self.env if env is None else env
        return interp.compile_node(self.expander_for(env).expand_toplevel(datum))

    def eval(self, datum, env=None):
        """Expand, compile and run one top-level form."""
        return self.machine.run(self.compile(datum, env))

    def eval_string(self, text, env=None):
        """Evaluate every form in ``text``; return the last value."""
        reader = Reader(text)
        result = UNSPECIFIED
        while True:
            datum = reader.read()
            if datum is EOF:
                return result
            result = self.eval(datum, env)

    def load_file(self, path, env=None):
        path = Path(path).resolve()
        self._dirs.append(str(path.parent))
        try:
            return self.eval_string(path.read_text(encoding="utf-8"), env)
        finally:
            self._dirs.pop()

    load = load_file

    def current_dir(self):
        return self._dirs[-1]

    def apply(self, proc, args):
        return self.machine.apply(proc, list(args))
