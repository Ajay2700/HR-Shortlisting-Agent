"""
Scoring Engine Node
=====================
The core intelligence of the agent. Evaluates each candidate against
the JD using LLM reasoning + embedding similarity.

Implements the mandatory 5-dimension scoring rubric:
  1. Skills Match (30%)
  2. Experience Relevance (25%)
  3. Education & Certifications (15%)
  4. Project / Portfolio (20%)
  5. Communication Quality (10%)

Combines LLM-based qualitative scoring with quantitative embedding
similarity for a hybrid evaluation approach.
"""

import logging
from agent.state import AgentState
from core.llm_service import llm_service
from core import embedding_service
from security.output_validator import output_validator
from security.audit_logger import audit_logger
from models.jd_schema import ParsedJD
from models.candidate_schema import CandidateProfile
from models.score_schema import CandidateScore, DimensionScore

logger = logging.getLogger(__name__)

# ── System Prompt ──────────────────────────────────────────────
SCORING_SYSTEM_PROMPT = """You are a senior HR evaluation specialist. Your task is to score a candidate against a Job Description using the standardized rubric below.

## SCORING RUBRIC (5 Mandatory Dimensions)

### 1. Skills Match (Weight: 30%)
- 0 (Poor): <30% of required skills match
- 5 (Average): 50-70% of required skills match
- 10 (Excellent): >85% of required skills match
Evaluate: Count matching technical skills, frameworks, tools, and languages against JD requirements.

### 2. Experience Relevance (Weight: 25%)
- 0 (Poor): Completely unrelated domain
- 5 (Average): Adjacent/related domain
- 10 (Excellent): Exact domain AND matching seniority level
Evaluate: Domain relevance, years of experience vs requirements, role progression.

### 3. Education & Certifications (Weight: 15%)
- 0 (Poor): Does not meet minimum education requirements
- 5 (Average): Meets minimum requirements
- 10 (Excellent): Exceeds requirements + relevant certifications
Evaluate: Degree level, field match, relevant certifications (AWS, GCP, etc.)

### 4. Project / Portfolio (Weight: 20%)
- 0 (Poor): No evidence of relevant projects
- 5 (Average): 1-2 generic projects
- 10 (Excellent): Strong, relevant portfolio with demonstrable impact
Evaluate: Number, quality, and relevance of projects. Open source, publications count.

### 5. Communication Quality (Weight: 10%)
- 0 (Poor): Poor structure, grammar errors, unclear
- 5 (Average): Adequate clarity and structure
- 10 (Excellent): Crisp, well-structured, impactful presentation
Evaluate: Resume clarity, structure, grammar, conciseness, impact statements.

## STRICT RULES:
1. Score ONLY based on evidence in the candidate profile. Do NOT assume or fabricate.
2. Each raw_score must be a float between 0.0 and 10.0 (one decimal place).
3. weighted_score = raw_score × weight (compute this correctly).
4. Provide a specific, evidence-based one-line justification for each dimension.
5. List specific evidence items (skills, projects, companies) that support each score.
6. total_weighted_score = sum of all weighted_scores.
7. Recommendation based on total_weighted_score:
   - >= 8.0: "STRONG HIRE"
   - >= 6.5: "HIRE"
   - >= 4.5: "MAYBE"
   - < 4.5: "NO HIRE"
8. overall_summary: 2-3 sentences summarizing the candidate's fit.

Be fair, consistent, and evidence-based. Avoid bias based on name, gender, or institution prestige."""


