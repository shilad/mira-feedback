"""Markdown and R Markdown evidence plugin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin
from .utils import read_text_with_cap


class MarkdownPlugin(EvidencePlugin):
    supported_kinds = ("markdown", "r-markdown")

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        content = read_text_with_cap(absolute, policy)
        content = redact_embedded_images(content)
        summary = f"Documentation extracted from {manifest_entry.path.name}."
        if manifest_entry.kind == "r-markdown":
            summary += " Contains R Markdown or Quarto content."
        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=clamp_snippets([content], policy.max_text_bytes_per_file),
        )


def redact_embedded_images(content: str) -> str:
    """
    Remove inline image blobs (data URIs or large hex strings) from markdown content.

    Keeps the surrounding text but replaces the heavy payload with a short placeholder.
    """
    data_uri_pattern = re.compile(
        r"data:image/[a-zA-Z0-9+\-\.]+;[^\s)>\"]+",
        flags=re.IGNORECASE,
    )
    content = data_uri_pattern.sub("[image-data-redacted]", content)

    hex_blob_pattern = re.compile(r"[0-9A-Fa-f]{256,}")
    content = hex_blob_pattern.sub("[hex-image-redacted]", content)
    return content
