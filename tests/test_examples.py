"""Tests for example files."""

import subprocess
import sys
from pathlib import Path

import pytest


class TestExamples:
    @pytest.fixture
    def examples_dir(self):
        return Path(__file__).parent.parent / "examples"

    def run_example(self, example_path):
        """Run an example file and return the result."""
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(example_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result

    def test_basic_example_runs(self, examples_dir):
        """Test that basic.py runs without errors."""
        basic_example = examples_dir / "basic.py"
        if not basic_example.exists():
            pytest.skip("basic.py not found")

        result = self.run_example(basic_example)

        # Check for success
        assert result.returncode == 0, (
            f"basic.py failed with:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

        # Verify expected output patterns - should show events like START/END
        output_lower = result.stdout.lower()
        assert (
            "StreamLL Basic Example" in result.stdout
            or "event" in output_lower
            or "start" in output_lower
            or "end" in output_lower
        ), f"basic.py should produce event output, got: {result.stdout[:200]}..."

    def test_examples_use_streamll(self, examples_dir):
        """Verify all examples import streamll."""
        example_files = list(examples_dir.glob("*.py"))

        for example_file in example_files:
            content = example_file.read_text()
            assert "import streamll" in content or "from streamll" in content, (
                f"{example_file.name} should import streamll"
            )

    def test_no_hardcoded_credentials(self, examples_dir):
        """Ensure examples don't contain hardcoded credentials."""
        example_files = list(examples_dir.glob("*.py"))

        suspicious_patterns = [
            "password=",
            "secret=",
            "token=",
            "api_key=",
            "aws_access_key",
        ]

        for example_file in example_files:
            content = example_file.read_text().lower()

            for pattern in suspicious_patterns:
                if pattern in content:
                    # Allow environment variable references
                    lines = content.split("\n")
                    for line in lines:
                        if pattern in line and "os.environ" not in line and "getenv" not in line:
                            pytest.fail(
                                f"{example_file.name} may contain hardcoded credentials: {pattern}"
                            )
