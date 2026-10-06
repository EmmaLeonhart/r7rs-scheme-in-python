"""Port procedures (R7RS 6.13) and the file procedures of (scheme file).

The current input, output and error ports are parameter objects. Procedures
whose port argument is optional are defined in prelude.scm on top of the
``%``-prefixed primitives here, which always take the port explicitly.
"""

from __future__ import annotations

import os
import sys

from . import ports
from .control import Parameter
from .printer import display_string, write_string
from .registry import PRIMITIVES, prim
from .types import (EOF, Char, MString, Primitive, SchemeError, UNSPECIFIED)

_identity = Primitive(lambda x: x, "identity", 1)

STDIN = ports.ConsoleInputPort()
STDOUT = ports.console_output("console-output-port", lambda: sys.stdout)
STDERR = ports.console_output("console-error-port", lambda: sys.stderr)

PRIMITIVES["current-input-port"] = Parameter(STDIN, _identity)
PRIMITIVES["current-output-port"] = Parameter(STDOUT, _identity)
PRIMITIVES["current-error-port"] = Parameter(STDERR, _identity)


def _port(p, who, kind):
    ok = isinstance(p, ports.Port) and {
        "text-in": p.input and p.textual, "text-out": p.output and p.textual,
        "bin-in": p.input and p.binary, "bin-out": p.output and p.binary,
        "out": p.output, "in": p.input, "any": True}[kind]
    if not ok:
        raise SchemeError("%s: wrong kind of port" % who, p)
    return p


def _string(s, who):
    if type(s) is not MString:
        raise SchemeError("%s: not a string" % who, s)
    return s.s


def _k(k, who):
    if type(k) is not int or k < 0:
        raise SchemeError("%s: not a valid count" % who, k)
    return k


def _range(n, start, end, who):
    """start/end may be #f (from the prelude wrappers) when not given."""
    if start is None or start is False:
        start = 0
    if end is None or end is False:
        end = n
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= n:
        raise SchemeError("%s: bad range" % who, start, end)
    return start, end


# --- predicates and closing ----------------------------------------------------------

@prim("port?", 1)
def port_p(x):
    return isinstance(x, ports.Port)


@prim("input-port?", 1)
def input_port_p(x):
    return isinstance(x, ports.Port) and x.input


@prim("output-port?", 1)
def output_port_p(x):
    return isinstance(x, ports.Port) and x.output


@prim("textual-port?", 1)
def textual_port_p(x):
    return isinstance(x, ports.Port) and x.textual


@prim("binary-port?", 1)
def binary_port_p(x):
    return isinstance(x, ports.Port) and x.binary


@prim("input-port-open?", 1)
def input_port_open(p):
    return _port(p, "input-port-open?", "in").open


@prim("output-port-open?", 1)
def output_port_open(p):
    return _port(p, "output-port-open?", "out").open


@prim("close-port", 1)
def close_port(p):
    _port(p, "close-port", "any").close()
    return UNSPECIFIED


@prim("close-input-port", 1)
def close_input_port(p):
    _port(p, "close-input-port", "in").close()
    return UNSPECIFIED


@prim("close-output-port", 1)
def close_output_port(p):
    _port(p, "close-output-port", "out").close()
    return UNSPECIFIED


# --- opening -------------------------------------------------------------------------

@prim("open-input-string", 1)
def open_input_string(s):
    p = ports.TextInputPort(_string(s, "open-input-string"))
    p.name = "string-input-port"
    return p


@prim("open-output-string", 0)
def open_output_string():
    return ports.StringOutputPort()


@prim("get-output-string", 1)
def get_output_string(p):
    if not isinstance(p, ports.StringOutputPort):
        raise SchemeError("get-output-string: not a string output port", p)
    return MString(p.getvalue())


@prim("open-input-bytevector", 1)
def open_input_bytevector(b):
    if type(b) is not bytearray:
        raise SchemeError("open-input-bytevector: not a bytevector", b)
    return ports.BinaryInputPort(b)


@prim("open-output-bytevector", 0)
def open_output_bytevector():
    return ports.BinaryOutputPort()


@prim("get-output-bytevector", 1)
def get_output_bytevector(p):
    if not isinstance(p, ports.BinaryOutputPort) or p.stream is not None:
        raise SchemeError("get-output-bytevector: not a bytevector output port", p)
    return bytearray(p.data)


@prim("open-input-file", 1)
def open_input_file(path):
    return ports.open_input_file(_string(path, "open-input-file"))


@prim("open-binary-input-file", 1)
def open_binary_input_file(path):
    return ports.open_binary_input_file(_string(path, "open-binary-input-file"))


@prim("open-output-file", 1)
def open_output_file(path):
    return ports.open_output_file(_string(path, "open-output-file"))


