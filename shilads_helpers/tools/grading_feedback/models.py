"""Pydantic models for grading feedback structure."""

from pydantic import BaseModel, Field
from typing import Dict


class RubricCriterion(BaseModel):
    """Single rubric criterion parsed from markdown."""
    name: str = Field(description="Name of the grading criterion")
    max_points: float = Field(description="Maximum points for this criterion")
    criteria: str = Field(description="Description of what's being evaluated")


class ComponentFeedback(BaseModel):
    """Feedback for a single rubric component."""
    score: float = Field(description="Points assigned for this component")
    max_score: float = Field(description="Maximum possible points for this component")
    feedback: str = Field(description="Specific feedback for this component")


class GradingResult(BaseModel):
    """Complete grading result that works with any rubric."""
    total_score: float = Field(description="Total points earned")
    max_score: float = Field(description="Maximum possible total points")
    components: Dict[str, ComponentFeedback] = Field(
        description="Feedback for each rubric component, keyed by component name"
    )
    comment: str = Field(description="Overall feedback comment for the student")

    def to_yaml_dict(self) -> dict:
        """Convert to dictionary suitable for YAML serialization."""
        return {
            'total_score': self.total_score,
            'max_score': self.max_score,
            'components': {
                name: {
                    'score': feedback.score,
                    'max_score': feedback.max_score,
                    'feedback': feedback.feedback
                }
                for name, feedback in self.components.items()
            },
            'comment': self.comment
        }