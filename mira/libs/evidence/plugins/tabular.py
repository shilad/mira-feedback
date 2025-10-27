"""Tabular data evidence plugin."""

from __future__ import annotations

import csv
import random
import statistics
from pathlib import Path
from typing import Dict, List, Optional

from ..models import EvidenceCard, EvidencePolicy, ManifestFile
from .base import EvidencePlugin


class CsvFilePlugin(EvidencePlugin):
    supported_kinds = ("tabular-data",)

    def build(
        self,
        submission_root: Path,
        manifest_entry: ManifestFile,
        policy: EvidencePolicy,
    ) -> Optional[EvidenceCard]:
        absolute = submission_root / manifest_entry.path
        delimiter = "\t" if absolute.suffix.lower() == ".tsv" else ","
        try:
            with absolute.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
                reader = csv.reader(handle, delimiter=delimiter)
                rows = []
                for idx, row in enumerate(reader):
                    rows.append(row)
                    if idx >= policy.max_csv_head_rows + policy.max_csv_random_rows:
                        break
        except Exception as exc:  # pylint: disable=broad-except
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary=f"Failed to sample tabular file: {exc}",
                snippets=[],
            )

        if not rows:
            return EvidenceCard(
                manifest_entry=manifest_entry,
                summary="Tabular file appears empty.",
                snippets=[],
            )

        header = rows[0]
        data_rows = rows[1:]
        random.seed(0)
        random_rows = random.sample(
            data_rows,
            k=min(len(data_rows), policy.max_csv_random_rows),
        ) if data_rows else []
        head_rows = data_rows[: policy.max_csv_head_rows]

        stats = summarize_tabular(header, head_rows + random_rows)
        snippets = ["HEAD:\n" + format_csv_rows(header, head_rows)]
        if random_rows:
            snippets.append("SAMPLED ROWS:\n" + format_csv_rows(header, random_rows))

        return EvidenceCard(
            manifest_entry=manifest_entry,
            summary="Tabular dataset sampled with bounded head and random rows.",
            snippets=snippets,
            stats=stats,
        )


def format_csv_rows(header: List[str], rows: List[List[str]]) -> str:
    rows_str = [", ".join(header)]
    for row in rows[:10]:
        rows_str.append(", ".join(row))
    return "\n".join(rows_str)


def summarize_tabular(header: List[str], rows: List[List[str]]) -> Dict[str, object]:
    columns: Dict[str, List[str]] = {name: [] for name in header}
    for row in rows:
        for name, value in zip(header, row):
            columns[name].append(value)

    numeric_summary: Dict[str, Dict[str, float]] = {}
    categorical_example: Dict[str, List[str]] = {}

    for name, values in columns.items():
        numeric_values: List[float] = []
        categorical_values: List[str] = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except ValueError:
                if value:
                    categorical_values.append(value)

        if numeric_values:
            numeric_summary[name] = {
                "count": len(numeric_values),
                "mean": statistics.fmean(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
            }
        if categorical_values:
            categorical_example[name] = categorical_values[:5]

    return {
        "numeric": numeric_summary,
        "categorical": categorical_example,
        "row_count_sampled": len(rows),
    }
