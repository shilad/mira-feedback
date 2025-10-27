"""OpenAI-based grader using pydantic-ai for structured output."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mira.libs.config_loader import ConfigType, get_config
from mira.libs.llm import create_agent
from mira.evidence import EvidenceBuilder, EvidencePolicy
from .models import ComponentFeedback, GradingAdjustment, GradingResult, RubricCriterion
from .rubric_parser import RubricParser

LOG = logging.getLogger(__name__)


def create_grading_agent(configs: ConfigType,
                         model: Optional[str] = None,
                         settings_dict: Optional[Dict[str, Any]] = None) -> Any:
    """
    Create a pydantic-ai Agent configured for grading with OpenAI models.

    This is a wrapper around the general create_agent function with a grading-specific prompt.

    Args:
        configs: Configuration dictionary (required)
        model: Model to use (overrides config value)
        settings_dict: Pydantic AI settings dict (overrides config values)

    Returns:
        Configured Agent for grading
    """
    system_prompt = (
        "You are a helpful grading assistant. Evaluate student submissions "
        "against the provided rubric criteria. Be fair, constructive, and specific "
        "in your feedback. Award partial credit where appropriate. "
        "When situational adjustments are provided, identify which situation best "
        "matches the submission and apply the corresponding adjustment. "
        "Document which adjustment was applied using its name.\n\n"
        "IMPORTANT: The submissions you receive have been anonymized to protect student privacy. "
        "You will see tags like REDACTED_PERSON1, REDACTED_EMAIL1, REDACTED_LOCATION1, etc. "
        "These are placeholders for actual names, emails, and other personally identifiable information. "
        "Do not be confused by these tags or penalize students for their presence - they are added "
        "automatically for privacy protection."
    )

    return create_agent(
        configs=configs,
        model=model,
        settings_dict=settings_dict,
        system_prompt=system_prompt
    )


class SubmissionGrader:
    """Grade submissions using OpenAI with structured output."""

    def __init__(self, configs: ConfigType,
                 model: Optional[str] = None, settings: Optional[Dict[str, Any]] = None):
        """
        Initialize the grader.

        Args:
            configs: Configuration dictionary (required)
            model: Model to use (overrides config value)
            settings: Pydantic AI settings dict (overrides config values)
        """
        self.configs = configs

        # Store model and settings for later use
        self.model_name = model
        self.settings = settings

        self.evidence_policy_overrides: Dict[str, Any] = get_config(
            "grading.evidence_builder.policy", configs, default={}
        ) or {}
        cache_dir_setting = get_config(
            "grading.evidence_builder.cache_dir", configs, default=None
        )
        self.evidence_cache_dir = Path(cache_dir_setting) if cache_dir_setting else None
        self.save_evidence_artifacts = bool(
            get_config("grading.evidence_builder.save_artifacts", configs, default=False)
        )

        # Create the main grading agent using the factory function
        self.agent = create_grading_agent(
            configs=self.configs,
            model=model,
            settings_dict=settings
        )

    async def grade_async(
        self,
        submission_content: str,
        rubric_criteria: List[RubricCriterion],
        *,
        is_evidence: bool = False
    ) -> GradingResult:
        """
        Grade a submission asynchronously.

        Args:
            submission_content: The student's submission text
            rubric_criteria: List of rubric criteria to evaluate against

        Returns:
            GradingResult with scores and feedback
        """
        # Build the grading prompt
        prompt = self._build_prompt(
            submission_content,
            rubric_criteria,
            is_evidence=is_evidence,
        )

        try:
            # Run the agent to get response
            # Settings are already configured in the agent creation
            result = await self.agent.run(prompt)

            # Parse the response to create GradingResult
            # Extract the actual output from the AgentRunResult
            if hasattr(result, 'output'):
                response_text = str(result.output)
            elif hasattr(result, 'data'):
                response_text = str(result.data)
            else:
                response_text = str(result)

            # Look for JSON in the response
            json_match = re.search(r'{.*}', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())

                    # Convert to GradingResult
                    components = {}
                    for name, info in data.get('components', {}).items():
                        # Extract adjustments (now required)
                        adjustments = []
                        if 'adjustments' in info and info['adjustments']:
                            adjustments = [
                                GradingAdjustment(
                                    name=adj.get('name', 'unknown'),
                                    description=adj.get('description', ''),
                                    score_impact=adj.get('score_impact', 0)
                                )
                                for adj in info['adjustments']
                            ]

                        # Generate feedback from adjustments
                        feedback = '; '.join([adj.get('description', '') for adj in info.get('adjustments', [])])
                        if not feedback:
                            feedback = "See adjustments for details"

                        components[name] = ComponentFeedback(
                            score=info.get('score', 0),
                            max_score=info.get('max_score', 0),
                            feedback=feedback,
                            adjustments=adjustments if adjustments else None
                        )

                    return GradingResult(
                        total_score=data.get('total_score', 0),
                        max_score=data.get('max_score', sum(c.max_points for c in rubric_criteria)),
                        components=components,
                        comment=data.get('comment', '')
                    )
                except json.JSONDecodeError:
                    pass

            # If we can't parse JSON, create a basic result
            LOG.warning("Could not parse structured response, creating basic result")
            return self._create_basic_result(rubric_criteria, response_text)

        except Exception as e:
            import traceback
            LOG.error(f"Error during grading: {e}: " + traceback.format_exc())
            # Return a default result on error
            return self._create_error_result(rubric_criteria, str(e))

    def grade(
        self,
        submission_content: str,
        rubric_criteria: List[RubricCriterion],
        *,
        is_evidence: bool = False
    ) -> GradingResult:
        """
        Grade a submission synchronously.

        Args:
            submission_content: The student's submission text
            rubric_criteria: List of rubric criteria to evaluate against

        Returns:
            GradingResult with scores and feedback
        """
        return asyncio.run(
            self.grade_async(
                submission_content,
                rubric_criteria,
                is_evidence=is_evidence,
            )
        )

    def grade_submission_file(self, submission_path: Path, rubric_path: Path) -> GradingResult:
        """
        Grade a submission file against a rubric file.

        Args:
            submission_path: Path to the submission file
            rubric_path: Path to the rubric markdown file

        Returns:
            GradingResult with scores and feedback
        """
        # Parse rubric
        parser = RubricParser()
        rubric_criteria = parser.parse_file(rubric_path)

        # Read submission
        try:
            submission_content = submission_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            LOG.error(f"Error reading submission file: {e}")
            return self._create_error_result(rubric_criteria, f"Could not read submission: {e}")

        # Grade the submission
        return self.grade(submission_content, rubric_criteria)

    def _build_prompt(
        self,
        submission: str,
        criteria: List[RubricCriterion],
        *,
        is_evidence: bool = False
    ) -> str:
        """Build the grading prompt with rubric criteria."""
        criteria_text = "\n".join([
            f"- {c.name} ({c.max_points} points): {c.criteria}"
            for c in criteria
        ])

        submission_label = "SUBMISSION EVIDENCE PACK" if is_evidence else "STUDENT SUBMISSION"
        submission_context = (
            "The material below is an evidence pack generated from the student's submission. "
            "It includes summaries, statistics, and excerpts curated under strict size limits. "
            "Assume the evidence is representative of the submission content."
            if is_evidence
            else "The material below is the student's submission content."
        )

        return f"""Grade this student submission according to the following rubric:

