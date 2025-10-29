"""Jupyter notebook evidence plugin."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin
from .utils import read_text_with_cap


class NotebookPlugin(EvidencePlugin):
    supported_kinds = ("notebook",)

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        try:
            import nbformat  # type: ignore

            notebook = nbformat.read(absolute, as_version=4)
        except Exception as exc:  # pylint: disable=broad-except
            raw = read_text_with_cap(absolute, policy)
            was_truncated_on_read = "truncated before processing" in raw
            snippets, was_clamped = clamp_snippets([raw], policy.max_text_bytes_per_file)

            truncation_warning = None
            if was_truncated_on_read:
                truncation_warning = f"File too large (>{policy.max_text_bytes_per_file * 20} bytes)"
            elif was_clamped:
                truncation_warning = f"Content exceeded {policy.max_text_bytes_per_file} bytes, truncated"

            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary=f"Notebook could not be parsed ({exc}); raw JSON snippet attached.",
                snippets=snippets,
                truncation_warning=truncation_warning,
            )

        cells = notebook.get("cells", [])[: policy.max_notebook_cells]
        code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
        markdown_cells = [cell for cell in cells if cell.get("cell_type") == "markdown"]

        md_snippets = [
            textwrap.dedent(cell.get("source", "")).strip()[: policy.max_text_bytes_per_file]
            for cell in markdown_cells[:5]
        ]
        code_snippets = [
            cell.get("source", "")[: policy.max_text_bytes_per_file]
            for cell in code_cells[:5]
        ]
        summary = (
            f"Notebook with {len(cells)} cells "
            f"({len(code_cells)} code, {len(markdown_cells)} markdown). "
            "Outputs trimmed."
        )
        snippets, was_clamped = clamp_snippets(md_snippets + code_snippets, policy.max_text_bytes_per_file)

        truncation_warning = None
        if was_clamped:
            truncation_warning = f"Notebook content exceeded {policy.max_text_bytes_per_file} bytes, some cells truncated"

        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=snippets,
            truncation_warning=truncation_warning,
        )
