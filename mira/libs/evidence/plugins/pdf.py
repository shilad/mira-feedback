"""PDF evidence plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin


class PdfFilePlugin(EvidencePlugin):
    supported_kinds = ("pdf",)

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        try:
            import fitz  # type: ignore

            doc = fitz.open(absolute)
            page_texts = []
            for page_idx in range(min(policy.max_pdf_pages, doc.page_count)):
                page = doc.load_page(page_idx)
                page_texts.append(page.get_text("text"))
        except Exception as exc:  # pylint: disable=broad-except
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary="PDF content not available; please review manually if required.",
                snippets=[],
            )

        snippets, was_clamped = clamp_snippets(page_texts, policy.max_text_bytes_per_file)

        truncation_warning = None
        if was_clamped:
            truncation_warning = f"PDF content exceeded {policy.max_text_bytes_per_file} bytes, some pages not included"

        summary = f"PDF document excerpted ({len(snippets)} pages captured)."
        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=snippets,
            truncation_warning=truncation_warning,
        )
