"""Test sources."""

import importlib
import unittest
from pathlib import Path

import pyobo.sources
from pyobo import Obo

EXCEPTIONS = {"biogrid", "agrovoc", "go", "chebi"}


class TestSources(unittest.TestCase):
    """Test sources."""

    def test_complete(self):
        """Test all files are imported in `__init__.py`."""
        directory = Path(pyobo.sources.__file__).parent.resolve()
        for path in directory.iterdir():
            if (
                path.stem in {"utils", "__init__", "__pycache__", "README"}
                or path.stem.endswith("_utils")
                or path.stem.endswith("_constants")
                or path.stem in EXCEPTIONS
            ):
                continue
            with self.subTest(module=path.stem):
                module = importlib.import_module(f"pyobo.sources.{path.stem}")
                getters = [
                    y
                    for k in module.__dir__()
                    if isinstance(y := getattr(module, k), type)
                    and issubclass(y, Obo)
                    and y is not Obo
                ]
                self.assertNotEqual(
                    0, len(getters), msg=f"forgot to create Obo subclass in {module.__name__}"
                )
