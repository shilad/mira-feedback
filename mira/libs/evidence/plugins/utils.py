"""Shared helpers for evidence plugins."""

from __future__ import annotations

from pathlib import Path

from ..models import EvidencePolicy


def read_text_with_cap(path: Path, policy: EvidencePolicy) -> str:
    """
    Read text file with a reasonable cap to prevent memory issues.

    Note: Returns full content up to 10x the per-file policy limit.
    Actual truncation happens after processing (image redaction, line truncation, etc.)
    in the plugin's build() method via clamp_snippets().
    """
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # pylint: disable=broad-except
        return f"[Unable to read file: {exc}]"

    # Allow reading larger files for processing, but cap at reasonable limit (20x policy)
    # This lets redaction/truncation functions work on full content before final clamping
    max_read_size = policy.max_text_bytes_per_file * 20
    if len(content) > max_read_size:
        return content[:max_read_size] + "\n... [file too large, truncated before processing] ..."
    return content
