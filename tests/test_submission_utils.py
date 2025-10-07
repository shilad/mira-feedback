"""Tests for submission utilities."""

import pytest
import tempfile
from pathlib import Path

from mira.tools.grading_feedback.submission_utils import (
    find_all_submission_files,
    create_submission_summary,
    build_submission_content,
    select_files_to_grade,
    SIZE_THRESHOLD,
    SUBMISSION_EXTENSIONS,
    SKIP_PATTERNS
)


def test_find_all_submission_files():
    """Test finding submission files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create various test files
        (tmpdir / "main.py").write_text("print('hello')")
        (tmpdir / "test.java").write_text("class Test {}")
        (tmpdir / "README.md").write_text("# Project")
        (tmpdir / "data.csv").write_text("a,b,c\n1,2,3")

        # Create files that should be skipped
        (tmpdir / "feedback.txt").write_text("Feedback")
        (tmpdir / ".hidden.py").write_text("hidden")
        (tmpdir / "rubric.md").write_text("Rubric")

        # Create subdirectory with files
        subdir = tmpdir / "src"
        subdir.mkdir()
        (subdir / "utils.py").write_text("def helper(): pass")

        # Find files
        files = find_all_submission_files(tmpdir)

        # Check results
        file_names = [f[0].name for f in files]
        assert "main.py" in file_names
        assert "test.java" in file_names
        assert "README.md" in file_names
        assert "data.csv" in file_names
        assert "utils.py" in file_names

        # Check that skipped files are not included
        assert "feedback.txt" not in file_names
        assert ".hidden.py" not in file_names
        assert "rubric.md" not in file_names

        # Check that files are sorted by size (largest first)
        sizes = [f[1] for f in files]
        assert sizes == sorted(sizes, reverse=True)


def test_find_all_submission_files_empty_dir():
    """Test finding files in an empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        files = find_all_submission_files(tmpdir)
        assert files == []


def test_create_submission_summary():
    """Test creating a submission summary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test files with known sizes
        file1 = tmpdir / "main.py"
        file1.write_text("x" * 100)  # 100 bytes

        file2 = tmpdir / "big.java"
        file2.write_text("x" * 5000)  # 5KB

        file3 = tmpdir / "huge.md"
        file3.write_text("x" * 2000000)  # ~2MB

        files = [
            (file1, 100),
            (file2, 5000),
            (file3, 2000000)
        ]

        # Create summary
        summary = create_submission_summary(tmpdir, files)

        # Check summary content
        assert tmpdir.name in summary
        assert "Total files: 3" in summary
        assert "100 bytes" in summary
        assert "4.9 KB" in summary
        assert "1.9 MB" in summary
        assert "(source code)" in summary
        assert "(documentation)" in summary


def test_build_submission_content():
    """Test building submission content from files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test files
        file1 = tmpdir / "main.py"
        file1.write_text("def main():\n    print('hello')")

        file2 = tmpdir / "test.pdf"
        file2.write_text("PDF content")  # Won't be read as text

        files = [
            (file1, file1.stat().st_size),
            (file2, file2.stat().st_size)
        ]

        # Build content
        content = build_submission_content(tmpdir, files)

        # Check content
        assert "FILE: main.py" in content
        assert "def main():" in content
        assert "print('hello')" in content
        assert "FILE: test.pdf" in content
        assert "[PDF file - content not extracted]" in content
        assert "=" * 60 in content  # Separator


def test_build_submission_content_truncation():
    """Test that large files are truncated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a large file
        large_file = tmpdir / "large.txt"
        large_content = "x" * 60000  # 60KB
        large_file.write_text(large_content)

        files = [(large_file, large_file.stat().st_size)]

        # Build content with small max size
        content = build_submission_content(tmpdir, files, max_file_size=1000)

        # Check truncation
        assert "... [truncated] ..." in content
        assert len(content) < 60000  # Should be much smaller than original


def test_build_submission_content_error_handling():
    """Test error handling when reading files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a file that we'll delete before reading
        file1 = tmpdir / "exists.py"
        file1.write_text("exists")

        # Reference to non-existent file
        file2 = tmpdir / "missing.py"

        files = [
            (file1, 100),
            (file2, 100)  # File doesn't exist
        ]

        # Build content - should handle missing file gracefully
        content = build_submission_content(tmpdir, files)

        assert "FILE: exists.py" in content
        assert "exists" in content
        assert "FILE: missing.py" in content
        assert "[Error reading file:" in content


def test_select_files_to_grade():
    """Test selecting files based on LLM selection."""
    # Create dummy file paths
    files = [
        (Path("/tmp/main.py"), 1000),
        (Path("/tmp/test.py"), 500),
        (Path("/tmp/utils.py"), 200),
        (Path("/tmp/README.md"), 100)
    ]

    # Test selection by full path
    selected = select_files_to_grade(files, ["/tmp/main.py", "/tmp/test.py"])
    assert len(selected) == 2
    assert selected[0][0].name == "main.py"
    assert selected[1][0].name == "test.py"

    # Test selection by filename only
    selected = select_files_to_grade(files, ["utils.py", "README.md"])
    assert len(selected) == 2
    assert selected[0][0].name == "utils.py"
    assert selected[1][0].name == "README.md"

    # Test mixed selection
    selected = select_files_to_grade(files, ["/tmp/main.py", "test.py"])
    assert len(selected) == 2

    # Test empty selection
    selected = select_files_to_grade(files, [])
    assert selected == []

    # Test non-matching selection
    selected = select_files_to_grade(files, ["nonexistent.py"])
    assert selected == []


def test_constants():
    """Test that constants are defined correctly."""
    assert SIZE_THRESHOLD == 10 * 1024  # 10KB
    assert isinstance(SUBMISSION_EXTENSIONS, list)
    assert "*.py" in SUBMISSION_EXTENSIONS
    assert "*.java" in SUBMISSION_EXTENSIONS
    assert isinstance(SKIP_PATTERNS, list)
    assert "feedback" in SKIP_PATTERNS
    assert "rubric" in SKIP_PATTERNS