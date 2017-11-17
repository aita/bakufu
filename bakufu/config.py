import io
import re
from enum import IntEnum

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
    ID = 1
    STRING = 2
    NUMBER = 3
    EQUAL = 4
    SEMICOLON = 5
    COMMA = 6
    LEFT_BRACKET = 7
    RIGHT_BRACKET = 8
    EOF = 9


def scan_id(s, start):
    pos = start
    c = s[pos]
    if not c.isalpha() and c != "_":
        raise ParseError("Unexpected character '%c' while scanning key" % c)

    pos += 1
    while True:
        c = s[pos]
        if c in DELIMITER:
            return Token.ID, s[start:pos], pos
        elif c.isalpha() or c.isdigit() or c == "_":
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
    return Token.NUMBER, value, pos


def scan_string(s, pos):
    buf = io.StringIO()
    quote = s[pos]
    pos += 1
    while True:
        c = s[pos]
        if c == quote:
            return Token.STRING, buf.getvalue(), pos+1
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
            return Token.EOF, "", len(s)
        if s[pos] not in WS:
            break
        pos += 1

    c = s[pos]
    if c == "#":
        return scan(s, skip_comment(s, pos))
    elif c == "=":
        return Token.EQUAL, c, pos+1
    elif c == ";":
        return Token.SEMICOLON, c, pos+1
    elif c == "{":
        return Token.LEFT_BRACKET, c, pos+1
    elif c == "}":
        return Token.RIGHT_BRACKET, c, pos+1
    try:
        if c.isdigit() or c in "+-":
            return scan_number(s, pos)
        if c == "." and s[pos+1].isdigit():
            return scan_number(s, pos)
        if c.isalpha() or c == "_":
            return scan_id(s, pos)
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
        if tok == Token.EOF:
            if depth > 0:
                raise ParseError("Unclosed block")
            return data
        if tok == Token.RIGHT_BRACKET:
            if depth < 1:
                raise ParseError("Unexpected token %s" % tok)
            scanner.junk()
            return data

        key = expect(scanner, Token.ID, Token.STRING)
        tok, _ = scanner.peek()
        if tok == Token.EQUAL:
            scanner.junk()
            tok, value = scanner.next()
            if tok == Token.ID:
                if value in RESERVED:
                    value = RESERVED[value]
                _update(data, key, value)
            elif tok in (Token.NUMBER, Token.STRING):
                _update(data, key, value)
            else:
                raise ParseError("Unexpected token %s" % tok)
            expect(scanner, Token.SEMICOLON)
            continue

        keys = [key]
        while True:
            tok, subkey = scanner.next()
            if tok in (Token.ID, Token.STRING):
                keys.append(subkey)
                continue
            elif tok == Token.LEFT_BRACKET:
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
