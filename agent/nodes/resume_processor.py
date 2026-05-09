"""
Resume Processor Node
=======================
LangGraph node that processes resumes (PDF/DOCX) and LinkedIn profiles
into structured CandidateProfile objects.

Handles both resume documents and LinkedIn JSON data through
unified profile extraction.
"""

import logging
import re
from agent.state import AgentState
from core.llm_service import llm_service
from core.pii_masker import pii_masker
from security.input_sanitizer import input_sanitizer
from security.audit_logger import audit_logger
from models.candidate_schema import CandidateProfile, WorkExperience, Education, Project

logger = logging.getLogger(__name__)

# ── System Prompt ──────────────────────────────────────────────
RESUME_PARSER_SYSTEM_PROMPT = """You are an expert resume analyst. Parse the following resume text into a structured candidate profile.

STRICT RULES:
1. Extract ONLY information explicitly present in the resume. Do NOT fabricate or assume.
2. For skills: List ALL technical and soft skills mentioned. Technical skills include programming languages, frameworks, tools, databases, cloud platforms. Soft skills include leadership, communication, teamwork etc.
3. For experience: Extract each position with company, title, duration, and description. Estimate years for each role.
4. For education: Extract institution, degree, field, year, and GPA if mentioned.
5. For projects: Extract project names, descriptions, and technologies used.
6. Calculate total_experience_years by summing up individual role durations.
7. For full_text: Concatenate the most important parts — summary, skills, experience descriptions.
8. If information is not available, use empty strings or empty lists. Never fabricate data.
9. Email and phone should be set to '[REDACTED]' for privacy.

Be thorough and accurate. Every detail matters for fair candidate evaluation."""


def process_candidates(state: AgentState) -> dict:
    """
    Process all resume files and LinkedIn profiles into structured CandidateProfiles.
    
    This node:
    1. Iterates through all uploaded resumes and LinkedIn profiles
    2. Sanitizes each document text
    3. Masks PII before LLM processing
    4. Extracts structured profiles using LLM
    5. Combines resume and LinkedIn profiles into a unified list
    """
    logger.info("═" * 50)
    logger.info("NODE: Resume Processor — Extracting candidate profiles")
    logger.info("═" * 50)

    resume_texts = state.get("resume_texts", {})
    linkedin_profiles = state.get("linkedin_profiles", {})
    profiles: list[dict] = []
    errors = list(state.get("errors", []))

    # Process resumes
    for filename, raw_text in resume_texts.items():
        logger.info(f"Processing resume: {filename}")
        try:
            profile = _extract_profile_from_text(raw_text, filename, "resume")
            profiles.append(profile.model_dump())
            audit_logger.log_candidate_processed(
                candidate_name=profile.name,
                source="resume",
                source_file=filename,
            )
            logger.info(f"  ✓ Extracted: {profile.name} ({len(profile.skills)} skills)")
        except Exception as e:
            error_msg = f"Failed to process resume '{filename}': {e}"
            logger.error(f"  ✗ {error_msg}")
            errors.append(error_msg)

    # Process LinkedIn profiles
    for filename, json_data in linkedin_profiles.items():
        logger.info(f"Processing LinkedIn profile: {filename}")
        try:
            from core.linkedin_parser import linkedin_parser
            profile = linkedin_parser.parse(json_data, source_file=filename)
            profiles.append(profile.model_dump())
            audit_logger.log_candidate_processed(
                candidate_name=profile.name,
                source="linkedin",
                source_file=filename,
            )
            logger.info(f"  ✓ Extracted: {profile.name} ({len(profile.skills)} skills)")
        except Exception as e:
            error_msg = f"Failed to process LinkedIn profile '{filename}': {e}"
            logger.error(f"  ✗ {error_msg}")
            errors.append(error_msg)

    logger.info(f"Total profiles extracted: {len(profiles)}")

    return {
        "candidate_profiles": profiles,
        "current_stage": "candidates_processed",
        "errors": errors,
    }


