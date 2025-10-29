"""HTML evidence plugin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile, clamp_snippets
from .base import EvidencePlugin
from .utils import read_text_with_cap


class HtmlPlugin(EvidencePlugin):
    supported_kinds = ("html",)

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        content = read_text_with_cap(absolute, policy)

        # Track if content was truncated during read
        was_truncated_on_read = "truncated before processing" in content

        # Clean HTML content
        content = clean_html(content)

        # Clamp to final size limit
        clamped_snippets, was_clamped = clamp_snippets([content], policy.max_text_bytes_per_file)

        # Build truncation warning if needed
        truncation_warning = None
        if was_truncated_on_read:
            truncation_warning = f"File too large (>{policy.max_text_bytes_per_file * 20} bytes), pre-truncated before processing"
        elif was_clamped:
            truncation_warning = f"Content exceeded {policy.max_text_bytes_per_file} bytes after processing, some content may be missing"

        summary = f"HTML content extracted from {manifest_entry.path.name}."

        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=clamped_snippets,
            truncation_warning=truncation_warning,
        )


def clean_html(content: str) -> str:
    """
    Clean HTML content for grading evidence.

    - Removes <script>, <style>, <noscript>, <iframe> tags and their content
    - Strips all attributes from remaining tags
    - Keeps tag structure intact for readability
    """
    # Remove script, style, noscript, and iframe tags with their content
    # Case-insensitive, handles multiline
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', content, flags=re.IGNORECASE | re.DOTALL)

    # Also remove self-closing iframe tags
    content = re.sub(r'<iframe[^>]*/>', '', content, flags=re.IGNORECASE)

    # Strip attributes from all remaining tags
    # Matches opening tags like <div class="foo" id="bar"> and replaces with <div>
    # Also handles self-closing tags like <img src="..." /> → <img />
    content = re.sub(r'<(\w+)[^>]*?(/?)>', r'<\1\2>', content)

    return content
