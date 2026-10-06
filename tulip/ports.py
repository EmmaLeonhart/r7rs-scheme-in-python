"""Ports (R7RS 6.13): textual and binary, input and output.

Input ports keep a buffer and a position. String and bytevector ports hold all
their data up front; file ports read the whole file when opened; the console
input port fills its buffer a line at a time, so ``read`` can wait for the
rest of a datum that spans lines.
"""

from __future__ import annotations

import sys

from .types import EOF, SchemeError


class Port:
    textual = False
    binary = False
    input = False
    output = False
    name = "port"

    def __init__(self):
        self.open = True

    def close(self):
        self.open = False

    def check_open(self, who):
        if not self.open:
            raise SchemeError("%s: port is closed" % who, self)

    def __repr__(self):
        return "#<%s>" % self.name


# --- textual input ------------------------------------------------------------------

class TextInputPort(Port):
    textual = True
    input = True
    name = "input-port"

    def __init__(self, text="", source=None):
        super().__init__()
        self.buffer = text
        self.pos = 0
        self.source = source        # callable returning more text, "" at EOF
        self.fold_case = False

    def fill(self):
        """Read more text into the buffer. False at end of input."""
        if self.source is None:
            return False
        more = self.source()
        if not more:
            self.source = None
            return False
        self.buffer = self.buffer[self.pos:] + more
        self.pos = 0
        return True

    def _available(self, n=1):
        while len(self.buffer) - self.pos < n:
            if not self.fill():
                return False
        return True

    def read_char(self):
        self.check_open("read-char")
        if not self._available():
            return EOF
        c = self.buffer[self.pos]
        self.pos += 1
        return c

    def peek_char(self):
        self.check_open("peek-char")
        if not self._available():
            return EOF
        return self.buffer[self.pos]

    def char_ready(self):
        self.check_open("char-ready?")
        return self.pos < len(self.buffer) or self.source is None

    def read_line(self):
        self.check_open("read-line")
        while True:
            i = self._line_end()
            if i is not None:
                line = self.buffer[self.pos:i]
                skip = 2 if self.buffer.startswith("\r\n", i) else 1
                self.pos = i + skip
                return line
            if not self.fill():
                if self.pos >= len(self.buffer):
                    return EOF
                line = self.buffer[self.pos:]
                self.pos = len(self.buffer)
                return line

    def _line_end(self):
        buf, pos = self.buffer, self.pos
        n = buf.find("\n", pos)
        r = buf.find("\r", pos)
        if r >= 0 and (n < 0 or r < n):
            if r + 1 == len(buf) and self.source is not None:
                return None        # might be the first half of \r\n
            return r
        return n if n >= 0 else None

    def read_string(self, k):
        self.check_open("read-string")
        self._available(k)
        if self.pos >= len(self.buffer):
            return EOF
        s = self.buffer[self.pos:self.pos + k]
        self.pos += len(s)
        return s

    def read_datum(self):
        from .reader import Reader, ReadError
        self.check_open("read")
        while True:
            text = self.buffer[self.pos:]
            reader = Reader(text, fold_case=self.fold_case)
            try:
                obj = reader.read()
            except ReadError as e:
                if "end of input" in str(e) and self.fill():
                    continue
                raise
            if obj is EOF or reader.pos >= len(text):
                # nothing yet, or a token that may continue: try for more
                if self.fill():
                    continue
            self.pos += reader.pos
            self.fold_case = reader.fold_case
            return obj


class ConsoleInputPort(TextInputPort):
    name = "console-input-port"

    def __init__(self):
        super().__init__("", self._readline)

    def _readline(self):
        return sys.stdin.readline()

    def close(self):
        pass


def open_input_file(path):
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as e:
        raise file_error("open-input-file", path, e)
    port = TextInputPort(text)
    port.name = "file-input-port"
    return port


# --- binary input ----------------------------------------------------------------------

class BinaryInputPort(Port):
    binary = True
    input = True
    name = "binary-input-port"

    def __init__(self, data=b""):
        super().__init__()
        self.data = bytes(data)
        self.pos = 0

    def read_u8(self):
        self.check_open("read-u8")
        if self.pos >= len(self.data):
            return EOF
        b = self.data[self.pos]
        self.pos += 1
        return b

    def peek_u8(self):
        self.check_open("peek-u8")
        if self.pos >= len(self.data):
            return EOF
        return self.data[self.pos]

    def read_bytes(self, k):
        self.check_open("read-bytevector")
        if self.pos >= len(self.data) and k > 0:
            return EOF
        chunk = self.data[self.pos:self.pos + k]
        self.pos += len(chunk)
        return bytearray(chunk)


def open_binary_input_file(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise file_error("open-binary-input-file", path, e)
    port = BinaryInputPort(data)
    port.name = "binary-file-input-port"
    return port


# --- textual output ----------------------------------------------------------------------

class TextOutputPort(Port):
    textual = True
    output = True
    name = "output-port"

    def __init__(self, stream=None, getter=None):
        super().__init__()
        self.stream = stream
        self.getter = getter        # for the console: look up sys.stdout late

    def _stream(self):
        return self.getter() if self.getter is not None else self.stream

    def write(self, text):
        self.check_open("write")
        self._stream().write(text)

    def flush(self):
        self._stream().flush()

    def close(self):
        if self.open and self.stream is not None:
            self.stream.close()
        self.open = False


class StringOutputPort(TextOutputPort):
    name = "string-output-port"

    def __init__(self):
        super().__init__()
        self.parts = []

    def write(self, text):
        self.check_open("write")
        self.parts.append(text)

    def flush(self):
        pass

    def close(self):
        self.open = False

    def getvalue(self):
        return "".join(self.parts)


def console_output(name, getter):
    port = TextOutputPort(getter=getter)
    port.name = name
    port.close = lambda: None      # closing the console does nothing
    return port


def open_output_file(path):
    try:
        f = open(path, "w", encoding="utf-8", newline="")
    except OSError as e:
        raise file_error("open-output-file", path, e)
    port = TextOutputPort(f)
    port.name = "file-output-port"
    return port


# --- binary output ---------------------------------------------------------------------

class BinaryOutputPort(Port):
    binary = True
    output = True
    name = "binary-output-port"

    def __init__(self, stream=None):
        super().__init__()
        self.stream = stream
        self.data = bytearray()

    def write_bytes(self, b):
        self.check_open("write-u8")
        if self.stream is not None:
            self.stream.write(bytes(b))
        else:
            self.data += b

    def flush(self):
        if self.stream is not None:
            self.stream.flush()

    def close(self):
        if self.open and self.stream is not None:
            self.stream.close()
        self.open = False


def open_binary_output_file(path):
    try:
        f = open(path, "wb")
    except OSError as e:
        raise file_error("open-binary-output-file", path, e)
    port = BinaryOutputPort(f)
    port.name = "binary-file-output-port"
    return port


def file_error(who, path, e):
    from .types import MString
    return SchemeError("%s: %s" % (who, e.strerror or e), MString(str(path)),
                       kind="file")
