"""
Candidate Schema
=================
Pydantic models for candidate profile data (from resumes and LinkedIn).
"""

from pydantic import BaseModel, Field
from typing import Optional


class WorkExperience(BaseModel):
    """A single work experience entry."""
    company: str = Field(default="", description="Company name")
    title: str = Field(default="", description="Job title")
    duration: str = Field(default="", description="Duration, e.g. 'Jan 2022 - Present'")
    years: float = Field(default=0.0, description="Approximate years in this role")
    description: str = Field(default="", description="Role description and achievements")
    domain: str = Field(default="", description="Industry/domain of the company")


class Education(BaseModel):
    """A single education entry."""
    institution: str = Field(default="", description="Institution name")
    degree: str = Field(default="", description="Degree earned")
    field: str = Field(default="", description="Field of study")
    year: str = Field(default="", description="Graduation year or duration")
    gpa: Optional[str] = Field(default=None, description="GPA if mentioned")


class Project(BaseModel):
    """A single project entry."""
    name: str = Field(default="", description="Project name")
    description: str = Field(default="", description="Project description")
    technologies: list[str] = Field(default_factory=list, description="Technologies used")
    url: Optional[str] = Field(default=None, description="Project URL if available")


class CandidateProfile(BaseModel):
    """Structured candidate profile extracted from resume or LinkedIn."""
    # Basic Info (PII - handled carefully)
    name: str = Field(description="Candidate full name")
    email: str = Field(default="[REDACTED]", description="Email address")
    phone: str = Field(default="[REDACTED]", description="Phone number")
    location: str = Field(default="", description="City/Location")
    source: str = Field(default="resume", description="Source: 'resume' or 'linkedin'")
    source_file: str = Field(default="", description="Original filename")
    
    # Professional Summary
    summary: str = Field(default="", description="Professional summary/headline")
    total_experience_years: float = Field(default=0.0, description="Total years of professional experience")
    
    # Detailed sections
    skills: list[str] = Field(default_factory=list, description="All skills mentioned")
    technical_skills: list[str] = Field(default_factory=list, description="Technical/hard skills")
    soft_skills: list[str] = Field(default_factory=list, description="Soft skills")
    work_experience: list[WorkExperience] = Field(default_factory=list, description="Work experience entries")
    education: list[Education] = Field(default_factory=list, description="Education entries")
    certifications: list[str] = Field(default_factory=list, description="Certifications")
    projects: list[Project] = Field(default_factory=list, description="Projects/portfolio items")
    languages: list[str] = Field(default_factory=list, description="Languages spoken")
    
    # For embedding
    full_text: str = Field(default="", description="Full concatenated profile text for embedding")