RUBRIC CRITERIA:
{criteria_text}

PRIVACY NOTICE:
The submission below has been anonymized to protect student privacy. Tags like REDACTED_PERSON1,
REDACTED_EMAIL1, REDACTED_LOCATION1, etc. are placeholders for actual personally identifiable
information. Do not penalize students for the presence of these tags.

INSTRUCTIONS:
1. Evaluate the submission against each criterion
2. Assign a score from 0 to the maximum points for each criterion
3. Provide specific, constructive feedback when a criterion is not fully met
4. Write an overall comment summarizing the student's performance
5. All comments should be very brief.
6. If the evidence pack seems insufficient, state that manual review is required and explain why.

Return your evaluation as a JSON object with this structure:
{{
    "total_score": <sum of all component scores>,
    "max_score": {sum(c.max_points for c in criteria)},
    "components": {{
        {', '.join([f'"{c.name}": {{"score": <0-{c.max_points}>, "max_score": {c.max_points}, "adjustments": [<list of adjustments>]}}'
                   for c in criteria])}
    }},
    "comment": "<overall feedback comment for the student>"
}}

Each component MUST have:
- "feedback": A clear explanation of what the student did well or needs to improve
- "adjustments": An array of score changes (can be empty if full credit)

Only create adjustments when deducting points (score_impact < 0):
{{"name": "<adjustment-name>", "description": "<specific issue>", "score_impact": <negative value>}}

Examples:
- Full credit: "feedback": "Well-defined research question about ferris wheel heights", "adjustments": []
- No credit: "feedback": "No research question provided", "adjustments": [{{"name": "missing-question", "description": "Required question not found in submission", "score_impact": -0.5}}]
- Partial credit: "feedback": "Question provided but lacks clarity", "adjustments": [{{"name": "vague-question", "description": "Question needs more specificity", "score_impact": -0.25}}]

