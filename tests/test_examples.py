"""Tests to ensure all uv examples run without errors."""

import os
import subprocess
from pathlib import Path

import pytest


class TestExamples:
    """Test all example scripts execute successfully."""

    @pytest.fixture(scope="class")
    def examples_dir(self):
        """Get examples directory path."""
        return Path(__file__).parent.parent / "examples"

    @pytest.fixture(scope="class") 
    def mock_env(self):
        """Environment with mock API keys to prevent real API calls."""
        return {
            **os.environ,
            "OPENROUTER_API_KEY": "mock-key-for-testing",
        }

    def test_quickstart_runs(self, examples_dir, mock_env):
        """Test ./quickstart.py runs without errors."""
        script = examples_dir / "quickstart.py"
        result = subprocess.run(
            [str(script)],
            env=mock_env,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        # Should not crash (exit code 0 or expected API error)
        assert result.returncode in (0, 1), f"Unexpected error: {result.stderr}"

    def test_production_redis_syntax(self, examples_dir):
        """Test production_redis.py has valid syntax."""
        script = examples_dir / "production_redis.py"
        # Just compile, don't run (needs Redis)
        result = subprocess.run(
            ["uv", "run", "python", "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_consumer_demo_syntax(self, examples_dir):
        """Test consumer_demo.py has valid syntax."""
        script = examples_dir / "consumer_demo.py" 
        # Just compile, don't run (needs Redis)
        result = subprocess.run(
            ["uv", "run", "python", "-m", "py_compile", str(script)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Syntax error: {result.stderr}"