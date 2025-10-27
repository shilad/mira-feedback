"""Plugin base class for evidence extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile


class EvidencePlugin:
    """Extension point for per-file extraction strategies."""

    supported_kinds: tuple[str, ...] = ()

    def matches(self, manifest_entry: ManifestFile) -> bool:
        return manifest_entry.kind in self.supported_kinds

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        raise NotImplementedError
