"""Ports. Stage 1 has textual output only; stage 3 adds the rest."""

from __future__ import annotations

import sys


class Port:
    textual = True
    binary = False
    input = False
    output = False

    def __init__(self):
        self.open = True

    def close(self):
        self.open = False


class TextOutputPort(Port):
    output = True

    def __init__(self, stream=None):
        super().__init__()
        self.stream = stream

    def write(self, text):
        stream = self.stream if self.stream is not None else sys.stdout
        stream.write(text)

    def flush(self):
        stream = self.stream if self.stream is not None else sys.stdout
        stream.flush()

    def __repr__(self):
        return "#<output-port>"


class StringOutputPort(TextOutputPort):
    def __init__(self):
        super().__init__()
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    def flush(self):
        pass

    def getvalue(self):
        return "".join(self.parts)

    def __repr__(self):
        return "#<string-output-port>"
