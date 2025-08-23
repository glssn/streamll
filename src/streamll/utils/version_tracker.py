"""Module version tracking for detecting code changes in DSPy modules.

This module provides AST-based hashing to detect when module implementations
change, enabling correlation of performance/behavior changes with code updates.
"""

import ast
import hashlib
import inspect
import logging
import textwrap
from typing import Any

logger = logging.getLogger(__name__)


class ModuleVersionTracker:
    """Tracks module versions using configurable hashing strategies.
    
    Uses AST-based hashing to detect actual logic changes while ignoring
    cosmetic changes like whitespace and comments. Includes caching to
    minimize performance overhead.
    """

    def __init__(self, strategy: str = 'ast'):
        """Initialize version tracker with specified strategy.
        
        Args:
            strategy: Hashing strategy - 'ast', 'ast_with_deps', or 'none'
        """
        self.strategy = strategy
        # Cache by class type instead of instance ID to avoid ID reuse issues
        self._cache: dict[type, str | None] = {}

    def get_version(self, module: Any) -> str | None:
        """Get cached version or compute it for a module.
        
        Args:
            module: The module instance to version
            
        Returns:
            Version hash string or None if unavailable
        """
        # Use the module's class as the cache key
        module_class = module.__class__

        if module_class not in self._cache:
            if self.strategy == 'ast':
                version = self._compute_ast_hash(module)
            elif self.strategy == 'ast_with_deps':
                version = self._compute_ast_with_deps_hash(module)
            elif self.strategy == 'none':
                version = None
            else:
                logger.warning(f"Unknown strategy: {self.strategy}")
                version = None

            self._cache[module_class] = version

        return self._cache[module_class]

    def _compute_ast_hash(self, module: Any) -> str | None:
        """Compute AST hash of the forward() method.
        
        Args:
            module: Module instance with forward() method
            
        Returns:
            12-character hash of the AST or None if unavailable
        """
        try:
            forward_method = getattr(module, 'forward', None)
            if not forward_method:
                return None

            # Get source and parse to AST
            source = inspect.getsource(forward_method)
            # Remove indentation from method source
            source = textwrap.dedent(source)
            tree = ast.parse(source)

            # Convert AST to canonical string (no whitespace/comments)
            ast_dump = ast.dump(tree, annotate_fields=False)

            # Hash the AST representation
            hash_value = hashlib.sha256(ast_dump.encode()).hexdigest()[:12]

            logger.debug(f"Computed AST hash for {module.__class__.__name__}: {hash_value}")
            return hash_value

        except (OSError, TypeError, SyntaxError) as e:
            logger.debug(f"Could not compute AST hash for {module}: {e}")
            return None

    def _compute_ast_with_deps_hash(self, module: Any) -> str | None:
        """Compute AST hash including methods called by forward().
        
        This advanced strategy detects changes in helper methods that
        forward() depends on, providing more comprehensive tracking.
        
        Args:
            module: Module instance to analyze
            
        Returns:
            12-character hash of combined ASTs or None
        """
        try:
            # Get the module class source
            source = inspect.getsource(module.__class__)
            tree = ast.parse(source)

            # Find forward method and methods it calls
            forward_node = None
            called_methods = set()

            # First pass: find forward method
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'forward':
                    forward_node = node
                    break

            if not forward_node:
                return None

            # Second pass: find methods called by forward
            for node in ast.walk(forward_node):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        # Check for self.method() calls
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id == 'self':
                                called_methods.add(node.func.attr)

            # Collect ASTs of forward and its dependencies
            methods_to_hash = ['forward'] + sorted(list(called_methods))
            method_asts = []

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if isinstance(method, ast.FunctionDef):
                            if method.name in methods_to_hash:
                                # Store just the method AST
                                method_asts.append(ast.dump(method, annotate_fields=False))

            # Combine and hash all relevant method ASTs
            combined = '|'.join(sorted(method_asts))
            hash_value = hashlib.sha256(combined.encode()).hexdigest()[:12]

            logger.debug(
                f"Computed AST+deps hash for {module.__class__.__name__}: "
                f"{hash_value} (includes {methods_to_hash})"
            )
            return hash_value

        except (OSError, TypeError, SyntaxError) as e:
            logger.debug(f"Could not compute AST+deps hash for {module}: {e}")
            return None

    def clear_cache(self):
        """Clear the version cache.
        
        Useful for testing or when modules are reloaded.
        """
        self._cache.clear()


# Global instance for convenience
_default_tracker = ModuleVersionTracker()


def get_module_version(module: Any, strategy: str = 'ast') -> str | None:
    """Convenience function to get module version.
    
    Args:
        module: Module instance to version
        strategy: Hashing strategy to use
        
    Returns:
        Version hash or None
    """
    if strategy != _default_tracker.strategy:
        tracker = ModuleVersionTracker(strategy=strategy)
        return tracker.get_version(module)
    return _default_tracker.get_version(module)
