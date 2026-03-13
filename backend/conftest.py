"""
Root conftest — ensures backend/ is on sys.path for all tests.
"""
import sys
import os

# Add backend/ directory to PYTHONPATH so `from app.xxx` imports work
sys.path.insert(0, os.path.dirname(__file__))