def score_candidates(state: AgentState) -> dict:
    """
    Score all candidates against the parsed JD.
    
    This node:
    1. Loads parsed JD and candidate profiles from state
    2. Computes embedding similarity scores
    3. Uses LLM to evaluate each candidate on 5 dimensions
    4. Validates and corrects all scores
    5. Logs results to audit trail
    """
    logger.info("═" * 50)
    logger.info("NODE: Scoring Engine — Evaluating candidates")
    logger.info("═" * 50)

    parsed_jd_dict = state.get("parsed_jd")
    candidates = state.get("candidate_profiles", [])
    errors = list(state.get("errors", []))

    if not parsed_jd_dict:
        return {
            "errors": errors + ["No parsed JD available for scoring"],
            "current_stage": "error",
        }

    if not candidates:
        return {
            "errors": errors + ["No candidate profiles to score"],
            "current_stage": "error",
        }

    parsed_jd = ParsedJD.model_validate(parsed_jd_dict)
    scores: list[dict] = []

    # Compute embedding similarities in batch for efficiency
    logger.info("Computing embedding similarities...")
    try:
        jd_summary = parsed_jd.summary_text or parsed_jd.job_title
        candidate_texts = [
            c.get("full_text", "") or c.get("summary", "") 
            for c in candidates
        ]
        similarities = embedding_service.batch_similarity(jd_summary, candidate_texts)
        logger.info(f"  ✓ Embedding similarities computed for {len(candidates)} candidates")
    except Exception as e:
        logger.warning(f"  ⚠ Embedding similarity failed, continuing without it: {e}")
        similarities = [None] * len(candidates)

    # Score each candidate
    for idx, candidate_dict in enumerate(candidates):
        candidate = CandidateProfile.model_validate(candidate_dict)
        logger.info(f"Scoring candidate {idx + 1}/{len(candidates)}: {candidate.name}")

        try:
            score = _score_single_candidate(parsed_jd, candidate, similarities[idx])
            
            # Validate and auto-correct
            is_valid, warnings = output_validator.validate_score(score)
            
            # Audit log
            audit_logger.log_candidate_scored(
                candidate_name=score.candidate_name,
                total_score=score.total_weighted_score,
                recommendation=score.recommendation,
                dimension_scores={
                    d.dimension: d.raw_score for d in score.all_dimensions
                },
            )

            scores.append(score.model_dump())
            logger.info(
                f"  ✓ Score: {score.total_weighted_score:.2f}/10 → {score.recommendation}"
            )

        except Exception as e:
            error_msg = f"Scoring failed for '{candidate.name}': {e}"
            logger.error(f"  ✗ {error_msg}")
            errors.append(error_msg)

    # Sort by total score descending
    scores.sort(key=lambda s: s.get("total_weighted_score", 0), reverse=True)

    logger.info(f"Scoring complete: {len(scores)} candidates scored")
    return {
        "candidate_scores": scores,
        "current_stage": "scored",
        "errors": errors,
    }


def _score_single_candidate(
    parsed_jd: ParsedJD,
    candidate: CandidateProfile,
    embedding_sim: float | None,
) -> CandidateScore:
    """Score a single candidate using LLM reasoning."""
    # Build detailed comparison prompt
    jd_summary = _format_jd_for_scoring(parsed_jd)
    candidate_summary = _format_candidate_for_scoring(candidate)

    user_prompt = (
        f"## JOB DESCRIPTION REQUIREMENTS\n{jd_summary}\n\n"
        f"## CANDIDATE PROFILE\n{candidate_summary}\n\n"
        f"Score this candidate against the JD using ALL 5 rubric dimensions. "
        f"Be specific and evidence-based in justifications."
    )

    try:
        score = llm_service.invoke_structured(
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=CandidateScore,
        )
    except Exception as e:
        logger.warning(f"LLM scoring failed for {candidate.name}, using heuristic scoring: {e}")
        score = _heuristic_score_candidate(parsed_jd, candidate, embedding_sim)

    # Attach metadata
    score.candidate_name = candidate.name
    score.candidate_source = candidate.source
    score.source_file = candidate.source_file
    score.embedding_similarity = embedding_sim

    return score


