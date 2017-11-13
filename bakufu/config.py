import io
import re
from enum import IntEnum, auto

from bakufu import logger


WS = " \t\r\n"
DELIMITER = WS + "=;{}#"

COMMENT = re.compile(r"#[^\n\r]*[\n\r]")

RESERVED = {
    "true": True,
    "false": False,
    "yes": True,
    "no": False,
    "on": True,
    "off": False,
}

ESCAPES = {
    "\\": "\\",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "t": "\t",
    "r": "\r",
    "n": "\n",
}


class ParseError(Exception):
    pass


class Token(IntEnum):
    barekey = auto()
    string = auto()
    number = auto()
    equal = auto()
    semicolon = auto()
    left_bracket = auto()
    right_bracket = auto()
    eof = auto()


def scan_barekey(s, start):
    pos = start
    firstchar = s[pos]
    if not firstchar.isalpha() and firstchar != "_":
        raise ParseError("Unexpected character '%c' while scanning key" % firstchar)

    pos += 1
    while True:
        c = s[pos]
        if c in DELIMITER:
            return Token.barekey, s[start:pos], pos
        elif c.isalpha() or c.isdigit():
            pos += 1
        else:
            raise ParseError("Unexpected character '%c' while scanning key" % c)


def scan_number(s, start):
    pos = start
    # sign
    if s[pos] in "+-":
        pos += 1
    # int
    if s[pos] == "0":
        pos += 1
    else:
        while s[pos].isdigit():
            pos += 1
    # frac
    if s[pos] == ".":
        pos += 1
        while s[pos].isdigit():
            pos += 1
    # exp
    if s[pos] in "eE":
        pos += 1
        if s[pos] in "+-":
            pos += 1
        while s[pos].isdigit():
            pos += 1

    if s[pos] not in DELIMITER:
        raise ParseError("Unpexected character '%c' while scanning number" % s[pos])

    value = s[start:pos]
    try:
        value = int(value)
    except ValueError:
        value = float(value)
    return Token.number, value, pos


def scan_string(s, pos):
    buf = io.StringIO()
    quote = s[pos]
    pos += 1
    while True:
        c = s[pos]
        if c == quote:
            return Token.string, buf.getvalue(), pos+1
        elif c in "\r\n":
            raise ParseError("EOL while scanning string")
        elif c == "\\":
            pos += 1
            escaped = s[pos]
            if escaped in ESCAPES:
                c = ESCAPES[escaped]
            else:
                c = escaped
        buf.write(c)
        pos += 1


def _skip(s, p, regex):
    m = regex.match(s, p)
    if m:
        return m.end()
    return p


def skip_comment(s, p):
    return _skip(s, p, COMMENT)


def scan(s, pos):
    while True:
        if len(s) <= pos:
            return Token.eof, "", len(s)
        if s[pos] not in WS:
            break
        pos += 1

    c = s[pos]
    if c == "#":
        return scanone(s, skip_comment(s, pos))
    elif c == "=":
        return Token.equal, c, pos+1
    elif c == ";":
        return Token.semicolon, c, pos+1
    elif c == "{":
        return Token.left_bracket, c, pos+1
    elif c == "}":
        return Token.right_bracket, c, pos+1
    try:
        if c.isdigit() or c in "+-":
            return scan_number(s, pos)
        if c == "." and s[pos+1].isdigit():
            return scan_number(s, pos)
        if c.isalpha() or c == "_":
            return scan_barekey(s, pos)
        if c in "'\"":
            return scan_string(s, pos)
    except IndexError:
        raise ParseError("Unexpected EOF")

    raise ParseError("Unexpected character '%c'" % c)


class Scanner:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def _peek(self):
        return scan(self.data, self.pos)

    def peek(self):
        one = self._peek()
        tok, value, _ = one
        return tok, value

    def next(self):
        one = self._peek()
        tok, value, self.pos = one
        return tok, value

    def junk(self):
        self.next()


def expect(scanner, *expected):
    tok, value = scanner.next()
    if tok not in expected:
        raise ParseError("Unexpected token %s" % tok)
    return value


def _update(data, key, value):
    if key in data:
        logger.warning("duplicated entry '%s'" % key)
    data[key] = value


def _update_section(data, keys, value):
    subdata = data
    for subkey in keys[:-1]:
        subdata = subdata.setdefault(subkey, {})
    lastkey = keys[-1]
    if lastkey not in subdata:
        subdata[lastkey] = value
    else:
        for k, v in value.items():
            _update(subdata[lastkey], k, v)


def parse(scanner, depth=0):
    data = {}
    while True:
        tok, _ = scanner.peek()
        if tok == Token.eof:
            if depth > 0:
                raise ParseError("Unclosed block")
            return data
        if tok == Token.right_bracket:
            if depth < 1:
                raise ParseError("Unexpected token %s" % tok)
            scanner.junk()
            return data

        key = expect(scanner, Token.barekey, Token.string)
        tok, _ = scanner.peek()
        if tok == Token.equal:
            scanner.junk()
            tok, value = scanner.next()
            if tok == Token.barekey:
                if value in RESERVED:
                    value = RESERVED[value]
                _update(data, key, value)
            elif tok in (Token.number, Token.string):
                _update(data, key, value)
            else:
                raise ParseError("Unexpected token %s" % tok)
            expect(scanner, Token.semicolon)
            continue

        keys = [key]
        while True:
            tok, subkey = scanner.next()
            if tok in (Token.barekey, Token.string):
                keys.append(subkey)
                continue
            elif tok == Token.left_bracket:
                value = parse(scanner, depth+1)
                _update_section(data, keys, value)
                break
            else:
                raise ParseError("Unexpected token %s" % tok)


def loads(s):
    scanner = Scanner(s)
    return parse(scanner)


def load(fp):
    return loads(fp.read())
