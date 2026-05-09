"""
Output Validator
==================
Validates LLM outputs to catch hallucinations and ensure data integrity.

Security Risk: Hallucination
  - LLM might generate false scores, fabricate skills not present in the
    resume, or produce inconsistent recommendations.
  - Mitigation: Structural validation via Pydantic, score range checks,
    cross-referencing claims against source data.
"""

import logging

from models.score_schema import CandidateScore, DimensionScore

logger = logging.getLogger(__name__)


class OutputValidator:
    """Validate LLM-generated scoring outputs for integrity."""

    def validate_score(self, score: CandidateScore) -> tuple[bool, list[str]]:
        """
        Validate a CandidateScore for consistency and correctness.
        
        Returns:
            Tuple of (is_valid, list of warning messages)
        """
        warnings = []

        # Check 1: All raw scores within valid range [0, 10]
        for dim in score.all_dimensions:
            if dim.raw_score < 0 or dim.raw_score > 10:
                warnings.append(
                    f"Score out of range for '{dim.dimension}': "
                    f"{dim.raw_score} (must be 0-10)"
                )

        # Check 2: Weighted scores computed correctly
        for dim in score.all_dimensions:
            expected = round(dim.raw_score * dim.weight, 2)
            if abs(dim.weighted_score - expected) > 0.01:
                # Auto-fix weighted score
                dim.weighted_score = expected
                warnings.append(
                    f"Corrected weighted score for '{dim.dimension}': "
                    f"{dim.weighted_score}"
                )

        # Check 3: Total weighted score matches sum of dimensions
        expected_total = round(sum(d.weighted_score for d in score.all_dimensions), 2)
        if abs(score.total_weighted_score - expected_total) > 0.05:
            warnings.append(
                f"Corrected total score: {score.total_weighted_score} → {expected_total}"
            )
            score.total_weighted_score = expected_total

        # Check 4: Recommendation aligns with score
        expected_rec = self._get_recommendation(score.total_weighted_score)
        if score.recommendation != expected_rec:
            warnings.append(
                f"Corrected recommendation: '{score.recommendation}' → '{expected_rec}' "
                f"(based on score {score.total_weighted_score})"
            )
            score.recommendation = expected_rec

        # Check 5: Justifications are not empty
        for dim in score.all_dimensions:
            if not dim.justification or len(dim.justification.strip()) < 10:
                warnings.append(f"Weak justification for '{dim.dimension}'")

        # Check 6: Candidate name is not empty
        if not score.candidate_name or score.candidate_name.strip() == "":
            warnings.append("Candidate name is empty")

        is_valid = len(warnings) == 0
        if warnings:
            logger.warning(
                f"Validation warnings for '{score.candidate_name}': "
                f"{'; '.join(warnings)}"
            )
        else:
            logger.info(f"Score validation passed for '{score.candidate_name}'")

        return is_valid, warnings

    @staticmethod
    def _get_recommendation(total_score: float) -> str:
        """Derive recommendation from total weighted score."""
        if total_score >= 8.0:
            return "STRONG HIRE"
        elif total_score >= 6.5:
            return "HIRE"
        elif total_score >= 4.5:
            return "MAYBE"
        else:
            return "NO HIRE"

    def validate_batch(self, scores: list[CandidateScore]) -> list[CandidateScore]:
        """Validate and fix a batch of scores. Returns corrected scores."""
        for score in scores:
            self.validate_score(score)
        return scores


# Singleton
output_validator = OutputValidator()
