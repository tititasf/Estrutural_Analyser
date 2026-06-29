"""Expose the project-level MCP package to the desktop application runtime.

The desktop app is launched from ``Agente-cad-PYSIDE-Restored-main`` while the
canonical MCP implementation lives at the project root. Extending this package
path keeps both entry points on one implementation instead of copying files.
"""

from pathlib import Path


_CANONICAL_MCP = Path(__file__).resolve().parents[3] / "src" / "mcp"
if not (_CANONICAL_MCP / "db_bridge.py").is_file():
    raise ImportError(f"Canonical MCP package not found at {_CANONICAL_MCP}")

_package_path = globals().get("__path__")
if _package_path is not None:
    _package_path.append(str(_CANONICAL_MCP))

