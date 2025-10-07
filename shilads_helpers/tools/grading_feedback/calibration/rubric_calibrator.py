"""Rubric calibrator that generates calibrated rubrics from grading patterns."""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .calibration_models import CalibrationAnalysis, CalibratedComponent
from .pattern_analyzer import PatternAnalyzer
from ..rubric_parser import RubricParser

LOG = logging.getLogger(__name__)


class RubricCalibrator:
    """Generates calibrated rubrics with situational adjustments."""

    def __init__(self):
        """Initialize the rubric calibrator."""
        self.analyzer = PatternAnalyzer()
        self.parser = RubricParser()

    def calibrate_rubric(
        self,
        original_rubric_path: Path,
        grading_results_path: Path,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Generate a calibrated rubric from grading results.

        Args:
            original_rubric_path: Path to the original rubric markdown file
            grading_results_path: Path to Pass 1 grading results YAML
            output_path: Optional path to save the calibrated rubric

        Returns:
            The calibrated rubric as a markdown string
        """
        # Read original rubric
        with open(original_rubric_path, 'r') as f:
            original_rubric = f.read()

        # Analyze grading patterns
        LOG.info(f"Analyzing grading patterns from {grading_results_path}")
        analysis = self.analyzer.analyze_grading_results(grading_results_path)

        # Generate calibrated rubric
        calibrated = self._insert_situational_adjustments(original_rubric, analysis)

        # Save if output path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(calibrated)
            LOG.info(f"Calibrated rubric saved to {output_path}")

        return calibrated

    def _insert_situational_adjustments(
        self,
        original_rubric: str,
        analysis: CalibrationAnalysis
    ) -> str:
        """Insert situational adjustments into the rubric."""

        # Check if adjustments already exist
        if "## Situational Adjustments" in original_rubric:
            # Replace existing adjustments
            parts = original_rubric.split("## Situational Adjustments")
            base_part = parts[0]

            # Find where the next major section starts
            remaining = parts[1]
            next_section = re.search(r'\n## (?!Situational)', remaining)
            if next_section:
                end_part = remaining[next_section.start():]
            else:
                end_part = ""
        else:
            # Insert adjustments after base rubric table
            # Find the end of the base rubric table
            table_end = self._find_base_rubric_end(original_rubric)
            if table_end:
                base_part = original_rubric[:table_end]
                end_part = original_rubric[table_end:]
            else:
                base_part = original_rubric
                end_part = ""

        # Generate adjustments section
        adjustments_section = self._generate_adjustments_section(analysis)

        # Combine parts
        return base_part + adjustments_section + end_part

    def _find_base_rubric_end(self, rubric_text: str) -> Optional[int]:
        """Find where the base rubric table ends."""
        # Look for the end of the base rubric table
        # Usually marked by "**Total**" row and followed by blank lines

        lines = rubric_text.split('\n')
        for i, line in enumerate(lines):
            if '**Total**' in line:
                # Found total line, find next non-table line
                for j in range(i + 1, len(lines)):
                    if lines[j] and not lines[j].startswith('|'):
                        return sum(len(l) + 1 for l in lines[:j])
                return sum(len(l) + 1 for l in lines[:i + 2])

        # Fallback: look for end of any table
        in_table = False
        for i, line in enumerate(lines):
            if line.startswith('|'):
                in_table = True
            elif in_table and not line.startswith('|') and line.strip():
                return sum(len(l) + 1 for l in lines[:i])

        return None

    def _generate_adjustments_section(self, analysis: CalibrationAnalysis) -> str:
        """Generate the Situational Adjustments markdown section."""

        sections = [
            "\n## Situational Adjustments",
            f"*Generated from analysis of {analysis.total_submissions} submissions - Review and edit before regrading*\n"
        ]

        # Generate adjustment tables for each component
        for comp_name, component in analysis.components.items():
            if not component.adjustments:
                continue

            sections.append(f"### {comp_name} ({component.max_points} points)")
            sections.append(component.base_criteria)
            sections.append("")

            # Create adjustment table
            sections.append("| Adjustment Name | Situation | Description | Examples | Score Adj. | Freq. |")
            sections.append("|-----------------|-----------|-------------|----------|------------|--------|")

            for adj in component.adjustments:
                # Format score adjustment for display
                score_display = f"{adj.score_adjustment:+.2f}".rstrip('0').rstrip('.')
                if score_display == "+0":
                    score_display = "0"

                # Escape pipe characters in text fields
                situation = adj.situation.replace('|', '\\|')
                description = adj.description.replace('|', '\\|')
                examples = adj.examples.replace('|', '\\|')[:30] + "..." if len(adj.examples) > 30 else adj.examples.replace('|', '\\|')

                sections.append(
                    f"| `{adj.name}` | {situation} | {description} | {examples} | {score_display} | {adj.frequency} |"
                )

            sections.append("")

        return '\n'.join(sections)

    def generate_calibration_report(
        self,
        analysis: CalibrationAnalysis,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Generate a detailed calibration report.

        Args:
            analysis: The calibration analysis results
            output_path: Optional path to save the report

        Returns:
            The report as a markdown string
        """
        report_lines = [
            "# Grading Calibration Analysis Report",
            f"\n**Generated:** {analysis.timestamp}",
            f"**Total Submissions:** {analysis.total_submissions}",
            f"**Source File:** {analysis.source_file or 'N/A'}",
            "\n## Component Analysis\n"
        ]

        for comp_name, component in analysis.components.items():
            report_lines.append(f"### {comp_name}")
            report_lines.append(f"**Max Points:** {component.max_points}")
            report_lines.append(f"**Base Criteria:** {component.base_criteria}")

            if component.adjustments:
                report_lines.append(f"**Patterns Found:** {len(component.adjustments)}")
                report_lines.append("\n**Most Common Adjustments:**")

                for adj in component.adjustments[:3]:  # Show top 3
                    freq_num = int(adj.frequency.split('/')[0])
                    percentage = (freq_num / analysis.total_submissions) * 100
                    report_lines.append(f"- `{adj.name}`: {adj.situation} ({percentage:.1f}% of submissions)")
            else:
                report_lines.append("**No clear patterns found**")

            report_lines.append("")

        report_lines.append("## Recommendations\n")
        report_lines.append("1. Review the generated adjustments for accuracy")
        report_lines.append("2. Modify adjustment names and descriptions as needed")
        report_lines.append("3. Consider combining similar adjustments")
        report_lines.append("4. Remove adjustments that appear too infrequently")
        report_lines.append("5. Test the calibrated rubric on a sample before full regrading")

        report = '\n'.join(report_lines)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            LOG.info(f"Calibration report saved to {output_path}")

        return report