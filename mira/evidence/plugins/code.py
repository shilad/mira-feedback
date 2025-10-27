"""Code file evidence plugin."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin
from .utils import read_text_with_cap


class CodeFilePlugin(EvidencePlugin):
    supported_kinds = ("code", "code-r")

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        content = read_text_with_cap(absolute, policy)
        summary = summarize_code(content, manifest_entry.path)
        snippets = clamp_snippets([content], policy.max_text_bytes_per_file)
        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=snippets,
        )


def summarize_code(content: str, path: Path) -> str:
    lines = content.splitlines()
    top_lines = "\n".join(lines[:5])
    def_lines = [
        line
        for line in lines
        if line.strip().startswith(("def ", "class ", "function", "proc", "fn "))
    ]
    def_preview = "; ".join(def_lines[:6])
    summary_parts = [
        f"Code excerpt from {path.name}.",
        f"First lines:\n{textwrap.dedent(top_lines).strip()}",
    ]
    if def_preview:
        summary_parts.append(f"Detected definitions: {def_preview}")
    return "\n".join(summary_parts)
