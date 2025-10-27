"""Structured text evidence plugin for JSON/YAML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile
from .base import EvidencePlugin


class JsonYamlPlugin(EvidencePlugin):
    supported_kinds = ("json", "yaml")

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        try:
            content = absolute.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # pylint: disable=broad-except
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary=f"Unable to read structured text: {exc}",
                snippets=[],
            )

        snippet = content[: policy.max_json_chars]
        if len(content) > policy.max_json_chars:
            snippet += "\n... [truncated] ..."

        try:
            parsed = json.loads(content)
            preview = json.dumps(parsed, indent=2)[: policy.max_json_chars]
            summary = "Structured document parsed as JSON."
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary=summary,
                snippets=[preview],
            )
        except json.JSONDecodeError:
            summary = "Structured document treated as plain text (non-JSON)."
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary=summary,
                snippets=[snippet],
            )
