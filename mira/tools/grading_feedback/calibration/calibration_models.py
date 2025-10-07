"""Data models for the Adaptive Rubric Calibration System."""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class GradingAdjustment(BaseModel):
    """An adjustment applied to a component during grading."""
    name: str = Field(description="Human-readable adjustment name (e.g., 'missing-question')")
    description: str = Field(description="Context-specific description of why this adjustment was applied")
    score_impact: float = Field(description="Score change applied (e.g., -0.5 for no credit)")


class SituationalAdjustment(BaseModel):
    """A situational adjustment definition in the calibrated rubric."""
    name: str = Field(description="Human-readable adjustment name")
    situation: str = Field(description="Short description of the situation")
    description: str = Field(description="Detailed description of when this applies")
    examples: str = Field(description="Example submissions that match this situation")
    score_adjustment: float = Field(description="Score adjustment to apply")
    frequency: str = Field(description="How often this occurred (e.g., '8/23')")


class CalibratedComponent(BaseModel):
    """A rubric component with its situational adjustments."""
    name: str = Field(description="Component name (e.g., 'Research Question')")
    max_points: float = Field(description="Maximum points for this component")
    base_criteria: str = Field(description="Base rubric criteria description")
    adjustments: List[SituationalAdjustment] = Field(
        default_factory=list,
        description="List of situational adjustments for this component"
    )


class CalibrationAnalysis(BaseModel):
    """Analysis results from grading pattern extraction."""
    total_submissions: int = Field(description="Total number of submissions analyzed")
    components: Dict[str, CalibratedComponent] = Field(
        description="Components with their discovered adjustments"
    )
    timestamp: str = Field(description="When the analysis was performed")
    source_file: Optional[str] = Field(
        default=None,
        description="Path to the grading results file analyzed"
    )