#!/usr/bin/env python3
"""
Verify that the StreamLL RAG demo is properly configured.
This script tests core functionality without external dependencies.
"""

import sys
from pathlib import Path


def test_demo_structure():
    """Test that all demo files are present."""
    demo_dir = Path(__file__).parent

    required_files = [
        "README.md",
        "docker-compose.yml",
        "pyproject.toml",
        "init-db.sql",
        ".env.example",
        "src/index.py",
        "src/rag.py",
        "data/streamll_overview.md",
        "data/dspy_integration.md",
        "data/production_patterns.md",
    ]

    missing_files = []
    for file_path in required_files:
        full_path = demo_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    return not missing_files


def test_documentation_content():
    """Test that documentation files contain expected content."""
    data_dir = Path(__file__).parent / "data"

    tests = [
        ("streamll_overview.md", ["StreamLL", "DSPy", "RedisSink", "TerminalSink"]),
        ("dspy_integration.md", ["callback", "LM", "Tool", "StreamllDSPyCallback"]),
        ("production_patterns.md", ["circuit breaker", "resilience", "infrastructure"]),
    ]

    for filename, expected_terms in tests:
        file_path = data_dir / filename

        try:
            with open(file_path) as f:
                content = f.read().lower()

            missing_terms = []
            for term in expected_terms:
                if term.lower() not in content:
                    missing_terms.append(term)

            if missing_terms:
                return False
            else:
                pass

        except Exception:
            return False

    return True


def test_docker_configuration():
    """Test Docker Compose configuration."""
    compose_file = Path(__file__).parent / "docker-compose.yml"

    try:
        with open(compose_file) as f:
            content = f.read()

        required_services = ["postgres", "redis"]
        required_ports = ["5432", "6379"]
        required_images = ["pgvector/pgvector", "redis"]

        checks = [
            (required_services, "services"),
            (required_ports, "ports"),
            (required_images, "images"),
        ]

        for items, _item_type in checks:
            missing = [item for item in items if item not in content]
            if missing:
                return False

        return True

    except Exception:
        return False


def test_python_imports():
    """Test that Python scripts have valid import structure."""
    # Different scripts have different requirements
    script_requirements = {
        "src/index.py": [
            "from llama_index.core import",
            "from llama_index.vector_stores.postgres import",
            "from llama_index.embeddings.openai import",
        ],
        "src/rag.py": ["import streamll", "from streamll.sinks import", "import dspy"],
    }

    for script_path, required_imports in script_requirements.items():
        full_path = Path(__file__).parent / script_path

        try:
            with open(full_path) as f:
                content = f.read()

            # Check that imports are present (not necessarily working)
            missing_imports = []
            for import_stmt in required_imports:
                if import_stmt not in content:
                    missing_imports.append(import_stmt)

            if missing_imports:
                return False
            else:
                pass

        except Exception:
            return False

    return True


def main():
    """Run all verification tests."""

    tests = [
        ("Demo Structure", test_demo_structure),
        ("Documentation Content", test_documentation_content),
        ("Docker Configuration", test_docker_configuration),
        ("Python Imports", test_python_imports),
    ]

    passed = 0
    total = len(tests)

    for _test_name, test_func in tests:
        if test_func():
            passed += 1


    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
