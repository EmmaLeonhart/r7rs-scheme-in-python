import unittest
from fractions import Fraction

from helpers import SchemeError  # noqa: F401  (sets sys.path)
from tulip.printer import write_string
from tulip.reader import Reader, read_all, read_one
from tulip.types import EOF, NIL, Char, MString, Pair, Symbol


def rw(text):
    """Read one datum and write it back."""
    return write_string(read_one(text))


class ReaderTests(unittest.TestCase):
    def test_atoms(self):
        self.assertEqual(read_one("42"), 42)
        self.assertEqual(read_one("-17"), -17)
        self.assertEqual(read_one("1/3"), Fraction(1, 3))
        self.assertEqual(read_one("4/2"), 2)
        self.assertIs(type(read_one("4/2")), int)
        self.assertEqual(read_one("1.5"), 1.5)
        self.assertEqual(read_one(".5"), 0.5)
        self.assertEqual(read_one("1e3"), 1000.0)
        self.assertEqual(read_one("1."), 1.0)
        self.assertIs(read_one("#t"), True)
        self.assertIs(read_one("#false"), False)
        self.assertIs(read_one("foo"), Symbol.intern("foo"))
        self.assertIs(read_one("..."), Symbol.intern("..."))
        self.assertIs(read_one("+"), Symbol.intern("+"))
        self.assertIs(read_one("-"), Symbol.intern("-"))
        self.assertIs(read_one("->x"), Symbol.intern("->x"))

    def test_number_prefixes(self):
        self.assertEqual(read_one("#xff"), 255)
        self.assertEqual(read_one("#b-101"), -5)
        self.assertEqual(read_one("#o17"), 15)
        self.assertEqual(read_one("#e1.5"), Fraction(3, 2))
        self.assertEqual(read_one("#e1e2"), 100)
        self.assertEqual(read_one("#i1/4"), 0.25)
        self.assertEqual(read_one("#x#e10"), 16)
        self.assertEqual(read_one("#e#x10"), 16)
        self.assertEqual(rw("+inf.0"), "+inf.0")
        self.assertEqual(rw("-inf.0"), "-inf.0")
        self.assertEqual(rw("+nan.0"), "+nan.0")

    def test_complex_rejected(self):
        with self.assertRaises(SchemeError):
            read_one("1+2i")

    def test_lists(self):
        self.assertEqual(rw("(1 2 3)"), "(1 2 3)")
        self.assertEqual(rw("(1 . 2)"), "(1 . 2)")
        self.assertEqual(rw("(1 2 . 3)"), "(1 2 . 3)")
        self.assertEqual(rw("(1 . (2 3))"), "(1 2 3)")
        self.assertIs(read_one("()"), NIL)
        self.assertEqual(rw("[a b]"), "(a b)")
        self.assertEqual(rw("'x"), "'x")
        self.assertEqual(rw("`(a ,b ,@c)"), "`(a ,b ,@c)")

    def test_vectors_and_bytevectors(self):
        self.assertEqual(read_one("#(1 2)"), [1, 2])
        self.assertEqual(read_one("#u8(1 255)"), bytearray([1, 255]))
        with self.assertRaises(SchemeError):
            read_one("#u8(256)")

    def test_chars(self):
        self.assertEqual(read_one(r"#\a"), Char("a"))
        self.assertEqual(read_one(r"#\space"), Char(" "))
        self.assertEqual(read_one(r"#\newline"), Char("\n"))
        self.assertEqual(read_one(r"#\x41"), Char("A"))
        self.assertEqual(read_one(r"#\x"), Char("x"))
        self.assertEqual(read_one(r"#\("), Char("("))
        self.assertEqual(read_one(r"#\λ"), Char("λ"))
        self.assertEqual(rw(r"(#\a #\b)"), r"(#\a #\b)")

    def test_strings(self):
        s = read_one(r'"a\nb\t\"q\"\\ \x41;"')
        self.assertIsInstance(s, MString)
        self.assertEqual(s.s, 'a\nb\t"q"\\ A')
        s = read_one('"line one \\\n    continued"')
        self.assertEqual(s.s, "line one continued")

    def test_bar_symbols(self):
        self.assertEqual(read_one("|hello world|").name, "hello world")
        self.assertEqual(rw("|hello world|"), "|hello world|")
        self.assertEqual(read_one(r"|a\x41;|").name, "aA")

    def test_comments(self):
        self.assertEqual(read_all("1 ; comment\n 2"), [1, 2])
        self.assertEqual(read_all("1 #| block #| nested |# |# 2"), [1, 2])
        self.assertEqual(read_all("1 #;(ignored datum) 2"), [1, 2])
        self.assertEqual(rw("(a #;b c)"), "(a c)")

    def test_fold_case(self):
        self.assertIs(read_one("#!fold-case FOO"), Symbol.intern("foo"))
        r = Reader("#!fold-case A #!no-fold-case B")
        self.assertEqual([r.read().name, r.read().name], ["a", "B"])

    def test_datum_labels(self):
        x = read_one("#0=(a . #0#)")
        self.assertIsInstance(x, Pair)
        self.assertIs(x.cdr, x)
        y = read_one("(#1=(x) #1#)")
        self.assertIs(y.car, y.cdr.car)

    def test_eof_and_errors(self):
        self.assertIs(read_one("   "), EOF)
        for bad in ["(1 2", ")", "(1 . )", "(. 1)", '"abc', "#\\nosuchname",
                    "#|", "#q"]:
            with self.subTest(bad=bad):
                with self.assertRaises(SchemeError):
                    read_all(bad)


if __name__ == "__main__":
    unittest.main()