def _extract_profile_from_text(
    raw_text: str,
    source_file: str,
    source: str,
) -> CandidateProfile:
    """Extract a CandidateProfile from raw resume text using LLM."""
    # Sanitize
    sanitized = input_sanitizer.sanitize(raw_text, context=f"resume:{source_file}")
    
    # Mask PII before sending to LLM
    masked_text, pii_detections = pii_masker.mask_text(sanitized)
    if pii_detections:
        audit_logger.log_security_event("PII_MASKED_IN_RESUME", {
            "source_file": source_file,
            "pii_types": [d.pii_type for d in pii_detections],
        })

    user_prompt = (
        f"Parse the following resume into a structured candidate profile.\n"
        f"Source file: {source_file}\n\n"
        f"--- RESUME START ---\n{masked_text}\n--- RESUME END ---"
    )

    try:
        profile = llm_service.invoke_structured(
            system_prompt=RESUME_PARSER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=CandidateProfile,
        )
    except Exception as e:
        logger.warning(f"LLM resume parse failed for {source_file}, using heuristic fallback: {e}")
        profile = _heuristic_extract_profile(masked_text, source_file, source)

    # Ensure source metadata is set
    profile.source = source
    profile.source_file = source_file
    
    # Ensure full_text is populated for embedding
    if not profile.full_text:
        parts = [
            profile.summary,
            " ".join(profile.skills),
            " ".join(w.description for w in profile.work_experience),
            " ".join(p.description for p in profile.projects),
        ]
        profile.full_text = " | ".join(p for p in parts if p)

    return profile


