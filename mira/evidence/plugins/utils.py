"""Shared helpers for evidence plugins."""

from __future__ import annotations

from pathlib import Path

from ..models import EvidencePolicy


def read_text_with_cap(path: Path, policy: EvidencePolicy) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # pylint: disable=broad-except
        return f"[Unable to read file: {exc}]"

    if len(content) > policy.max_text_bytes_per_file:
        return content[: policy.max_text_bytes_per_file] + "\n... [truncated] ..."
    return content
