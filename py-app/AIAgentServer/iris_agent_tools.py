# Small wrapper module that re-exports the programmatic API from iris-commuter.py
# so other code can import a clean module name.

from typing import Dict, Any

# Import by relative module path. The iris-commuter.py file is in the same folder.
from .iris_commuter import create_commuter, import_class_file, compile_document_name, send_and_compile_file

__all__ = ["create_commuter", "import_class_file", "compile_document_name", "send_and_compile_file"]

# Optional convenience: provide a single entrypoint for agentic tools
def run_import(path: str, url: str = None, user: str = None, password: str = None) -> Dict[str, Any]:
    commuter = create_commuter(url=url, user=user, password=password)
    return import_class_file(commuter, path)

def run_compile(path: str, name: str, url: str = None, user: str = None, password: str = None) -> Dict[str, Any]:
    commuter = create_commuter(url=url, user=user, password=password)
    return compile_document_name(commuter, name)

def run_send_and_compile(path: str, url: str = None, user: str = None, password: str = None) -> Dict[str, Any]:
    commuter = create_commuter(url=url, user=user, password=password)
    return send_and_compile_file(commuter, path)
