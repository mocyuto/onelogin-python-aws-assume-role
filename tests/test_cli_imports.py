#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Smoke test: the CLI module must import with only its declared dependencies.

This guards against a runtime dependency being used in code but missing from
`pyproject.toml` (e.g. `keyring`, which a fresh `uv sync --locked --no-dev`
must pull in or the console script crashes on startup).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class CliImportTest(unittest.TestCase):
    def test_cli_module_imports(self):
        # Importing the entry-point module exercises every top-level import
        # (keyring, boto3, lxml, yaml, requests, ...). If any declared
        # dependency is missing, this raises ModuleNotFoundError.
        from aws_assume_role import aws_assume_role

        self.assertTrue(callable(aws_assume_role.main))


if __name__ == "__main__":
    unittest.main()
