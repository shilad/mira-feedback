"""Shared utilities for processing submission directories."""

import logging
from pathlib import Path
from typing import List, Tuple

LOG = logging.getLogger(__name__)

# Size threshold for two-pass approach (10KB)
SIZE_THRESHOLD = 10 * 1024  # 10KB in bytes

# Common file extensions to look for in submissions
SUBMISSION_EXTENSIONS = [
    '*.py', '*.ipynb',
    '*.R', '*.r', '*.Rmd', '*.qmd',
    '*.java', '*.cpp', '*.c', '*.h',
    '*.js', '*.ts', '*.jsx', '*.tsx',
    '*.md', '*.txt', '*.html',
    '*.sql', '*.sh', '*.yml', '*.yaml', '*.json',
    '*.csv', '*.pdf'
]

# Files to skip during discovery
SKIP_PATTERNS = ['feedback', 'grading', 'rubric', '.git']


def find_all_submission_files(submission_dir: Path) -> List[Tuple[Path, int]]:
    """
    Find all submission files in a directory with their sizes.

    Args:
        submission_dir: Directory to search for submission files

    Returns:
        List of (file_path, size_in_bytes) tuples, sorted by size (largest first)
    """
    submission_files = []

    for ext in SUBMISSION_EXTENSIONS:
        files = list(submission_dir.glob(ext))
        for file in files:
            # Skip feedback, rubric, and hidden files
            if any(skip in file.name.lower() for skip in SKIP_PATTERNS):
                continue
            if file.name.startswith('.'):
                continue

            try:
                size = file.stat().st_size
                submission_files.append((file, size))
            except Exception as e:
                LOG.warning(f"Could not stat file {file}: {e}")

    # Also check subdirectories (one level deep)
    for subdir in submission_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('.'):
            for ext in SUBMISSION_EXTENSIONS:
                files = list(subdir.glob(ext))
                for file in files:
                    if any(skip in file.name.lower() for skip in SKIP_PATTERNS):
                        continue
                    if file.name.startswith('.'):
                        continue

                    try:
                        size = file.stat().st_size
                        submission_files.append((file, size))
                    except Exception as e:
                        LOG.warning(f"Could not stat file {file}: {e}")

    # Sort by size (largest first) for better visibility
    submission_files.sort(key=lambda x: x[1], reverse=True)

    return submission_files


def create_submission_summary(submission_dir: Path, files: List[Tuple[Path, int]]) -> str:
    """
    Create a summary of submission contents for LLM to decide which files to review.

    Args:
        submission_dir: The submission directory
        files: List of (file_path, size) tuples

    Returns:
        Summary string describing the submission structure
    """
    summary = f"SUBMISSION DIRECTORY: {submission_dir.name}\n"
    summary += f"Total files: {len(files)}\n"
    summary += f"Total size: {sum(f[1] for f in files):,} bytes\n\n"
    summary += "FILE STRUCTURE:\n"

    for file_path, size in files:
        # Get relative path from submission directory
        try:
            rel_path = file_path.relative_to(submission_dir)
        except ValueError:
            rel_path = file_path.name

        # Format size nicely
        if size < 1024:
            size_str = f"{size} bytes"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"

        summary += f"  - {rel_path}: {size_str}\n"

        # Add file type hint
        suffix = file_path.suffix.lower()
        if suffix in ['.py', '.java', '.cpp', '.c', '.js', '.ts']:
            summary += f"    (source code)\n"
        elif suffix in ['.md', '.txt', '.pdf']:
            summary += f"    (documentation)\n"
        elif suffix in ['.ipynb', '.Rmd', '.qmd']:
            summary += f"    (notebook)\n"
        elif suffix in ['.csv', '.json', '.yml', '.yaml']:
            summary += f"    (data/config)\n"

    return summary


def build_submission_content(submission_dir: Path, files_to_grade: List[Tuple[Path, int]],
                            max_file_size: int = 50000) ->  str:
    """
    Build the submission content string from selected files.

    Args:
        submission_dir: The submission directory
        files_to_grade: List of (file_path, size) tuples to include
        max_file_size: Maximum characters to read from each file before truncating

    Returns:
        Formatted submission content string
    """
    submission_content = ""

    for file_path, size in files_to_grade:
        try:
            rel_path = file_path.relative_to(submission_dir)
        except ValueError:
            rel_path = file_path.name

        submission_content += f"\n{'='*60}\n"
        submission_content += f"FILE: {rel_path}\n"
        submission_content += f"{'='*60}\n"

        try:
            if file_path.suffix.lower() == '.pdf':
                submission_content += "[PDF file - content not extracted]\n"
            else:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                # Truncate very large files
                if len(content) > max_file_size:
                    content = content[:max_file_size] + "\n... [truncated] ..."
                submission_content += content
        except Exception as e:
            submission_content += f"[Error reading file: {e}]\n"

    return submission_content


def select_files_to_grade(submission_files: List[Tuple[Path, int]],
                         selected_filenames: List[str]) -> List[Tuple[Path, int]]:
    """
    Filter submission files to only those selected by the LLM.

    Args:
        submission_files: All submission files found
        selected_filenames: List of filenames selected by LLM

    Returns:
        Filtered list of files to grade
    """
    files_to_grade = []

    for file_path, size in submission_files:
        # Check if file path or just filename matches selection
        if str(file_path) in selected_filenames or str(file_path.name) in selected_filenames:
            files_to_grade.append((file_path, size))
            LOG.debug(f"Selected for grading: {file_path.name}")

    return files_to_grade