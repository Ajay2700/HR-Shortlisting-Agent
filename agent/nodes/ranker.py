"""
Ranker Node
=============
Sorts candidates by total weighted score and assigns final rankings.
"""

import logging
from agent.state import AgentState

logger = logging.getLogger(__name__)


def rank_candidates(state: AgentState) -> dict:
    """Rank all scored candidates by total weighted score (descending)."""
    logger.info("NODE: Ranker — Sorting candidates by score")

    scores = state.get("candidate_scores", [])
    if not scores:
        return {
            "errors": state.get("errors", []) + ["No scores available for ranking"],
            "current_stage": "error",
        }

    ranked = sorted(
        scores,
        key=lambda s: s.get("total_weighted_score", 0),
        reverse=True,
    )

    for i, s in enumerate(ranked, 1):
        name = s.get("candidate_name", "Unknown")
        score = s.get("total_weighted_score", 0)
        rec = s.get("recommendation", "N/A")
        logger.info(f"  #{i} {name}: {score:.2f}/10 -> {rec}")

    return {
        "candidate_scores": ranked,
        "current_stage": "ranked",
    }
