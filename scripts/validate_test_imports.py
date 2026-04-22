#!/usr/bin/env python3
"""Validate test module imports before pytest runs."""

import os
import sys
import ast
from pathlib import Path
from typing import Set, List, Tuple

class ImportValidator:
    """Validates imports in test modules."""

    STANDARD_LIBRARY = {
        'pytest', 'json', 'unittest', 'mock', 'datetime', 'time',
        'concurrent', 'subprocess', 'os', 're', 'collections', 'typing',
        'asyncio', 'inspect', 'sys', 'pathlib', 'tempfile'
    }

    def __init__(self, test_dir: str = 'tests'):
        self.test_dir = Path(test_dir)
        self.local_modules = self._find_local_modules()
        self.errors: List[Tuple[str, str]] = []

    def _find_local_modules(self) -> Set[str]:
        """Find all local modules in the project."""
        modules = {
            'spectrum_systems', 'scripts', 'tests', 'working_paper_generator',
            'apps', 'packages', 'control_plane', 'shared'
        }
        return modules

    def validate_all(self) -> bool:
        """Validate all test modules."""
        if not self.test_dir.exists():
            return True

        test_files = list(self.test_dir.glob('test_*.py'))
        for test_file in test_files:
            self._validate_file(test_file)

        if self.errors:
            print("❌ Import Validation Failed")
            for file, error in self.errors:
                print(f"  {file}: {error}")
            return False

        print(f"✅ Import Validation Passed ({len(test_files)} test modules)")
        return True

    def _validate_file(self, file_path: Path) -> None:
        """Validate imports in a single file."""
        try:
            with open(file_path) as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            self.errors.append((str(file_path), f"Syntax error: {e}"))
            return

        imports = self._extract_imports(tree)
        problematic = self._check_imports(imports)

        if problematic:
            self.errors.append((str(file_path), f"Missing dependencies: {', '.join(problematic)}"))

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """Extract all imported modules from AST."""
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])

        return imports

    def _check_imports(self, imports: Set[str]) -> List[str]:
        """Check if imports are available."""
        problematic = []

        for imp in imports:
            if imp in self.STANDARD_LIBRARY or imp in self.local_modules:
                continue
            if imp.startswith('test_'):  # Other test modules
                continue
            if self._is_available(imp):
                continue
            problematic.append(imp)

        return sorted(problematic)

    def _is_available(self, module: str) -> bool:
        """Check if a module is importable."""
        try:
            __import__(module)
            return True
        except ImportError:
            return False


if __name__ == '__main__':
    validator = ImportValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)
