"""Data models for evidence extraction used during grading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_POLICY_VERSION = "v1"


@dataclass(frozen=True)
class EvidencePolicy:
    """Caps and knobs that keep evidence extraction deterministic and safe."""

    max_total_bytes: int = 500_000
    max_files: int = 40
    max_text_bytes_per_file: int = 60_000
    max_notebook_cells: int = 200
    max_csv_head_rows: int = 50
    max_csv_random_rows: int = 150
    max_json_chars: int = 20_000
    max_pdf_pages: int = 5
    hash_salt: str = DEFAULT_POLICY_VERSION


@dataclass
class ManifestFile:
    """Lightweight manifest entry describing a file inside the submission."""

    path: Path
    size: int
    suffix: str
    kind: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "size": self.size,
            "suffix": self.suffix,
            "kind": self.kind,
        }


@dataclass
class EvidenceCard:
    """
    Compiled evidence for a single file.

    Each card keeps a short rationale, structured metadata, and tightly bounded
    excerpts that can be stitched into the final grading prompt.
    """

    manifest_entry: ManifestFile
    summary: str
    snippets: List[str] = field(default_factory=list)
    stats: Optional[Dict[str, object]] = None

    def as_prompt_block(self) -> str:
        parts: List[str] = [
            f"FILE: {self.manifest_entry.path.as_posix()}",
            f"TYPE: {self.manifest_entry.kind}",
            f"SUMMARY: {self.summary.strip()}",
        ]
        if self.stats:
            stats_str = json.dumps(self.stats, indent=2, ensure_ascii=True)
            parts.append(f"STATS:\n{stats_str}")
        if self.snippets:
            for idx, snippet in enumerate(self.snippets, start=1):
                parts.append(f"SNIPPET {idx}:\n{snippet.strip()}")
        return "\n".join(parts)

    def to_dict(self) -> Dict[str, object]:
        return {
            "manifest_entry": self.manifest_entry.to_dict(),
            "summary": self.summary,
            "snippets": self.snippets,
            "stats": self.stats,
        }


@dataclass
class EvidencePack:
    """All extracted evidence for a submission."""

    manifest: List[ManifestFile]
    cards: List[EvidenceCard]
    policy: EvidencePolicy

    def render_for_model(self) -> str:
        """
        Render evidence into a compact, consistent format the grader model can consume.

        Cards are already size bounded, so we concatenate with section dividers.
        """
        rendered_cards = "\n\n".join(card.as_prompt_block() for card in self.cards)
        manifest_lines = "\n".join(
            f"- {entry.path.as_posix()} ({entry.kind}, {entry.size} bytes)"
            for entry in self.manifest
        )
        return (
            "SUBMISSION MANIFEST:\n"
            f"{manifest_lines}\n\n"
            "EVIDENCE CARDS:\n"
            f"{rendered_cards}"
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "policy": self.policy.__dict__,
            "manifest": [entry.to_dict() for entry in self.manifest],
            "cards": [card.to_dict() for card in self.cards],
        }


def clamp_snippets(snippets: Iterable[str], max_total_bytes: int) -> List[str]:
    """Ensure combined snippet size stays within policy budget."""
    result: List[str] = []
    running = 0
    for snippet in snippets:
        encoded = snippet.encode("utf-8", errors="ignore")
        if running + len(encoded) > max_total_bytes:
            break
        result.append(snippet)
        running += len(encoded)
    return result
