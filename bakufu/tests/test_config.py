import unittest
from bakufu.config import Token


class TestConfigScanner(unittest.TestCase):
    def _callFUT(self, text):
        from bakufu import config
        return config.scan(text, 0)

    def test_number(self):
        self.assertEqual(self._callFUT("+0;"), (Token.number, 0, 2))
        self.assertEqual(self._callFUT("-123;"), (Token.number, -123, 4))
        self.assertEqual(self._callFUT(".5e4;"), (Token.number, 5000.0, 4))
        self.assertEqual(self._callFUT("10E-2;"), (Token.number, 0.1, 5))


class TestConfigLoad(unittest.TestCase):
    def _callFUT(self, text):
        from bakufu import config
        return config.loads(text)

    def test_pair(self):
        pair = self._callFUT("key=value;")
        self.assertEqual(pair, {"key": "value"})

    def test_section(self):
        result = self._callFUT("""
            section {
                x = 1;
                y = "hello";
                z = 'world';
            }
        """)
        self.assertEqual(result, {
            "section": {
                "x": 1,
                "y": "hello",
                "z": "world",
            }
        })

        result = self._callFUT("""
            a {
                x = 1;
                y = 2;
                z {
                    m = 1;
                    n = 2;
                }
            }
            a z {
                m = 1;
                n = 1;
            }
        """)
        self.assertEqual(result, {
            "a": {
                "x": 1,
                "y": 2,
                "z": {
                    "m": 1,
                    "n": 1,
                }
            },
        })