@prim("open-binary-output-file", 1)
def open_binary_output_file(path):
    return ports.open_binary_output_file(_string(path, "open-binary-output-file"))


@prim("file-exists?", 1)
def file_exists(path):
    return os.path.exists(_string(path, "file-exists?"))


@prim("delete-file", 1)
def delete_file(path):
    p = _string(path, "delete-file")
    try:
        os.remove(p)
    except OSError as e:
        raise ports.file_error("delete-file", p, e)
    return UNSPECIFIED


# --- input -----------------------------------------------------------------------------

@prim("eof-object", 0)
def eof_object():
    return EOF


@prim("eof-object?", 1)
def eof_object_p(x):
    return x is EOF


def _char_or_eof(c):
    return EOF if c is EOF else Char(c)


@prim("%read-char", 1)
def read_char(p):
    return _char_or_eof(_port(p, "read-char", "text-in").read_char())


@prim("%peek-char", 1)
def peek_char(p):
    return _char_or_eof(_port(p, "peek-char", "text-in").peek_char())


@prim("%char-ready?", 1)
def char_ready(p):
    return _port(p, "char-ready?", "text-in").char_ready()


@prim("%read-line", 1)
def read_line(p):
    line = _port(p, "read-line", "text-in").read_line()
    return EOF if line is EOF else MString(line)


@prim("%read-string", 2)
def read_string(k, p):
    s = _port(p, "read-string", "text-in").read_string(_k(k, "read-string"))
    return EOF if s is EOF else MString(s)


@prim("%read", 1)
def read(p):
    return _port(p, "read", "text-in").read_datum()


@prim("%read-u8", 1)
def read_u8(p):
    return _port(p, "read-u8", "bin-in").read_u8()


@prim("%peek-u8", 1)
def peek_u8(p):
    return _port(p, "peek-u8", "bin-in").peek_u8()


@prim("%u8-ready?", 1)
def u8_ready(p):
    _port(p, "u8-ready?", "bin-in").check_open("u8-ready?")
    return True


@prim("%read-bytevector", 2)
def read_bytevector(k, p):
    return _port(p, "read-bytevector", "bin-in").read_bytes(_k(k, "read-bytevector"))


@prim("%read-bytevector!", 4)
def read_bytevector_bang(bv, p, start, end):
    if type(bv) is not bytearray:
        raise SchemeError("read-bytevector!: not a bytevector", bv)
    start, end = _range(len(bv), start, end, "read-bytevector!")
    if start == end:
        return 0
    chunk = _port(p, "read-bytevector!", "bin-in").read_bytes(end - start)
    if chunk is EOF:
        return EOF
    bv[start:start + len(chunk)] = chunk
    return len(chunk)


# --- output ------------------------------------------------------------------------------

@prim("%write", 2)
def write(obj, p):
    _port(p, "write", "text-out").write(write_string(obj))
    return UNSPECIFIED


@prim("%write-shared", 2)
def write_shared(obj, p):
    _port(p, "write-shared", "text-out").write(write_string(obj, "shared"))
    return UNSPECIFIED


@prim("%write-simple", 2)
def write_simple(obj, p):
    _port(p, "write-simple", "text-out").write(write_string(obj, "simple"))
    return UNSPECIFIED


@prim("%display", 2)
def display(obj, p):
    _port(p, "display", "text-out").write(display_string(obj))
    return UNSPECIFIED


@prim("%newline", 1)
def newline(p):
    _port(p, "newline", "text-out").write("\n")
    return UNSPECIFIED


@prim("%write-char", 2)
def write_char(c, p):
    if type(c) is not Char:
        raise SchemeError("write-char: not a character", c)
    _port(p, "write-char", "text-out").write(c.ch)
    return UNSPECIFIED


@prim("%write-string", 4)
def write_string_(s, p, start, end):
    text = _string(s, "write-string")
    start, end = _range(len(text), start, end, "write-string")
    _port(p, "write-string", "text-out").write(text[start:end])
    return UNSPECIFIED


@prim("%write-u8", 2)
def write_u8(b, p):
    if type(b) is not int or not 0 <= b <= 255:
        raise SchemeError("write-u8: not a byte", b)
    _port(p, "write-u8", "bin-out").write_bytes(bytes([b]))
    return UNSPECIFIED


@prim("%write-bytevector", 4)
def write_bytevector(bv, p, start, end):
    if type(bv) is not bytearray:
        raise SchemeError("write-bytevector: not a bytevector", bv)
    start, end = _range(len(bv), start, end, "write-bytevector")
    _port(p, "write-bytevector", "bin-out").write_bytes(bv[start:end])
    return UNSPECIFIED


@prim("%flush-output-port", 1)
def flush_output_port(p):
    _port(p, "flush-output-port", "out").flush()
    return UNSPECIFIED
