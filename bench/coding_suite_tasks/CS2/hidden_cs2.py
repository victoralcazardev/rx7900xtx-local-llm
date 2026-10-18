"""Hidden scoring test for CS2: copied to the worktree root only after the episode."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent


class HiddenCS2(unittest.TestCase):
    def test_stub_docs_and_export(self):
        stub = ast.parse((ROOT / "more_itertools/more.pyi").read_text())
        names = {n.name for n in stub.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("iequals", names)
        self.assertIn(".. autofunction:: iequals", (ROOT / "docs/api.rst").read_text())
        import more_itertools

        self.assertIn("iequals", more_itertools.more.__all__)
        self.assertTrue(more_itertools.iequals("abc", ["a", "b", "c"]))


if __name__ == "__main__":
    unittest.main()
