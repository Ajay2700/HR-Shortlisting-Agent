"""
LinkedIn Profile Parser
========================
Parses LinkedIn profile data from JSON format.
Supports manually exported LinkedIn JSON (compliant with LinkedIn TOS).

Design Decision: Using manual JSON import instead of web scraping
to avoid violating LinkedIn's Terms of Service — a critical compliance
consideration for any enterprise deployment.
"""

import json
import logging
from pathlib import Path

from models.candidate_schema import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
)

logger = logging.getLogger(__name__)


class LinkedInParser:
    """Parse LinkedIn profile JSON data into CandidateProfile."""

    def parse(self, json_data: str | dict, source_file: str = "linkedin") -> CandidateProfile:
        """
        Parse LinkedIn JSON data into a CandidateProfile.
        
        Accepts either a JSON string or a dict. Handles various LinkedIn
        export formats and normalizes into our standard schema.
        """
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        # Extract work experience
        work_experience = []
        for exp in data.get("experience", data.get("positions", [])):
            work_experience.append(WorkExperience(
                company=exp.get("company", exp.get("companyName", "")),
                title=exp.get("title", exp.get("position", "")),
                duration=exp.get("duration", exp.get("dates", "")),
                years=self._estimate_years(exp.get("duration", "")),
                description=exp.get("description", exp.get("summary", "")),
                domain=exp.get("industry", exp.get("domain", "")),
            ))

        # Extract education
        education = []
        for edu in data.get("education", []):
            education.append(Education(
                institution=edu.get("school", edu.get("institution", "")),
                degree=edu.get("degree", edu.get("degreeName", "")),
                field=edu.get("field", edu.get("fieldOfStudy", "")),
                year=edu.get("year", edu.get("dates", "")),
            ))

        # Extract skills
        skills = data.get("skills", [])
        if isinstance(skills, list) and skills and isinstance(skills[0], dict):
            skills = [s.get("name", str(s)) for s in skills]

        # Extract projects
        projects = []
        for proj in data.get("projects", []):
            projects.append(Project(
                name=proj.get("name", proj.get("title", "")),
                description=proj.get("description", ""),
                technologies=proj.get("technologies", []),
                url=proj.get("url", None),
            ))

        # Compute total experience
        total_exp = sum(w.years for w in work_experience)

        # Build full text for embedding
        text_parts = [
            data.get("headline", ""),
            data.get("summary", data.get("about", "")),
            " ".join(skills),
            " ".join(w.description for w in work_experience),
        ]

        profile = CandidateProfile(
            name=data.get("name", data.get("fullName", "Unknown")),
            email=data.get("email", "[REDACTED]"),
            phone=data.get("phone", "[REDACTED]"),
            location=data.get("location", data.get("locationName", "")),
            source="linkedin",
            source_file=source_file,
            summary=data.get("headline", data.get("summary", "")),
            total_experience_years=total_exp,
            skills=skills,
            technical_skills=[s for s in skills if not self._is_soft_skill(s)],
            soft_skills=[s for s in skills if self._is_soft_skill(s)],
            work_experience=work_experience,
            education=education,
            certifications=data.get("certifications", []),
            projects=projects,
            languages=data.get("languages", []),
            full_text=" | ".join(p for p in text_parts if p),
        )

        logger.info(f"Parsed LinkedIn profile: {profile.name} ({len(skills)} skills, {len(work_experience)} positions)")
        return profile

    def parse_file(self, file_path: str | Path) -> CandidateProfile:
        """Parse a LinkedIn JSON file."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.parse(data, source_file=path.name)

    @staticmethod
    def _estimate_years(duration_str: str) -> float:
        """Estimate years from a duration string like '2 years 3 months'."""
        if not duration_str:
            return 0.0
        years = 0.0
        duration_lower = duration_str.lower()
        import re
        yr_match = re.search(r"(\d+)\s*(?:year|yr)", duration_lower)
        mo_match = re.search(r"(\d+)\s*(?:month|mo)", duration_lower)
        if yr_match:
            years += int(yr_match.group(1))
        if mo_match:
            years += int(mo_match.group(1)) / 12.0
        return round(years, 1)

    @staticmethod
    def _is_soft_skill(skill: str) -> bool:
        """Heuristic to classify soft skills."""
        soft_keywords = {
            "leadership", "communication", "teamwork", "problem solving",
            "management", "presentation", "negotiation", "mentoring",
            "collaboration", "creativity", "adaptability", "critical thinking",
            "time management", "project management", "stakeholder management",
        }
        return skill.lower().strip() in soft_keywords


# Singleton
linkedin_parser = LinkedInParser()