{submission_label}:
{submission_context}

{submission}"""

    def _create_basic_result(self, criteria: List[RubricCriterion], response_text: str) -> GradingResult:
        """Create a basic result when structured parsing fails."""
        components = {}
        # Give partial credit when we can't parse the response
        for criterion in criteria:
            components[criterion.name] = ComponentFeedback(
                score=criterion.max_points * 0.5,  # Default to 50% credit
                max_score=criterion.max_points,
                feedback="Automated evaluation - please review manually"
            )

        return GradingResult(
            total_score=sum(c.max_points * 0.5 for c in criteria),
            max_score=sum(c.max_points for c in criteria),
            components=components,
            comment=f"Automated grading completed. Response: {response_text[:200]}..."
        )

    def _create_error_result(self, criteria: List[RubricCriterion], error_msg: str) -> GradingResult:
        """Create an error result when grading fails."""
        components = {}
        for criterion in criteria:
            components[criterion.name] = ComponentFeedback(
                score=0,
                max_score=criterion.max_points,
                feedback=f"Could not evaluate: {error_msg}"
            )

        return GradingResult(
            total_score=0,
            max_score=sum(c.max_points for c in criteria),
            components=components,
            comment=f"Grading error occurred: {error_msg}"
        )

    def _build_evidence_policy(self) -> EvidencePolicy:
        """Apply configuration overrides to the default evidence policy."""
        overrides: Dict[str, Any] = {}
        for field_name in EvidencePolicy.__dataclass_fields__.keys():  # type: ignore[attr-defined]
            if field_name in self.evidence_policy_overrides:
                overrides[field_name] = self.evidence_policy_overrides[field_name]
        return EvidencePolicy(**overrides)

    def _resolve_cache_dir(self, submission_dir: Path) -> Optional[Path]:  # pylint: disable=unused-argument
        """Determine where evidence cache artifacts should live."""
        if self.evidence_cache_dir:
            cache_path = self.evidence_cache_dir
        else:
            cache_path = Path(".mira_cache") / "evidence"

        if not cache_path.is_absolute():
            cache_path = (Path.cwd() / cache_path).resolve()

        return cache_path

    async def _grade_with_evidence_builder_async(
        self,
        submission_dir: Path,
        rubric_criteria: List[RubricCriterion],
    ) -> Optional[GradingResult]:
        """Use the evidence builder pipeline to prepare content before grading."""
        policy = self._build_evidence_policy()
        cache_dir = self._resolve_cache_dir(submission_dir)
        builder = EvidenceBuilder(policy=policy, cache_dir=cache_dir)
        evidence_pack = builder.build_evidence(submission_dir)

        if not evidence_pack.cards:
            LOG.warning("Evidence builder produced zero cards for %s", submission_dir)
            return None

        evidence_text = evidence_pack.render_for_model()

        if self.save_evidence_artifacts:
            artifacts_dir = submission_dir / ".mira_evidence"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / "evidence.json").write_text(
                json.dumps(evidence_pack.to_dict(), indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            (artifacts_dir / "evidence.txt").write_text(
                evidence_text,
                encoding="utf-8",
            )

        return await self.grade_async(
            evidence_text,
            rubric_criteria,
            is_evidence=True,
        )

    async def grade_submission_directory_async(
        self,
        submission_dir: Path,
        rubric_criteria: List[RubricCriterion],
    ) -> GradingResult:
        """
        Grade all files in a submission directory using the evidence builder pipeline.

        This asynchronous version avoids nested event loops when called from batch grading.
        """
        try:
            result = await self._grade_with_evidence_builder_async(submission_dir, rubric_criteria)
            if result:
                return result
            LOG.warning("Evidence builder produced no cards for %s", submission_dir)
        except Exception as exc:  # pylint: disable=broad-except
            import traceback
            LOG.error("Evidence-based grading failed for %s: %s", submission_dir, exc)
            LOG.debug("Evidence failure traceback: %s", traceback.format_exc())
            error_msg = f"Evidence extraction failed: {exc}"
            return self._create_error_result(rubric_criteria, error_msg)

        return self._create_error_result(
            rubric_criteria,
            "Evidence extraction produced no usable content.",
        )

    def grade_submission_directory(self, submission_dir: Path, rubric_criteria: List[RubricCriterion]) -> GradingResult:
        """Synchronous wrapper for grading a submission directory."""
        return asyncio.run(self.grade_submission_directory_async(submission_dir, rubric_criteria))
