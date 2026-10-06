"""A runtime: a global environment with the standard bindings, the expander
and the machine. ``Runtime().eval_string("(+ 1 2)")`` returns 3."""

from __future__ import annotations

from pathlib import Path

from . import expander, interp
from . import prims_data, prims_misc, prims_numbers  # noqa: F401 (register)
from .reader import Reader
from .registry import PRIMITIVES
from .types import EOF, UNSPECIFIED, Environment

PRELUDE = Path(__file__).with_name("prelude.scm")

_HELPERS = ["memv", "cons", "list", "append", "list->vector", "%make-promise",
            "%case-lambda", "%make-record-type", "%record-constructor",
            "%record-predicate", "%record-accessor", "%record-modifier"]


class Runtime:
    def __init__(self):
        self.env = Environment("user")
        for name, proc in PRIMITIVES.items():
            self.env.define(name, proc)
        expander.install(self.env, {n: PRIMITIVES[n] for n in _HELPERS})
        self.expander = expander.Expander(self.env)
        self.machine = interp.Machine()
        self.eval_string(PRELUDE.read_text(encoding="utf-8"))

    def eval(self, datum):
        """Expand, compile and run one top-level form."""
        node = self.expander.expand_toplevel(datum)
        return self.machine.run(interp.compile_node(node))

    def eval_string(self, text):
        """Evaluate every form in ``text``; return the last value."""
        reader = Reader(text)
        result = UNSPECIFIED
        while True:
            datum = reader.read()
            if datum is EOF:
                return result
            result = self.eval(datum)

    def load(self, path):
        return self.eval_string(Path(path).read_text(encoding="utf-8"))

    def apply(self, proc, args):
        return self.machine.apply(proc, list(args))
