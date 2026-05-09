"""
Job Description Schema
=======================
Pydantic models for structured JD parsing output.
Enforces type safety and validation on LLM-extracted data.
"""

from pydantic import BaseModel, Field
from typing import Optional


class JDRequirement(BaseModel):
    """A single requirement extracted from the Job Description."""
    category: str = Field(description="Category: 'skill', 'experience', 'education', 'certification', 'soft_skill'")
    requirement: str = Field(description="The specific requirement text")
    priority: str = Field(description="Priority level: 'must_have', 'nice_to_have', 'preferred'")
    years_experience: Optional[int] = Field(default=None, description="Years of experience required, if specified")


class ParsedJD(BaseModel):
    """Structured representation of a parsed Job Description."""
    job_title: str = Field(description="The job title/role")
    department: str = Field(default="", description="Department or team")
    company: str = Field(default="", description="Company name")
    location: str = Field(default="", description="Job location")
    experience_range: str = Field(default="", description="Required experience range, e.g. '3-5 years'")
    
    # Categorized requirements
    technical_skills: list[str] = Field(default_factory=list, description="Required technical skills")
    soft_skills: list[str] = Field(default_factory=list, description="Required soft skills")
    education_requirements: list[str] = Field(default_factory=list, description="Education qualifications required")
    certifications: list[str] = Field(default_factory=list, description="Certifications required or preferred")
    experience_requirements: list[str] = Field(default_factory=list, description="Experience-related requirements")
    responsibilities: list[str] = Field(default_factory=list, description="Key responsibilities of the role")
    
    # Structured requirements list
    requirements: list[JDRequirement] = Field(default_factory=list, description="All requirements in structured format")
    
    # Summary for embedding
    summary_text: str = Field(default="", description="Concatenated summary text for embedding generation")
