"""
Shared setup for the tests of graphdb/: the CSV export and the domain files.

The backend's tests reach `app` through their package; these put backend/ on
the import path themselves, so `pytest graphdb/tests` also runs on its own.
"""

import gzip
import importlib.util
import os
import sys

import pytest

GRAPHDB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(GRAPHDB)
BACKEND = os.path.join(REPO, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(GRAPHDB, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def export_csv():
    return _load("export_csv")


@pytest.fixture(scope="session")
def fetch_domains():
    return _load("fetch_domains")


@pytest.fixture
def write_gz():
    def write(path, text):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
        return str(path)
    return write
