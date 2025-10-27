"""Plugin registry for evidence extraction."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .base import EvidencePlugin
from .code import CodeFilePlugin
from .markdown import MarkdownPlugin
from .notebook import NotebookPlugin
from .pdf import PdfFilePlugin
from .structured import JsonYamlPlugin
from .tabular import CsvFilePlugin
from .text import PlainTextPlugin

NOTEBOOK_EXTENSIONS = {".ipynb"}
CSV_EXTENSIONS = {".csv", ".tsv"}
JSON_EXTENSIONS = {".json"}
YAML_EXTENSIONS = {".yml", ".yaml"}
PDF_EXTENSIONS = {".pdf"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
R_DOC_EXTENSIONS = {".rmd", ".Rmd", ".qmd", ".Qmd"}
R_SOURCE_EXTENSIONS = {".r", ".R"}
CODE_EXTENSIONS = {
    ".py",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".sql",
    ".sh",
    ".ps1",
    ".go",
    ".jl",
    ".rb",
    ".scala",
    ".pl",
    ".swift",
    ".kt",
    ".m",
}
TEXT_EXTENSIONS = {".txt", ".text", ".log"}


def default_plugins() -> List[EvidencePlugin]:
    return [
        CodeFilePlugin(),
        NotebookPlugin(),
        CsvFilePlugin(),
        JsonYamlPlugin(),
        PdfFilePlugin(),
        MarkdownPlugin(),
        PlainTextPlugin(),
    ]


def infer_kind(rel_path: Path, suffix: str) -> Optional[str]:
    suffix_lower = suffix.lower()
    if suffix_lower in NOTEBOOK_EXTENSIONS:
        return "notebook"
    if suffix_lower in CSV_EXTENSIONS:
        return "tabular-data"
    if suffix_lower in JSON_EXTENSIONS:
        return "json"
    if suffix_lower in YAML_EXTENSIONS:
        return "yaml"
    if suffix_lower in PDF_EXTENSIONS:
        return "pdf"
    if suffix_lower in MARKDOWN_EXTENSIONS:
        return "markdown"
    if suffix_lower in TEXT_EXTENSIONS:
        return "text"
    if suffix_lower in R_DOC_EXTENSIONS:
        return "r-markdown"
    if suffix_lower in R_SOURCE_EXTENSIONS:
        return "code-r"
    if suffix_lower in CODE_EXTENSIONS:
        return "code"

    if rel_path.parts and rel_path.parts[0].lower() in {"data", "datasets"}:
        return "tabular-data"

    return None
