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
        summary = f"Plain text excerpt from {manifest_entry.path.name}."
        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=clamp_snippets([content], policy.max_text_bytes_per_file),
        )
