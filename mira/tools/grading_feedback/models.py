"""Pydantic models for grading feedback structure."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class RubricCriterion(BaseModel):
    """Single rubric criterion parsed from markdown."""
    name: str = Field(description="Name of the grading criterion")
    max_points: float = Field(description="Maximum points for this criterion")
    criteria: str = Field(description="Description of what's being evaluated")


class GradingAdjustment(BaseModel):
    """An adjustment applied during grading."""
    name: str = Field(description="Human-readable adjustment name (e.g., 'missing-question')")
    description: str = Field(description="Context-specific description of why this adjustment was applied")
    score_impact: float = Field(description="Score change applied (e.g., -0.5 for no credit)")


class ComponentFeedback(BaseModel):
    """Feedback for a single rubric component."""
    score: float = Field(description="Points assigned for this component")
    max_score: float = Field(description="Maximum possible points for this component")
    adjustments: Optional[List[GradingAdjustment]] = Field(
        default=None,
        description="List of adjustments applied to this component"
    )
    # Legacy field - no longer used, adjustments contain the feedback
    feedback: Optional[str] = Field(default=None, description="Deprecated: use adjustments instead")


class GradingResult(BaseModel):
    """Complete grading result that works with any rubric."""
    total_score: float = Field(description="Total points earned")
    max_score: float = Field(description="Maximum possible total points")
    components: Dict[str, ComponentFeedback] = Field(
        description="Feedback for each rubric component, keyed by component name"
    )
    comment: str = Field(description="Overall feedback comment for the student")
    truncation_warnings: Optional[List[str]] = Field(
        default=None,
        description="Warnings if evidence was truncated due to size limits"
    )

    def to_yaml_dict(self) -> dict:
        """Convert to dictionary suitable for YAML serialization."""
        components_dict = {}
        for name, feedback in self.components.items():
            component_data = {
                'score': feedback.score,
                'max_score': feedback.max_score,
            }
            # Include adjustments if present (adjustments contain the feedback details)
            if feedback.adjustments:
                component_data['adjustments'] = [
                    {
                        'name': adj.name,
                        'description': adj.description,
                        'score_impact': adj.score_impact
                    }
                    for adj in feedback.adjustments
                ]
            components_dict[name] = component_data

        result = {
            'total_score': self.total_score,
            'max_score': self.max_score,
            'components': components_dict,
            'comment': self.comment
        }
        if self.truncation_warnings:
            result['truncation_warnings'] = self.truncation_warnings
        return result