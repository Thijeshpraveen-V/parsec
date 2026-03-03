import ast
from typing import List, Dict, Any
import inspect

class PackageUsageVisitor(ast.NodeVisitor):
    def __init__(self, package_names: set[str]):
        self.package_names = package_names
        self.imports: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, Any]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            pkg = alias.name.split(".")[0]
            if pkg in self.package_names:
                self.imports.append({
                    "line": node.lineno,
                    "package": pkg,
                    "alias": alias.asname or alias.name.split(".")[0],
                    "full_import": alias.name,
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.module.split(".")[0] in self.package_names:
            self.imports.append({
                "line": node.lineno,
                "package": node.module.split(".")[0],
                "module": node.module,
                "names": [alias.name for alias in node.names],
            })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = self._get_func_name(node.func)
        if func_name and func_name.split(".")[0] in self.package_names:
            self.calls.append({
                "line": node.lineno,
                "call": func_name,
                "package": func_name.split(".")[0],
            })
        self.generic_visit(node)

    def _get_func_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attr_name(node)
        return None

    def _get_attr_name(self, node: ast.Attribute) -> str | None:
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None

def find_package_usage(source: str, package_names: set[str]) -> Dict[str, List[Any]]:
    """
    Find all imports and calls for given packages.
    """
    try:
        tree = ast.parse(source)
        visitor = PackageUsageVisitor(package_names)
        visitor.visit(tree)
        return {
            "imports": visitor.imports,
            "calls": visitor.calls,
        }
    except SyntaxError:
        return {"imports": [], "calls": []}
