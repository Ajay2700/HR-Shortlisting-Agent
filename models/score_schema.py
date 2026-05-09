"""
Scoring Schema
===============
Pydantic models for the mandatory scoring rubric output.
Enforces the exact 5-dimension scoring format required by TCI.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class DimensionScore(BaseModel):
    """Score for a single rubric dimension."""
    dimension: str = Field(description="Dimension name")
    weight: float = Field(description="Weight as decimal, e.g. 0.30 for 30%")
    raw_score: float = Field(ge=0, le=10, description="Raw score 0-10")
    weighted_score: float = Field(description="raw_score * weight")
    justification: str = Field(description="One-line justification for this score")
    evidence: list[str] = Field(default_factory=list, description="Specific evidence from candidate profile")

    @field_validator("weighted_score", mode="before")
    @classmethod
    def compute_weighted(cls, v, info):
        """Auto-compute weighted score if not provided correctly."""
        if "raw_score" in info.data and "weight" in info.data:
            expected = round(info.data["raw_score"] * info.data["weight"], 2)
            return expected
        return v


class CandidateScore(BaseModel):
    """Complete scoring result for a single candidate."""
    candidate_name: str = Field(description="Candidate name")
    candidate_source: str = Field(default="resume", description="Source: resume or linkedin")
    source_file: str = Field(default="", description="Original source filename")
    
    # Dimension scores (mandatory 5 dimensions)
    skills_match: DimensionScore = Field(description="Skills Match score (30% weight)")
    experience_relevance: DimensionScore = Field(description="Experience Relevance score (25% weight)")
    education_certs: DimensionScore = Field(description="Education & Certifications score (15% weight)")
    project_portfolio: DimensionScore = Field(description="Project/Portfolio score (20% weight)")
    communication_quality: DimensionScore = Field(description="Communication Quality score (10% weight)")
    
    # Aggregated
    total_weighted_score: float = Field(description="Sum of all weighted scores (0-10 scale)")
    recommendation: str = Field(description="'STRONG HIRE', 'HIRE', 'MAYBE', 'NO HIRE'")
    overall_summary: str = Field(description="2-3 sentence summary of the candidate")
    
    # Semantic similarity (bonus)
    embedding_similarity: Optional[float] = Field(default=None, description="Cosine similarity score 0-1")
    
    # Human override
    is_overridden: bool = Field(default=False, description="Whether HR has overridden this score")
    override_reason: str = Field(default="", description="Reason for override")
    original_score: Optional[float] = Field(default=None, description="Original score before override")

    @property
    def all_dimensions(self) -> list[DimensionScore]:
        return [
            self.skills_match,
            self.experience_relevance,
            self.education_certs,
            self.project_portfolio,
            self.communication_quality,
        ]


class ShortlistReport(BaseModel):
    """Complete shortlist report with all candidates ranked."""
    job_title: str = Field(description="Job title being hired for")
    company: str = Field(default="", description="Company name")
    total_candidates: int = Field(description="Total candidates evaluated")
    shortlisted_count: int = Field(description="Number of candidates recommended")
    
    candidates: list[CandidateScore] = Field(description="All candidates, sorted by score descending")
    
    # Metadata
    model_used: str = Field(default="", description="LLM model used for scoring")
    timestamp: str = Field(default="", description="Report generation timestamp")
    agent_version: str = Field(default="1.0.0", description="Agent version")
