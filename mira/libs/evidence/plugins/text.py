"""Plain text evidence plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin
from .utils import read_text_with_cap


class PlainTextPlugin(EvidencePlugin):
    supported_kinds = ("text",)

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        content = read_text_with_cap(absolute, policy)

        # Track truncation
        was_truncated_on_read = "truncated before processing" in content
        clamped_snippets, was_clamped = clamp_snippets([content], policy.max_text_bytes_per_file)

        truncation_warning = None
        if was_truncated_on_read:
            truncation_warning = f"File too large (>{policy.max_text_bytes_per_file * 20} bytes)"
        elif was_clamped:
            truncation_warning = f"Content exceeded {policy.max_text_bytes_per_file} bytes, truncated"

        summary = f"Plain text excerpt from {manifest_entry.path.name}."
        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=clamped_snippets,
            truncation_warning=truncation_warning,
        )
