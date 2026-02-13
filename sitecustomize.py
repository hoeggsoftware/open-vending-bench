import os, sys, importlib

# Ensure the project root is on sys.path for imports like 'cerebras'
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Pre‑load the stub package so patch can find it when pytest starts
try:
    importlib.import_module("cerebras")
except Exception:
    pass
