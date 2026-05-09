"""
JD Parser Node
================
LangGraph node that parses a Job Description into structured requirements.

Prompt Design:
  - System prompt establishes the agent as an expert HR analyst
  - Guardrails prevent the LLM from adding requirements not in the JD
  - Structured output via Pydantic ensures type-safe extraction
"""

import logging
import re
from agent.state import AgentState
from core.llm_service import llm_service
from core.pii_masker import pii_masker
from security.input_sanitizer import input_sanitizer
from security.audit_logger import audit_logger
from models.jd_schema import ParsedJD, JDRequirement

logger = logging.getLogger(__name__)

# ── System Prompt ──────────────────────────────────────────────
# This prompt is shared in documentation as required by the assignment.
JD_PARSER_SYSTEM_PROMPT = """You are an expert HR analyst specializing in Job Description analysis.
Your task is to parse a Job Description and extract ALL requirements into a structured format.

STRICT RULES:
1. Extract ONLY what is explicitly stated in the JD. Do NOT infer or add requirements.
2. Classify each requirement accurately by category and priority.
3. Distinguish between "must_have" (required) and "nice_to_have" (preferred/bonus) requirements.
4. Extract experience ranges as stated (e.g., "3-5 years").
5. Separate technical skills from soft skills accurately.
6. Generate a summary_text by concatenating: job_title + all skills + experience + education requirements.

You must respond with a structured JSON output matching the provided schema exactly.
Do not hallucinate or fabricate any information not present in the JD."""


def parse_jd(state: AgentState) -> dict:
    """
    Parse the Job Description text into structured requirements.
    
    This node:
    1. Sanitizes JD text for prompt injection
    2. Masks any PII found in the JD
    3. Uses LLM to extract structured requirements
    4. Logs the parsing event for audit trail
    """
    logger.info("═" * 50)
    logger.info("NODE: JD Parser — Extracting structured requirements")
    logger.info("═" * 50)

    jd_text = state.get("jd_text", "")
    
    if not jd_text.strip():
        return {
            "errors": state.get("errors", []) + ["JD text is empty"],
            "current_stage": "error",
        }

    # Security: Sanitize input
    sanitized_jd = input_sanitizer.sanitize(jd_text, context="job_description")
    
    # Security: Mask PII in JD before sending to LLM
    masked_jd, pii_detections = pii_masker.mask_text(sanitized_jd)
    if pii_detections:
        audit_logger.log_security_event("PII_DETECTED_IN_JD", {
            "pii_types": [d.pii_type for d in pii_detections],
            "count": len(pii_detections),
        })

    # Invoke LLM with structured output
    user_prompt = f"Parse the following Job Description and extract all requirements:\n\n{masked_jd}"

    try:
        parsed_jd = llm_service.invoke_structured(
            system_prompt=JD_PARSER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=ParsedJD,
        )
        
        # Generate summary text if not populated
        if not parsed_jd.summary_text:
            parts = [
                parsed_jd.job_title,
                " ".join(parsed_jd.technical_skills),
                " ".join(parsed_jd.soft_skills),
                " ".join(parsed_jd.education_requirements),
                " ".join(parsed_jd.experience_requirements),
                parsed_jd.experience_range,
            ]
            parsed_jd.summary_text = " | ".join(p for p in parts if p)

        # Audit log
        audit_logger.log_jd_parsed(
            job_title=parsed_jd.job_title,
            num_requirements=len(parsed_jd.requirements),
        )

        logger.info(
            f"✓ JD parsed: '{parsed_jd.job_title}' — "
            f"{len(parsed_jd.technical_skills)} tech skills, "
            f"{len(parsed_jd.requirements)} total requirements"
        )

        return {
            "parsed_jd": parsed_jd.model_dump(),
            "current_stage": "jd_parsed",
            "errors": state.get("errors", []),
        }

    except Exception as e:
        logger.error(f"JD parsing failed: {e}")
        logger.warning("Falling back to heuristic JD parser (no LLM)")
        fallback_jd = _heuristic_parse_jd(masked_jd)
        fallback_errors = state.get("errors", []) + [
            f"JD parsing used heuristic fallback due to LLM error: {str(e)}"
        ]
        return {
            "parsed_jd": fallback_jd.model_dump(),
            "errors": fallback_errors,
            "current_stage": "jd_parsed",
        }