def _heuristic_score_candidate(
    parsed_jd: ParsedJD,
    candidate: CandidateProfile,
    embedding_sim: float | None,
) -> CandidateScore:
    """Deterministic fallback scoring when LLM is unavailable."""
    jd_tech = {s.lower() for s in parsed_jd.technical_skills}
    cand_tech = {s.lower() for s in (candidate.technical_skills or candidate.skills)}
    overlap = sorted(jd_tech.intersection(cand_tech))

    if jd_tech:
        skills_raw = min(10.0, round((len(overlap) / max(1, len(jd_tech))) * 10, 1))
    else:
        skills_raw = 5.0

    exp_target = _min_years_from_jd(parsed_jd)
    cand_years = max(0.0, candidate.total_experience_years or 0.0)
    if exp_target <= 0:
        exp_raw = 6.0 if cand_years > 0 else 4.0
    else:
        exp_raw = min(10.0, round((cand_years / exp_target) * 10, 1))

    edu_text = " ".join(e.degree.lower() + " " + e.field.lower() for e in candidate.education)
    edu_raw = 7.0 if any(k in edu_text for k in ["bachelor", "b.tech", "b.e", "bsc"]) else 4.5
    if any(k in edu_text for k in ["master", "m.tech", "msc", "phd"]):
        edu_raw = 8.5

    project_raw = min(10.0, round(3.0 + len(candidate.projects) * 1.5, 1))
    comm_raw = 7.5 if len(candidate.summary or "") > 40 else 5.5

    dims = [
        DimensionScore(
            dimension="Skills Match",
            weight=0.30,
            raw_score=skills_raw,
            weighted_score=skills_raw * 0.30,
            justification=f"{len(overlap)} matched technical skills from JD.",
            evidence=overlap[:8],
        ),
        DimensionScore(
            dimension="Experience Relevance",
            weight=0.25,
            raw_score=exp_raw,
            weighted_score=exp_raw * 0.25,
            justification=f"Candidate has {cand_years:.1f} years vs target {exp_target:.1f}.",
            evidence=[f"Total experience: {cand_years:.1f} years"],
        ),
        DimensionScore(
            dimension="Education & Certifications",
            weight=0.15,
            raw_score=edu_raw,
            weighted_score=edu_raw * 0.15,
            justification="Education assessed from extracted degree keywords.",
            evidence=[e.degree for e in candidate.education[:3] if e.degree],
        ),
        DimensionScore(
            dimension="Project / Portfolio",
            weight=0.20,
            raw_score=project_raw,
            weighted_score=project_raw * 0.20,
            justification=f"{len(candidate.projects)} projects found in profile.",
            evidence=[p.name for p in candidate.projects[:4] if p.name],
        ),
        DimensionScore(
            dimension="Communication Quality",
            weight=0.10,
            raw_score=comm_raw,
            weighted_score=comm_raw * 0.10,
            justification="Estimated from summary clarity/length in extracted profile.",
            evidence=[(candidate.summary or "")[:120]],
        ),
    ]

    total = round(sum(d.weighted_score for d in dims), 2)
    rec = _recommendation_from_score(total)

    return CandidateScore(
        candidate_name=candidate.name,
        candidate_source=candidate.source,
        source_file=candidate.source_file,
        skills_match=dims[0],
        experience_relevance=dims[1],
        education_certs=dims[2],
        project_portfolio=dims[3],
        communication_quality=dims[4],
        total_weighted_score=total,
        recommendation=rec,
        overall_summary=(
            "Fallback heuristic scoring used because LLM quota was unavailable. "
            f"Top matched skills: {', '.join(overlap[:5]) if overlap else 'none detected'}."
        ),
        embedding_similarity=embedding_sim,
    )


def _min_years_from_jd(jd: ParsedJD) -> float:
    import re
    values: list[float] = []
    texts = [jd.experience_range] + list(jd.experience_requirements)
    for t in texts:
        for m in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", t or "", flags=re.IGNORECASE):
            values.append(float(m))
    return min(values) if values else 0.0


def _recommendation_from_score(total: float) -> str:
    if total >= 8.0:
        return "STRONG HIRE"
    if total >= 6.5:
        return "HIRE"
    if total >= 4.5:
        return "MAYBE"
    return "NO HIRE"


def _format_jd_for_scoring(jd: ParsedJD) -> str:
    """Format JD into a clear comparison prompt."""
    parts = [
        f"**Job Title:** {jd.job_title}",
        f"**Company:** {jd.company}" if jd.company else "",
        f"**Experience Required:** {jd.experience_range}" if jd.experience_range else "",
        f"**Technical Skills Required:** {', '.join(jd.technical_skills)}" if jd.technical_skills else "",
        f"**Soft Skills Required:** {', '.join(jd.soft_skills)}" if jd.soft_skills else "",
        f"**Education:** {', '.join(jd.education_requirements)}" if jd.education_requirements else "",
        f"**Certifications:** {', '.join(jd.certifications)}" if jd.certifications else "",
        f"**Experience Requirements:** {'; '.join(jd.experience_requirements)}" if jd.experience_requirements else "",
    ]
    return "\n".join(p for p in parts if p)


def _format_candidate_for_scoring(c: CandidateProfile) -> str:
    """Format candidate profile into a clear comparison prompt."""
    parts = [
        f"**Name:** {c.name}",
        f"**Summary:** {c.summary}" if c.summary else "",
        f"**Total Experience:** {c.total_experience_years} years",
        f"**Technical Skills:** {', '.join(c.technical_skills)}" if c.technical_skills else "",
        f"**All Skills:** {', '.join(c.skills)}" if c.skills else "",
    ]

    # Work experience
    if c.work_experience:
        parts.append("**Work Experience:**")
        for w in c.work_experience:
            parts.append(f"  - {w.title} at {w.company} ({w.duration}): {w.description[:200]}")

    # Education
    if c.education:
        parts.append("**Education:**")
        for e in c.education:
            parts.append(f"  - {e.degree} in {e.field} from {e.institution} ({e.year})")

    # Certifications
    if c.certifications:
        parts.append(f"**Certifications:** {', '.join(c.certifications)}")

    # Projects
    if c.projects:
        parts.append("**Projects/Portfolio:**")
        for p in c.projects:
            techs = f" [{', '.join(p.technologies)}]" if p.technologies else ""
            parts.append(f"  - {p.name}: {p.description[:150]}{techs}")

    return "\n".join(p for p in parts if p)
