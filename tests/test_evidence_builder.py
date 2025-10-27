from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from mira.evidence import EvidenceBuilder, EvidencePolicy
from mira.evidence.models import EvidenceCard


def _build_cards(tmp_path: Path) -> dict[str, EvidenceCard]:
    builder = EvidenceBuilder(policy=EvidencePolicy(max_total_bytes=1_000_000))
    pack = builder.build_evidence(tmp_path)
    return {card.manifest_entry.path.name: card for card in pack.cards}


def test_evidence_builder_captures_python_and_r_code(tmp_path):
    (tmp_path / "main.py").write_text(
        "def add(a, b):\n"
        "    \"\"\"Return the sum of two numbers.\"\"\"\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "analysis.R").write_text(
        "add <- function(a, b) {\n"
        "  a + b\n"
        "}\n",
        encoding="utf-8",
    )

    cards = _build_cards(tmp_path)

    py_card = cards["main.py"]
    assert py_card.manifest_entry.kind == "code"
    assert "Code excerpt from main.py." in py_card.summary
    assert any("def add" in snippet for snippet in py_card.snippets)

    r_card = cards["analysis.R"]
    assert r_card.manifest_entry.kind == "code-r"
    assert "Code excerpt from analysis.R." in r_card.summary
    assert any("add <- function" in snippet for snippet in r_card.snippets)


def test_evidence_builder_captures_r_markdown(tmp_path):
    (tmp_path / "report.Rmd").write_text(
        textwrap.dedent(
            """
            ---
            title: "Weekly Analysis"
            ---

            ```{r}
            summary(cars)
            ```
            """
        ).strip(),
        encoding="utf-8",
    )

    cards = _build_cards(tmp_path)
    rmd_card = cards["report.Rmd"]
    assert rmd_card.manifest_entry.kind == "r-markdown"
    assert "Contains R Markdown or Quarto content." in rmd_card.summary
    assert rmd_card.snippets, "Expected R Markdown content snippet"


def test_evidence_builder_captures_notebook(tmp_path):
    nbformat = pytest.importorskip("nbformat")
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Title"),
        nbformat.v4.new_code_cell("print('hello world')"),
    ]
    nbformat.write(nb, tmp_path / "analysis.ipynb")

    cards = _build_cards(tmp_path)
    nb_card = cards["analysis.ipynb"]
    assert nb_card.manifest_entry.kind == "notebook"
    assert nb_card.summary.startswith("Notebook with")
    assert any("print('hello world')" in snippet for snippet in nb_card.snippets)


def test_evidence_builder_samples_tabular_data(tmp_path):
    (tmp_path / "data.csv").write_text(
        "value,category\n1,A\n2,B\n3,B\n4,A\n",
        encoding="utf-8",
    )

    cards = _build_cards(tmp_path)
    csv_card = cards["data.csv"]
    assert csv_card.manifest_entry.kind == "tabular-data"
    assert csv_card.summary.startswith("Tabular dataset sampled")
    assert "HEAD" in csv_card.snippets[0]
    assert csv_card.stats is not None
    assert csv_card.stats["numeric"]["value"]["mean"] == pytest.approx(2.5)
    assert "category" in csv_card.stats["categorical"]


def test_evidence_builder_handles_json_and_yaml(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"threshold": 0.8, "features": ["a", "b"]}),
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "threshold: 0.5\nfeatures:\n  - x\n  - y\n",
        encoding="utf-8",
    )

    cards = _build_cards(tmp_path)
    json_card = cards["config.json"]
    assert json_card.manifest_entry.kind == "json"
    assert json_card.summary == "Structured document parsed as JSON."
    assert json_card.snippets and '"threshold": 0.8' in json_card.snippets[0]

    yaml_card = cards["config.yaml"]
    assert yaml_card.manifest_entry.kind == "yaml"
    assert yaml_card.summary == "Structured document treated as plain text (non-JSON)."
    assert "threshold: 0.5" in yaml_card.snippets[0]


def test_evidence_builder_handles_plain_text_and_pdf(tmp_path):
    (tmp_path / "notes.txt").write_text(
        "Remember to normalize the dataset before modeling.",
        encoding="utf-8",
    )
    (tmp_path / "report.pdf").write_text("This is not a real PDF.", encoding="utf-8")

    cards = _build_cards(tmp_path)

    text_card = cards["notes.txt"]
    assert text_card.manifest_entry.kind == "text"
    assert text_card.summary == "Plain text excerpt from notes.txt."
    assert text_card.snippets and "normalize the dataset" in text_card.snippets[0]

    pdf_card = cards["report.pdf"]
    assert pdf_card.manifest_entry.kind == "pdf"
    assert (
        pdf_card.summary
        == "PDF content not available; please review manually if required."
    )
    assert not pdf_card.snippets or all(not snippet for snippet in pdf_card.snippets)


def test_markdown_embedded_images_are_redacted(tmp_path):
    long_hex = "ABCDEF" * 200  # 1200 characters
    markdown = textwrap.dedent(
        f"""
        # Results

        ![plot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA)

        Here is an embedded blob:

        {long_hex}
        """
    )
    (tmp_path / "report.md").write_text(markdown, encoding="utf-8")

    cards = _build_cards(tmp_path)
    md_card = cards["report.md"]
    rendered = " ".join(md_card.snippets)
    assert "[image-data-redacted]" in rendered
    assert "[hex-image-redacted]" in rendered
    assert "iVBORw0KGgo" not in rendered
    assert long_hex not in rendered


def test_manifest_skips_cache_and_feedback(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    cache_dir = tmp_path / ".mira_cache" / "evidence"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cached.json").write_text("{}", encoding="utf-8")
    (tmp_path / "mira_feedback.yaml").write_text("total_score: 10", encoding="utf-8")

    builder = EvidenceBuilder(policy=EvidencePolicy(max_total_bytes=1_000_000))
    pack = builder.build_evidence(tmp_path)
    manifest_paths = {entry.path.as_posix() for entry in pack.manifest}

    assert "main.py" in manifest_paths
    assert all(".mira_cache" not in path for path in manifest_paths)
    assert "mira_feedback.yaml" not in manifest_paths
