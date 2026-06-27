"""
mcp/registry.py — Tool catalogue with auto-generated JSON schemas.

Discovers every public function in tools/*.py, inspects its signature and
docstring, and builds a JSON schema for each one. Drop a new tools/mytool.py
file → it appears in the MCP catalogue automatically.
"""

import importlib
import inspect
import logging
import os
import pkgutil
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("jarvis.mcp.registry")

TOOLS_PACKAGE = "tools"
TOOLS_DIR = Path(__file__).parent.parent / "tools"

# Python type → JSON Schema type mapping
_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "NoneType": "null",
}


def _py_type_to_json(annotation) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"
    name = getattr(annotation, "__name__", str(annotation))
    return _TYPE_MAP.get(name, "string")


def _build_schema(func: Callable) -> dict:
    """Build a JSON Schema object from a Python function's signature + docstring."""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        prop = {"type": _py_type_to_json(param.annotation)}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default if param.default is not None else ""
        properties[param_name] = prop

    schema = {
        "name": func.__name__,
        "description": doc.split("\n")[0] if doc else f"Execute {func.__name__}",
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }
    return schema


class ToolRegistry:
    """
    Discovers and registers all tool functions from the tools/ package.

    A function is registered if:
      - It lives in a module directly under jarvis/tools/
      - Its name does not start with '_'
      - It is not a class
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}        # name → {schema, callable}
        self._discover()

    def _discover(self):
        for finder, module_name, is_pkg in pkgutil.iter_modules([str(TOOLS_DIR)]):
            full_name = f"{TOOLS_PACKAGE}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except ImportError as e:
                logger.warning("Skipping module %s (import error): %s", full_name, e)
                continue

            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                obj = getattr(module, attr_name)
                if not callable(obj) or inspect.isclass(obj):
                    continue
                # Only register functions defined in this module (not imports)
                if getattr(obj, "__module__", "") != full_name:
                    continue

                try:
                    schema = _build_schema(obj)
                    key = f"{module_name}.{attr_name}"
                    self._tools[key] = {"schema": schema, "callable": obj}
                    logger.debug("Registered tool: %s", key)
                except Exception as e:
                    logger.warning("Could not register %s.%s: %s", module_name, attr_name, e)

        logger.info("Tool registry: %d tools discovered.", len(self._tools))

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def list_schemas(self) -> list[dict]:
        """Return all tool JSON schemas (for MCP server advertisement)."""
        return [entry["schema"] for entry in self._tools.values()]

    def get_callable(self, tool_name: str) -> Optional[Callable]:
        """Retrieve the callable for a registered tool by its full name."""
        entry = self._tools.get(tool_name)
        return entry["callable"] if entry else None

    def call(self, tool_name: str, arguments: dict) -> Any:
        """Invoke a tool by name with a dict of arguments."""
        fn = self.get_callable(tool_name)
        if fn is None:
            raise KeyError(f"Unknown tool: {tool_name}")
        return fn(**arguments)

    def all_tools(self) -> dict:
        return dict(self._tools)


# Module-level singleton
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