def _heuristic_extract_profile(raw_text: str, source_file: str, source: str) -> CandidateProfile:
    """Rule-based resume parser used when LLM is unavailable."""
    normalized_text = _normalize_resume_text(raw_text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    sections = _split_sections(lines)

    name = _guess_name(lines, source_file)
    skills = _extract_skill_matches(
        normalized_text,
        [
            "python", "java", "javascript", "typescript", "react", "node", "sql",
            "aws", "azure", "gcp", "docker", "kubernetes", "git", "linux",
            "pandas", "numpy", "tensorflow", "pytorch", "django", "flask",
            "fastapi", "mongodb", "postgresql", "mysql", "rest api", "langchain",
            "llm", "rag", "prompt engineering", "huggingface", "qdrant", "faiss",
            "streamlit", "tailwind css", "opencv", "mediapipe",
        ],
    )
    soft_skills = _extract_skill_matches(
        normalized_text,
        ["communication", "leadership", "teamwork", "collaboration", "problem solving", "time management"],
    )
    technical_skills = [s for s in skills if s not in soft_skills]

    summary = _extract_summary(lines, sections)
    projects = _extract_projects(lines, sections)
    education_items = _extract_education(lines, sections)
    work_experience, inferred_years = _extract_work_experience(lines, sections)
    total_exp = _extract_total_experience_years(normalized_text)
    if total_exp == 0.0 and inferred_years > 0:
        total_exp = inferred_years

    full_text = " | ".join(
        part for part in [summary, " ".join(skills), normalized_text[:4000]] if part
    )

    return CandidateProfile(
        name=name,
        email="[REDACTED]",
        phone="[REDACTED]",
        source=source,
        source_file=source_file,
        summary=summary,
        total_experience_years=total_exp,
        skills=skills,
        technical_skills=technical_skills,
        soft_skills=soft_skills,
        work_experience=work_experience,
        education=education_items,
        certifications=_extract_certifications(lines, sections),
        projects=projects,
        languages=_extract_languages(lines, sections),
        full_text=full_text,
    )


def _guess_name(lines: list[str], source_file: str) -> str:
    for line in lines[:15]:
        if "@" in line:
            # Many resumes keep name on same line as email after separators.
            right = re.split(r"@", line, maxsplit=1)[-1]
            tail = re.sub(r"[^A-Za-z ]", " ", right)
            tokens = [t for t in tail.split() if t and t[0].isalpha()]
            if len(tokens) >= 2:
                guess = " ".join(tokens[-3:])
                if all(tok[0].isupper() for tok in guess.split()):
                    return guess

    for line in lines[:12]:
        candidate = re.sub(r"\s+", " ", line).strip()
        if "@" in candidate or "http" in candidate.lower():
            continue
        if any(ch.isdigit() for ch in candidate):
            continue
        if 1 <= len(candidate.split()) <= 5 and all(part.replace(".", "").isalpha() for part in candidate.split()):
            # Avoid section headings
            if candidate.upper() in {"SUMMARY", "PROJECTS", "SKILLS", "EDUCATION"}:
                continue
            return line
    stem = source_file.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    return stem or "Unknown Candidate"


def _extract_skill_matches(text: str, vocab: list[str]) -> list[str]:
    out: list[str] = []
    lower = text.lower()
    for skill in vocab:
        if skill.lower() in lower:
            out.append(skill)
    return out


def _extract_total_experience_years(text: str) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", text, flags=re.IGNORECASE)
    if matches:
        return max(float(m) for m in matches)
    return 0.0


def _extract_summary(lines: list[str], sections: dict[str, list[str]]) -> str:
    if "SUMMARY" in sections and sections["SUMMARY"]:
        return " ".join(sections["SUMMARY"][:4])[:500]
    for line in lines[:50]:
        lower = line.lower()
        if "summary" in lower or "profile" in lower or "objective" in lower:
            return line[:300]
    return lines[0][:300] if lines else ""


def _extract_education(lines: list[str], sections: dict[str, list[str]]) -> list[Education]:
    items: list[Education] = []
    edu_lines = sections.get("EDUCATION", lines)
    for line in edu_lines:
        lower = line.lower()
        if any(k in lower for k in ["bachelor", "master", "b.tech", "m.tech", "b.e", "bsc", "msc", "degree"]):
            year_match = re.search(r"(19|20)\d{2}\s*[–-]\s*(19|20)\d{2}|(19|20)\d{2}", line)
            gpa_match = re.search(r"(cgpa|gpa)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)", line, flags=re.IGNORECASE)
            institution = ""
            degree_line = line[:120]
            if items and not any(k in lower for k in ["bachelor", "master", "b.tech", "m.tech", "b.e", "bsc", "msc"]):
                institution = line[:120]
            items.append(
                Education(
                    institution=institution,
                    degree=degree_line,
                    field="",
                    year=year_match.group(0) if year_match else "",
                    gpa=gpa_match.group(2) if gpa_match else None,
                )
            )
            if len(items) >= 3:
                break
    return items


def _extract_projects(lines: list[str], sections: dict[str, list[str]]) -> list[Project]:
    """Extract projects from dedicated section with title/description/tech parsing."""
    items: list[Project] = []
    project_lines = sections.get("PROJECTS", [])
    if not project_lines:
        # fallback scan entire document if section heading missing
        project_lines = lines

    current_name = ""
    current_desc: list[str] = []
    current_tech: list[str] = []

    def flush():
        nonlocal current_name, current_desc, current_tech
        if current_name or current_desc:
            name = current_name or "Project"
            description = " ".join(current_desc).strip()[:500]
            technologies = list(dict.fromkeys([t for t in current_tech if t]))[:15]
            if description:
                items.append(Project(name=name[:120], description=description, technologies=technologies))
        current_name = ""
        current_desc = []
        current_tech = []

    for line in project_lines:
        clean = line.strip("•- ").strip()
        low = clean.lower()

        if _is_section_heading(clean):
            if items:
                break
            continue

        looks_like_title = (
            len(clean) >= 6
            and len(clean) <= 120
            and not low.startswith("technologies")
            and not low.startswith("built ")
            and not low.startswith("designed ")
            and not low.startswith("implemented ")
            and not low.startswith("developed ")
            and not low.startswith("deployed ")
            and not low.startswith("engineered ")
            and not low.startswith("created ")
            and not low.startswith("worked ")
            and ("(" in clean and ")" in clean or " - " in clean or clean.istitle())
            and not clean.startswith("http")
            and not clean.endswith(".")
        )
        if looks_like_title:
            flush()
            current_name = re.sub(r"\(\s*\d{4}.*?\)", "", clean).strip(" -")
            continue

        if low.startswith("technologies"):
            tech_part = clean.split(":", 1)[1] if ":" in clean else clean
            current_tech.extend([x.strip() for x in tech_part.split(",") if x.strip()])
            continue

        if clean:
            current_desc.append(clean)

    flush()

    # Ultra-fallback if parsing failed but project signals exist
    if not items:
        for line in lines:
            low = line.lower()
            if "project" in low and len(line) > 20:
                items.append(Project(name="Project", description=line[:250], technologies=[]))
            if len(items) >= 4:
                break
    return items


def _extract_work_experience(lines: list[str], sections: dict[str, list[str]]) -> tuple[list[WorkExperience], float]:
    exp_lines = sections.get("EXPERIENCE", [])
    if not exp_lines:
        return [], 0.0

    items: list[WorkExperience] = []
    total_years = 0.0
    for line in exp_lines:
        clean = line.strip("•- ").strip()
        if not clean or _is_section_heading(clean):
            continue
        years = _years_from_date_span(clean)
        if years > 0:
            total_years += years
        if " at " in clean.lower() or years > 0:
            items.append(
                WorkExperience(
                    company="",
                    title=clean[:120],
                    duration=_extract_date_span(clean),
                    years=round(years, 2),
                    description=clean[:300],
                    domain="",
                )
            )
        if len(items) >= 6:
            break
    return items, round(total_years, 2)


def _extract_certifications(lines: list[str], sections: dict[str, list[str]]) -> list[str]:
    cert_lines = sections.get("CERTIFICATIONS", [])
    if not cert_lines:
        cert_lines = [l for l in lines if "certif" in l.lower()]
    out = [l.strip("•- ").strip() for l in cert_lines if l.strip()]
    return out[:8]


def _extract_languages(lines: list[str], sections: dict[str, list[str]]) -> list[str]:
    lang_lines = sections.get("LANGUAGES", [])
    if not lang_lines:
        lang_lines = [l for l in lines if l.lower().startswith("languages")]
    out: list[str] = []
    for line in lang_lines:
        if ":" in line:
            line = line.split(":", 1)[1]
        out.extend([x.strip() for x in line.split(",") if x.strip()])
    return list(dict.fromkeys(out))[:6]


def _normalize_resume_text(text: str) -> str:
    text = text.replace("\u2022", "•").replace("\u00a0", " ")
    # Replace common corrupted symbols from PDF extraction
    text = text.replace("", "•").replace("¯", "•").replace("Ó", "•").replace("½", "•").replace("", "•")
    return text


def _is_section_heading(line: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z&/ ]", "", line).strip().upper()
    headings = {
        "SUMMARY", "PROJECTS", "SKILLS", "EDUCATION", "EXPERIENCE",
        "WORK EXPERIENCE", "CERTIFICATIONS", "LANGUAGES", "ACHIEVEMENTS", "AWARDS",
        "ACHIEVEMENTS AWARDS",
    }
    return cleaned in headings


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "GENERAL"
    sections[current] = []

    for line in lines:
        if _is_section_heading(line):
            current = re.sub(r"[^A-Za-z ]", "", line).strip().upper()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _extract_date_span(text: str) -> str:
    m = re.search(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{4}\s*[–-]\s*(?:Present|Now|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{4}))", text, flags=re.IGNORECASE)
    return m.group(1) if m else ""


def _years_from_date_span(text: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years|yrs|year)", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0