def _heuristic_parse_jd(jd_text: str) -> ParsedJD:
    """
    Lightweight, rule-based JD parser used when LLM calls fail.
    Keeps the pipeline running under quota/rate-limit outages.
    """
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    title = _extract_job_title(lines)
    exp_range = _extract_experience_range(jd_text)

    technical_skills = _extract_matches(
        jd_text,
        [
            "python", "java", "javascript", "typescript", "react", "node", "sql",
            "aws", "azure", "gcp", "docker", "kubernetes", "git", "langchain",
            "machine learning", "data analysis", "pandas", "numpy", "tensorflow",
            "pytorch",
        ],
    )
    soft_skills = _extract_matches(
        jd_text,
        ["communication", "leadership", "collaboration", "problem solving", "teamwork", "adaptability"],
    )
    education = _extract_lines_by_keywords(
        lines, ["bachelor", "master", "phd", "degree", "education", "b.tech", "m.tech"]
    )
    certs = _extract_lines_by_keywords(lines, ["certification", "certified", "aws", "gcp", "azure"])
    responsibilities = _extract_lines_by_keywords(
        lines, ["responsibilities", "you will", "role includes", "develop", "design", "build", "maintain"]
    )
    experience_requirements = _extract_lines_by_keywords(
        lines, ["experience", "years", "worked", "background"]
    )

    requirements: list[JDRequirement] = []
    for skill in technical_skills:
        requirements.append(JDRequirement(category="skill", requirement=skill, priority="must_have"))
    for skill in soft_skills:
        requirements.append(JDRequirement(category="soft_skill", requirement=skill, priority="preferred"))
    for item in education:
        requirements.append(JDRequirement(category="education", requirement=item, priority="must_have"))
    for item in certs:
        requirements.append(JDRequirement(category="certification", requirement=item, priority="preferred"))
    for item in experience_requirements[:5]:
        requirements.append(JDRequirement(category="experience", requirement=item, priority="must_have"))

    summary_parts = [
        title,
        " ".join(technical_skills),
        " ".join(soft_skills),
        exp_range,
        " ".join(education),
    ]

    return ParsedJD(
        job_title=title or "Unknown Role",
        experience_range=exp_range,
        technical_skills=technical_skills,
        soft_skills=soft_skills,
        education_requirements=education,
        certifications=certs,
        experience_requirements=experience_requirements,
        responsibilities=responsibilities,
        requirements=requirements,
        summary_text=" | ".join(part for part in summary_parts if part),
    )


def _extract_job_title(lines: list[str]) -> str:
    for line in lines[:20]:
        lower = line.lower()
        if any(k in lower for k in ["job title", "position", "role"]):
            parts = re.split(r":|-", line, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return parts[1].strip()
    for line in lines[:10]:
        if 3 <= len(line.split()) <= 8 and not line.endswith("."):
            return line
    return ""


def _extract_experience_range(text: str) -> str:
    match = re.search(r"(\d{1,2}\s*[-+to]{1,3}\s*\d{0,2}\s*\+?\s*years?)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_matches(text: str, vocab: list[str]) -> list[str]:
    found = []
    lower = text.lower()
    for item in vocab:
        if item.lower() in lower:
            found.append(item)
    return found


def _extract_lines_by_keywords(lines: list[str], keywords: list[str], limit: int = 8) -> list[str]:
    out: list[str] = []
    for line in lines:
        line_lower = line.lower()
        if any(k in line_lower for k in keywords):
            out.append(line[:300])
            if len(out) >= limit:
                break
    return out
