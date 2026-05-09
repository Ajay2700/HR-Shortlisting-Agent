"""
Agent State
=============
Defines the LangGraph state schema that flows through the agent graph.
This is the central data structure that all nodes read from and write to.
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from models.jd_schema import ParsedJD
from models.candidate_schema import CandidateProfile
from models.score_schema import CandidateScore, ShortlistReport


class AgentState(TypedDict):
    """
    State schema for the HR Shortlisting Agent graph.
    
    Each field represents a stage of the pipeline.
    LangGraph ensures type-safe state transitions between nodes.
    """
    # Input data
    jd_text: str                                    # Raw JD text
    resume_texts: dict[str, str]                    # {filename: raw_text}
    linkedin_profiles: dict[str, dict]              # {filename: json_data}
    
    # Parsed data
    parsed_jd: Optional[dict]                       # ParsedJD as dict
    candidate_profiles: list[dict]                  # List of CandidateProfile dicts
    
    # Scoring
    candidate_scores: list[dict]                    # List of CandidateScore dicts
    
    # Report
    report: Optional[dict]                          # ShortlistReport as dict
    report_html: str                                # Generated HTML report
    report_path: str                                # Path to saved report
    
    # Status tracking
    current_stage: str                              # Current pipeline stage
    errors: list[str]                               # Error messages
    messages: Annotated[list, add_messages]          # Message history for LangGraph
