"""
LangGraph Agent Orchestrator
===============================
Defines the agent graph using LangGraph's StateGraph.
Implements a deterministic pipeline: JD Parse → Resume Process → Score → Rank → Report.

Architecture: Linear state-machine (not ReAct loop) because:
  - HR screening follows a fixed, auditable pipeline
  - Deterministic flows are easier to debug and explain
  - Human-in-the-loop is handled as a post-processing step via the UI
  - Each node has clear input/output contracts via Pydantic

Agent Flow Diagram:
  ┌──────────┐   ┌──────────────────┐   ┌────────────────┐   ┌────────┐   ┌────────────────┐
  │ JD Parse │──▶│ Resume/LinkedIn  │──▶│ Scoring Engine │──▶│ Ranker │──▶│ Report Gen     │
  │          │   │   Processor      │   │ (LLM+Embed)   │   │        │   │ (HTML Output)  │
  └──────────┘   └──────────────────┘   └────────────────┘   └────────┘   └────────────────┘
"""

import logging
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.jd_parser import parse_jd
from agent.nodes.resume_processor import process_candidates
from agent.nodes.scoring_engine import score_candidates
from agent.nodes.ranker import rank_candidates
from agent.nodes.report_generator import generate_report

logger = logging.getLogger(__name__)


def should_continue(state: AgentState) -> str:
    """Conditional edge: stop on error, continue otherwise."""
    if state.get("current_stage") == "error":
        return "end"
    return "continue"


def build_agent_graph() -> StateGraph:
    """
    Build and compile the LangGraph agent.
    
    Returns a compiled graph ready for invocation.
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("parse_jd", parse_jd)
    graph.add_node("process_candidates", process_candidates)
    graph.add_node("score_candidates", score_candidates)
    graph.add_node("rank_candidates", rank_candidates)
    graph.add_node("generate_report", generate_report)

    # Set entry point
    graph.set_entry_point("parse_jd")

    # Add conditional edges (error handling)
    graph.add_conditional_edges(
        "parse_jd",
        should_continue,
        {"continue": "process_candidates", "end": END},
    )
    graph.add_conditional_edges(
        "process_candidates",
        should_continue,
        {"continue": "score_candidates", "end": END},
    )
    graph.add_conditional_edges(
        "score_candidates",
        should_continue,
        {"continue": "rank_candidates", "end": END},
    )
    graph.add_edge("rank_candidates", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


def run_agent(
    jd_text: str,
    resume_texts: dict[str, str] | None = None,
    linkedin_profiles: dict[str, dict] | None = None,
) -> AgentState:
    """
    Execute the full shortlisting pipeline.
    
    Args:
        jd_text: Raw job description text
        resume_texts: Dict of {filename: extracted_text} for resumes
        linkedin_profiles: Dict of {filename: json_data} for LinkedIn
        
    Returns:
        Final AgentState with all results
    """
    logger.info("=" * 60)
    logger.info("STARTING HR SHORTLISTING AGENT")
    logger.info("=" * 60)

    graph = build_agent_graph()

    initial_state: AgentState = {
        "jd_text": jd_text,
        "resume_texts": resume_texts or {},
        "linkedin_profiles": linkedin_profiles or {},
        "parsed_jd": None,
        "candidate_profiles": [],
        "candidate_scores": [],
        "report": None,
        "report_html": "",
        "report_path": "",
        "current_stage": "starting",
        "errors": [],
        "messages": [],
    }

    # Execute the graph
    final_state = graph.invoke(initial_state)

    logger.info("=" * 60)
    stage = final_state.get("current_stage", "unknown")
    errors = final_state.get("errors", [])
    logger.info(f"AGENT COMPLETE — Stage: {stage}, Errors: {len(errors)}")
    logger.info("=" * 60)

    return final_state
