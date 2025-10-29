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

        # Track if content was truncated during read
        was_truncated_on_read = "truncated before processing" in content

        content = redact_embedded_images(content)
        content = truncate_long_lines(content)

        # Clamp to final size limit
        clamped_snippets, was_clamped = clamp_snippets([content], policy.max_text_bytes_per_file)

        # Build truncation warning if needed
        truncation_warning = None
        if was_truncated_on_read:
            truncation_warning = f"File too large (>{policy.max_text_bytes_per_file * 20} bytes), pre-truncated before processing"
        elif was_clamped:
            truncation_warning = f"Content exceeded {policy.max_text_bytes_per_file} bytes after processing, some content may be missing"

        summary = f"Documentation extracted from {manifest_entry.path.name}."
        if manifest_entry.kind == "r-markdown":
            summary += " Contains R Markdown or Quarto content."

        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary=summary,
            snippets=clamped_snippets,
            truncation_warning=truncation_warning,
        )


def redact_embedded_images(content: str) -> str:
    """
    Remove inline image blobs (data URIs or large hex strings) from markdown content.

    Keeps the surrounding text but replaces the heavy payload with a short placeholder.
    """
    # Remove entire <img> tags (both self-closing and paired)
    img_tag_pattern = re.compile(
        r"<img\s+[^>]*?(?:src\s*=\s*['\"]data:image/[^'\"]+['\"])[^>]*?(?:/>|>.*?</img>)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    content = img_tag_pattern.sub("[image-redacted]", content)

    # Also catch any remaining standalone img tags
    img_simple_pattern = re.compile(r"<img[^>]*>", flags=re.IGNORECASE)
    content = img_simple_pattern.sub("[image-redacted]", content)

    # Remove R Markdown/pandoc style images: ![alt](path) or ![](path)
    md_image_pattern = re.compile(r"!\[.*?\]\([^\)]+\)")
    content = md_image_pattern.sub("[image-redacted]", content)

    # Catch any remaining data URIs in various quote styles
    data_uri_pattern = re.compile(
        r"data:image/[a-zA-Z0-9+\-\.]+;[^\s)>\"']+",
        flags=re.IGNORECASE,
    )
    content = data_uri_pattern.sub("[image-data-redacted]", content)

    # Remove large hex blobs (likely encoded images)
    hex_blob_pattern = re.compile(r"[0-9A-Fa-f]{256,}")
    content = hex_blob_pattern.sub("[hex-data-redacted]", content)

    return content


def truncate_long_lines(content: str, max_line_length: int = 500) -> str:
    """
    Intelligently truncate extra-long lines while preserving structure.

    - Lines >max_line_length: Keep first 200 + last 100 chars with placeholder
    - Collapse repetitive code output patterns
    - Preserve markdown headers, lists, code blocks
    """
    lines = content.split('\n')
    result_lines = []
    in_code_block = False
    code_block_lines = []

    for line in lines:
        # Track code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block - process accumulated lines
                if len(code_block_lines) > 20:
                    # Keep first 8 and last 8 lines of long code blocks
                    kept_lines = (
                        code_block_lines[:8] +
                        ['... [code block truncated] ...'] +
                        code_block_lines[-8:]
                    )
                    result_lines.extend(kept_lines)
                else:
                    result_lines.extend(code_block_lines)
                code_block_lines = []
                in_code_block = False
                result_lines.append(line)
            else:
                in_code_block = True
                result_lines.append(line)
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Truncate very long lines (but preserve structure)
        if len(line) > max_line_length:
            # Keep markdown structure markers
            if line.strip().startswith(('#', '-', '*', '>', '|')):
                # Keep headers, lists, blockquotes, tables as-is up to limit
                result_lines.append(line[:max_line_length] + ' [...]')
            else:
                # For prose/data: keep start and end
                truncated = (
                    line[:200] +
                    ' [...line truncated...] ' +
                    line[-100:]
                )
                result_lines.append(truncated)
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)
