"""Pattern analyzer for extracting grading patterns from Pass 1 results."""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from datetime import datetime
import re

from .calibration_models import (
    SituationalAdjustment,
    CalibratedComponent,
    CalibrationAnalysis
)

LOG = logging.getLogger(__name__)


class PatternAnalyzer:
    """Analyzes grading results to identify patterns and generate adjustments."""

    def __init__(self):
        """Initialize the pattern analyzer."""
        self.component_patterns = defaultdict(lambda: defaultdict(list))

    def analyze_grading_results(self, grading_file: Path) -> CalibrationAnalysis:
        """
        Analyze a grading results file to extract patterns.

        Args:
            grading_file: Path to the grading results YAML file

        Returns:
            CalibrationAnalysis with discovered patterns
        """
        with open(grading_file, 'r') as f:
            try:
                # Try safe_load first (for plain YAML)
                grading_data = yaml.safe_load(f)
            except yaml.constructor.ConstructorError as e:
                # If safe_load fails due to Python objects, use unsafe_load
                LOG.warning(f"Found Python objects in YAML, using unsafe_load: {e}")
                f.seek(0)  # Reset file pointer
                grading_data = yaml.unsafe_load(f)

                # Convert Python objects to plain dicts if needed
                grading_data = self._convert_python_objects(grading_data)

        submissions = grading_data.get('submissions', [])
        total_submissions = len(submissions)

        if total_submissions == 0:
            LOG.warning("No submissions found in grading file")
            return CalibrationAnalysis(
                total_submissions=0,
                components={},
                timestamp=datetime.now().isoformat(),
                source_file=str(grading_file)
            )

        # Extract patterns from each submission
        component_data = defaultdict(lambda: {
            'scores': [],
            'feedback': [],
            'max_score': 0
        })

        for submission in submissions:
            components = submission.get('components', {})
            for comp_name, comp_data in components.items():
                score = comp_data.get('score', 0)
                max_score = comp_data.get('max_score', 0)
                feedback = comp_data.get('feedback', '')

                component_data[comp_name]['scores'].append(score)
                component_data[comp_name]['feedback'].append((score, feedback))
                component_data[comp_name]['max_score'] = max_score

        # Analyze patterns for each component
        calibrated_components = {}

        for comp_name, data in component_data.items():
            adjustments = self._generate_adjustments_for_component(
                comp_name,
                data['scores'],
                data['feedback'],
                data['max_score'],
                total_submissions
            )

            calibrated_components[comp_name] = CalibratedComponent(
                name=comp_name,
                max_points=data['max_score'],
                base_criteria=self._extract_base_criteria(comp_name),
                adjustments=adjustments
            )

        return CalibrationAnalysis(
            total_submissions=total_submissions,
            components=calibrated_components,
            timestamp=datetime.now().isoformat(),
            source_file=str(grading_file)
        )

    def _generate_adjustments_for_component(
        self,
        comp_name: str,
        scores: List[float],
        feedback_data: List[Tuple[float, str]],
        max_score: float,
        total_submissions: int
    ) -> List[SituationalAdjustment]:
        """Generate situational adjustments for a component based on patterns."""

        adjustments = []

        # Group feedback by score
        score_groups = defaultdict(list)
        for score, feedback in feedback_data:
            score_groups[score].append(feedback)

        # Generate adjustment names based on component and score
        comp_prefix = self._get_component_prefix(comp_name)

        for score, feedbacks in score_groups.items():
            if len(feedbacks) < 2:  # Skip if pattern appears only once
                continue

            # Find common patterns in feedback
            common_pattern = self._find_common_pattern(feedbacks)

            # Determine adjustment type based on score
            if score == 0:
                adj_name = f"{comp_prefix}-missing"
                situation = f"No {comp_name.lower()} provided"
                score_adj = -max_score
            elif score == max_score:
                adj_name = f"{comp_prefix}-good"
                situation = f"Meets all criteria"
                score_adj = 0
            elif score == max_score / 2:
                adj_name = f"{comp_prefix}-partial"
                situation = f"Partially meets criteria"
                score_adj = -max_score / 2
            else:
                adj_name = f"{comp_prefix}-incomplete"
                situation = f"Incomplete or unclear"
                score_adj = score - max_score

            # Extract example from feedback
            example = self._extract_example(feedbacks[0])

            adjustments.append(SituationalAdjustment(
                name=adj_name,
                situation=situation,
                description=common_pattern or "Standard grading applied",
                examples=example,
                score_adjustment=score_adj,
                frequency=f"{len(feedbacks)}/{total_submissions}"
            ))

        # Sort adjustments by frequency (most common first)
        adjustments.sort(key=lambda x: int(x.frequency.split('/')[0]), reverse=True)

        return adjustments

    def _get_component_prefix(self, comp_name: str) -> str:
        """Generate a prefix for adjustment names based on component."""
        comp_lower = comp_name.lower()

        if 'question' in comp_lower:
            return 'question'
        elif 'visual' in comp_lower or 'plot' in comp_lower:
            return 'plot'
        elif 'description' in comp_lower or 'desc' in comp_lower:
            return 'description'
        elif 'ai' in comp_lower:
            return 'ai-statement'
        else:
            # Create prefix from first word
            return comp_lower.split()[0] if comp_lower else 'component'

    def _find_common_pattern(self, feedbacks: List[str]) -> str:
        """Find common patterns in a list of feedback strings."""
        if not feedbacks:
            return ""

        # Find common words/phrases
        words = []
        for feedback in feedbacks:
            words.extend(feedback.lower().split())

        word_counter = Counter(words)
        common_words = [w for w, c in word_counter.most_common(10) if c > len(feedbacks) / 2]

        # Try to reconstruct a pattern
        if 'missing' in common_words or 'no' in common_words:
            return "Component missing or not provided"
        elif 'unclear' in common_words or 'vague' in common_words:
            return "Component present but lacks clarity or specificity"
        elif 'good' in common_words or 'clear' in common_words:
            return "Component meets requirements"
        elif 'partial' in common_words or 'incomplete' in common_words:
            return "Component partially meets requirements"
        else:
            # Use the most common feedback as the pattern
            return feedbacks[0] if feedbacks else ""

    def _extract_example(self, feedback: str) -> str:
        """Extract example text from feedback."""
        # Look for quoted text
        quoted = re.findall(r'"([^"]*)"', feedback)
        if quoted:
            return quoted[0]

        # Look for text in parentheses
        parens = re.findall(r'\(([^)]*)\)', feedback)
        if parens:
            return parens[0]

        # Return first few words if no example found
        words = feedback.split()[:5]
        return ' '.join(words) + '...' if len(words) > 3 else feedback

    def _extract_base_criteria(self, comp_name: str) -> str:
        """Extract base criteria description for a component."""
        # This would ideally come from the original rubric
        # For now, generate a generic description
        comp_lower = comp_name.lower()

        if 'question' in comp_lower:
            return "Clear, simple research question that can be answered with a visualization"
        elif 'visual' in comp_lower:
            return "Appropriate visualization that helps answer the research question"
        elif 'description' in comp_lower:
            return "Two-sentence description explaining the visualization and insights"
        elif 'ai' in comp_lower:
            return "Statement about AI tool usage"
        else:
            return f"Meets criteria for {comp_name}"

    def _convert_python_objects(self, data):
        """
        Recursively convert Python objects to plain dicts/lists.

        Args:
            data: Data structure potentially containing Python objects

        Returns:
            Cleaned data structure with only plain Python types
        """
        if isinstance(data, dict):
            return {k: self._convert_python_objects(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_python_objects(item) for item in data]
        elif hasattr(data, '__dict__'):
            # Convert Python object to dict
            obj_dict = data.__dict__.get('__dict__', {})
            if obj_dict:
                return obj_dict
            else:
                # Try to extract attributes directly
                return {
                    'name': getattr(data, 'name', None),
                    'description': getattr(data, 'description', None),
                    'score_impact': getattr(data, 'score_impact', None)
                }
        else:
            return data