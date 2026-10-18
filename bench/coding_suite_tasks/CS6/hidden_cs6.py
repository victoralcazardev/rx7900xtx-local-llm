"""Hidden acceptance test for CS6: runs from a directory outside the worktree."""
import unittest

import tomli


class AcceptanceCS6(unittest.TestCase):
    def check(self, doc, msg):
        with self.assertRaises(tomli.TOMLDecodeError) as cm:
            tomli.loads(doc)
        self.assertEqual(cm.exception.msg, msg)

    def test_duplicate_table_message(self):
        self.check("[t]\nk = 1\n[t]\n", "Cannot declare table [t] twice")
        self.check("[a.b]\n[a.b]\n", "Cannot declare table [a.b] twice")


if __name__ == "__main__":
    unittest.main()
