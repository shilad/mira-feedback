#!/usr/bin/env python3
"""CLI for the Adaptive Rubric Calibration System."""

import click
import logging
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown

from .rubric_calibrator import RubricCalibrator
from .pattern_analyzer import PatternAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

console = Console()


@click.command()
@click.option(
    '--rubric',
    '-r',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to the original rubric markdown file'
)
@click.option(
    '--grading-results',
    '-g',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to Pass 1 grading results YAML file'
)
@click.option(
    '--output',
    '-o',
    type=click.Path(path_type=Path),
    default=None,
    help='Output path for calibrated rubric (default: calibrated_rubric.md)'
)
@click.option(
    '--report',
    type=click.Path(path_type=Path),
    default=None,
    help='Generate detailed analysis report at this path'
)
@click.option(
    '--show-preview',
    is_flag=True,
    default=True,
    help='Show preview of calibrated rubric'
)
@click.option(
    '--auto-save',
    is_flag=True,
    help='Automatically save without prompting'
)
def main(rubric, grading_results, output, report, show_preview, auto_save):
    """
    Generate a calibrated rubric from grading patterns.

    This command analyzes Pass 1 grading results to identify common patterns
    and generates situational adjustments for more consistent grading.

    Example:
        grade-calibrate -r rubric.md -g grading_pass1.yaml -o calibrated_rubric.md
    """
    console.print("\n[bold cyan]Adaptive Rubric Calibration System[/bold cyan]")
    console.print("=" * 50)

    # Set default output path if not provided
    if output is None:
        output = Path('calibrated_rubric.md')

    # Initialize calibrator
    calibrator = RubricCalibrator()

    # Analyze patterns
    console.print(f"\n[yellow]Analyzing grading patterns from:[/yellow] {grading_results}")
    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze_grading_results(grading_results)

    # Display analysis summary
    console.print(f"\n[green]Analysis Complete![/green]")
    console.print(f"Total submissions analyzed: {analysis.total_submissions}")
    console.print(f"Components found: {len(analysis.components)}")

    # Show component summary table
    table = Table(title="Component Pattern Summary")
    table.add_column("Component", style="cyan")
    table.add_column("Max Points", justify="right")
    table.add_column("Patterns Found", justify="right")
    table.add_column("Most Common", style="yellow")

    for comp_name, component in analysis.components.items():
        patterns_count = len(component.adjustments)
        most_common = component.adjustments[0].name if component.adjustments else "N/A"
        table.add_row(
            comp_name,
            str(component.max_points),
            str(patterns_count),
            most_common
        )

    console.print("\n")
    console.print(table)

    # Generate calibrated rubric
    console.print(f"\n[yellow]Generating calibrated rubric...[/yellow]")
    calibrated_rubric = calibrator.calibrate_rubric(
        rubric,
        grading_results,
        output if auto_save else None
    )

    # Show preview if requested
    if show_preview:
        console.print("\n[bold cyan]Calibrated Rubric Preview:[/bold cyan]")
        console.print("=" * 50)

        # Extract just the Situational Adjustments section for preview
        if "## Situational Adjustments" in calibrated_rubric:
            preview_start = calibrated_rubric.index("## Situational Adjustments")
            preview_text = calibrated_rubric[preview_start:preview_start + 2000]
            if len(calibrated_rubric) > preview_start + 2000:
                preview_text += "\n\n... (preview truncated) ..."
        else:
            preview_text = "No situational adjustments generated."

        md = Markdown(preview_text)
        console.print(md)

    # Generate report if requested
    if report:
        console.print(f"\n[yellow]Generating calibration report...[/yellow]")
        calibrator.generate_calibration_report(analysis, report)
        console.print(f"[green]Report saved to:[/green] {report}")

    # Save calibrated rubric
    if not auto_save:
        console.print(f"\n[bold yellow]Review the calibrated rubric above.[/bold yellow]")
        save = click.confirm(f"Save calibrated rubric to {output}?", default=True)

        if save:
            with open(output, 'w') as f:
                f.write(calibrated_rubric)
            console.print(f"[green]✓ Calibrated rubric saved to:[/green] {output}")
        else:
            console.print("[red]Calibrated rubric not saved.[/red]")
    else:
        console.print(f"[green]✓ Calibrated rubric saved to:[/green] {output}")

    # Show next steps
    console.print("\n[bold cyan]Next Steps:[/bold cyan]")
    console.print("1. Review and edit the calibrated rubric as needed")
    console.print("2. Test on a few sample submissions")
    console.print("3. Run regrading with: grade-batch --rubric {} --submissions-dir <path>".format(output))

    console.print("\n[green]Calibration complete![/green]\n")


if __name__ == '__main__':
    main()