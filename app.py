"""
HR Resume & LinkedIn Shortlisting Agent — Streamlit UI
========================================================
Premium dashboard for the AI-powered candidate shortlisting system.

Features:
  - Job Description upload (text/file)
  - Resume upload (PDF/DOCX) + LinkedIn JSON upload
  - Real-time pipeline progress tracking
  - Interactive results dashboard with score breakdowns
  - Human-in-the-loop score override capability
  - Report download (HTML)
  - Audit trail viewer

Run: streamlit run app.py
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import validate_config, LLM_MODEL, OPENAI_API_KEY
from core.document_parser import document_parser
from core.linkedin_parser import linkedin_parser
from security.audit_logger import audit_logger
from security.input_sanitizer import input_sanitizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="HR Shortlisting Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header gradient */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white;
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(26, 26, 46, 0.3);
    }
    .main-header h1 {
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        opacity: 0.8;
        font-size: 0.95rem;
        margin-top: 0.3rem;
    }
    
    /* Stat cards */
    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-top: 4px solid #e94560;
    }
    .stat-number {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    .stat-label {
        font-size: 0.75rem;
        color: #636e72;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Score badges */
    .badge-strong-hire {
        background: #00b894;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-hire {
        background: #55efc4;
        color: #00695c;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-maybe {
        background: #6c5ce7;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-no-hire {
        background: #d63031;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    /* Pipeline progress */
    .pipeline-step {
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.3rem 0;
        font-size: 0.85rem;
    }
    .step-done { background: #d4edda; color: #155724; }
    .step-active { background: #cce5ff; color: #004085; }
    .step-pending { background: #f8f9fa; color: #6c757d; }
    
    /* Sidebar styling */
    .sidebar-section {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    
    # ── Header ──────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>🎯 HR Resume & LinkedIn Shortlisting Agent</h1>
        <p>AI-powered candidate evaluation with transparent scoring rubric</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        
        # API Key status
        if OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
            st.success(f"✅ LLM: {LLM_MODEL}")
        else:
            st.error("❌ OPENAI_API_KEY not configured")
            st.info("Add your API key to `.env` file")
            
        st.divider()
        st.markdown("### 📋 Pipeline Stages")
        
        stages = {
            "jd_parsed": "1️⃣ JD Parsing",
            "candidates_processed": "2️⃣ Profile Extraction",
            "scored": "3️⃣ Candidate Scoring",
            "ranked": "4️⃣ Ranking",
            "report_generated": "5️⃣ Report Generation",
        }
        
        current = st.session_state.get("current_stage", "")
        stage_list = list(stages.keys())
        for key, label in stages.items():
            if current == key:
                st.markdown(f'<div class="pipeline-step step-done">✅ {label}</div>', unsafe_allow_html=True)
            elif stage_list.index(key) < stage_list.index(current) if current in stage_list else False:
                st.markdown(f'<div class="pipeline-step step-done">✅ {label}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="pipeline-step step-pending">⬜ {label}</div>', unsafe_allow_html=True)
        
        st.divider()
        st.markdown("### 🔒 Security")
        st.markdown("""
        - ✅ PII masking enabled
        - ✅ Input sanitization active
        - ✅ Prompt injection defense
        - ✅ Output validation
        - ✅ Audit trail logging
        """)

    # ── Main Content Tabs ────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Input & Configure",
        "📊 Results & Rankings",
        "✏️ Human Override",
        "📜 Audit Trail",
    ])

    # ═══════════════════════════════════════════════════════════
    # TAB 1: INPUT & CONFIGURE
    # ═══════════════════════════════════════════════════════════
    with tab1:
        col_jd, col_candidates = st.columns([1, 1])

        # -- JD Input --
        with col_jd:
            st.markdown("### 📄 Job Description")
            jd_input_method = st.radio(
                "Input method:",
                ["📋 Paste text", "📁 Upload file", "📂 Use sample JD"],
                horizontal=True,
                key="jd_method",
            )

            jd_text = ""
            if jd_input_method == "📋 Paste text":
                jd_text = st.text_area(
                    "Paste the Job Description:",
                    height=300,
                    placeholder="Paste the complete job description here...",
                    key="jd_textarea",
                )
            elif jd_input_method == "📁 Upload file":
                jd_file = st.file_uploader(
                    "Upload JD (TXT/PDF/DOCX):",
                    type=["txt", "pdf", "docx"],
                    key="jd_upload",
                )
                if jd_file:
                    if jd_file.name.endswith(".txt"):
                        jd_text = jd_file.read().decode("utf-8")
                    else:
                        jd_text = document_parser.parse(
                            jd_file.name, jd_file.read()
                        )
                    st.success(f"✅ Loaded: {jd_file.name}")
            else:
                sample_path = Path(__file__).parent / "sample_data" / "sample_jd.txt"
                if sample_path.exists():
                    jd_text = sample_path.read_text(encoding="utf-8")
                    st.success("✅ Sample JD loaded")
                else:
                    st.warning("Sample JD file not found")

            if jd_text:
                with st.expander("Preview JD", expanded=False):
                    st.text(jd_text[:1000] + ("..." if len(jd_text) > 1000 else ""))

        # -- Candidate Input --
        with col_candidates:
            st.markdown("### 👥 Candidate Profiles")

            # Resume uploads
            st.markdown("**📄 Resumes (PDF/DOCX)**")
            resume_files = st.file_uploader(
                "Upload resumes:",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                key="resume_upload",
            )

            st.divider()

            # LinkedIn uploads
            st.markdown("**🔗 LinkedIn Profiles (JSON)**")
            linkedin_input = st.radio(
                "LinkedIn input method:",
                ["📁 Upload JSON files", "📂 Use sample profiles"],
                horizontal=True,
                key="linkedin_method",
            )

            linkedin_files = []
            linkedin_data = {}

            if linkedin_input == "📁 Upload JSON files":
                linkedin_files = st.file_uploader(
                    "Upload LinkedIn JSON:",
                    type=["json"],
                    accept_multiple_files=True,
                    key="linkedin_upload",
                )
                for f in (linkedin_files or []):
                    try:
                        data = json.loads(f.read().decode("utf-8"))
                        linkedin_data[f.name] = data
                        st.success(f"✅ {f.name}: {data.get('name', 'Unknown')}")
                    except Exception as e:
                        st.error(f"❌ Failed to parse {f.name}: {e}")
            else:
                sample_dir = Path(__file__).parent / "sample_data" / "linkedin"
                if sample_dir.exists():
                    for json_file in sorted(sample_dir.glob("*.json")):
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        linkedin_data[json_file.name] = data
                    st.success(f"✅ Loaded {len(linkedin_data)} sample LinkedIn profiles")
                else:
                    st.warning("Sample LinkedIn profiles not found")

            # Summary
            total = len(resume_files or []) + len(linkedin_data)
            st.info(f"📊 Total candidates: **{total}** ({len(resume_files or [])} resumes, {len(linkedin_data)} LinkedIn)")

        # -- Run Button --
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            run_disabled = not jd_text or total == 0
            if st.button(
                "🚀 Run Shortlisting Agent",
                type="primary",
                use_container_width=True,
                disabled=run_disabled,
            ):
                _run_agent_pipeline(jd_text, resume_files, linkedin_data)

    # ═══════════════════════════════════════════════════════════
    # TAB 2: RESULTS & RANKINGS
    # ═══════════════════════════════════════════════════════════
    with tab2:
        if "results" not in st.session_state or not st.session_state.results:
            st.info("🔍 Run the agent first to see results here.")
        else:
            _render_results(st.session_state.results)

    # ═══════════════════════════════════════════════════════════
    # TAB 3: HUMAN OVERRIDE
    # ═══════════════════════════════════════════════════════════
    with tab3:
        if "results" not in st.session_state or not st.session_state.results:
            st.info("🔍 Run the agent first to override scores.")
        else:
            _render_override_panel(st.session_state.results)

    # ═══════════════════════════════════════════════════════════
    # TAB 4: AUDIT TRAIL
    # ═══════════════════════════════════════════════════════════
    with tab4:
        _render_audit_trail()


def _run_agent_pipeline(jd_text, resume_files, linkedin_data):
    """Execute the agent pipeline with progress tracking."""
    try:
        validate_config()
    except EnvironmentError as e:
        st.error(f"❌ Configuration Error: {e}")
        return

    progress = st.progress(0, text="Initializing agent...")
    status = st.status("Running Shortlisting Agent...", expanded=True)

    # Step 1: Parse resumes
    status.write("📄 Parsing uploaded resumes...")
    progress.progress(10, text="Parsing resumes...")
    resume_texts = {}
    for f in (resume_files or []):
        try:
            text = document_parser.parse(f.name, f.read())
            safe_name = input_sanitizer.validate_file_name(f.name)
            resume_texts[safe_name] = text
            status.write(f"  ✅ Parsed: {safe_name} ({len(text)} chars)")
        except Exception as e:
            status.write(f"  ❌ Failed: {f.name} — {e}")

    # Step 2: Run agent
    status.write("🤖 Running AI agent pipeline...")
    progress.progress(20, text="Running agent pipeline...")

    from agent.graph import run_agent

    try:
        result = run_agent(
            jd_text=jd_text,
            resume_texts=resume_texts,
            linkedin_profiles=linkedin_data,
        )

        # Update progress through stages
        stage = result.get("current_stage", "")
        progress.progress(100, text="Pipeline complete!")

        errors = result.get("errors", [])
        scores = result.get("candidate_scores", [])

        if errors:
            for err in errors:
                status.write(f"⚠️ {err}")

        if scores:
            status.write(f"✅ Scored {len(scores)} candidates")
            st.session_state.results = result
            st.session_state.current_stage = "report_generated"
            status.update(label="✅ Agent completed successfully!", state="complete")
        else:
            status.update(label="❌ Agent completed with errors", state="error")

    except Exception as e:
        logger.exception("Agent pipeline failed")
        status.update(label=f"❌ Pipeline failed: {e}", state="error")
        progress.progress(100, text="Failed")


def _render_results(results):
    """Render the results dashboard."""
    scores = results.get("candidate_scores", [])
    parsed_jd = results.get("parsed_jd", {})

    if not scores:
        st.warning("No candidate scores available.")
        return

    # -- Stats Row --
    st.markdown("### 📊 Overview")
    shortlisted = [s for s in scores if s.get("recommendation") in ("STRONG HIRE", "HIRE")]
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Candidates", len(scores))
    with c2:
        st.metric("Shortlisted", len(shortlisted))
    with c3:
        top_score = scores[0].get("total_weighted_score", 0) if scores else 0
        st.metric("Top Score", f"{top_score:.2f}/10")
    with c4:
        avg = sum(s.get("total_weighted_score", 0) for s in scores) / len(scores) if scores else 0
        st.metric("Average Score", f"{avg:.2f}/10")

    st.divider()

    # -- Rankings Table --
    st.markdown("### 🏆 Candidate Rankings")
    
    table_data = []
    for i, s in enumerate(scores, 1):
        rec = s.get("recommendation", "N/A")
        table_data.append({
            "Rank": f"#{i}",
            "Name": s.get("candidate_name", "Unknown"),
            "Source": s.get("candidate_source", ""),
            "Score": f"{s.get('total_weighted_score', 0):.2f}",
            "Skills": f"{s.get('skills_match', {}).get('raw_score', 0):.1f}",
            "Exp.": f"{s.get('experience_relevance', {}).get('raw_score', 0):.1f}",
            "Edu.": f"{s.get('education_certs', {}).get('raw_score', 0):.1f}",
            "Projects": f"{s.get('project_portfolio', {}).get('raw_score', 0):.1f}",
            "Comm.": f"{s.get('communication_quality', {}).get('raw_score', 0):.1f}",
            "Recommendation": rec,
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # -- Detailed Cards --
    st.markdown("### 📋 Detailed Breakdown")
    for i, s in enumerate(scores):
        rec = s.get("recommendation", "N/A")
        badge_class = f"badge-{rec.lower().replace(' ', '-')}"
        
        with st.expander(
            f"#{i+1} {s.get('candidate_name', 'Unknown')} — "
            f"{s.get('total_weighted_score', 0):.2f}/10 — {rec}",
            expanded=(i < 3),
        ):
            # Dimension details
            dims = [
                ("Skills Match", "skills_match", 0.30),
                ("Experience Relevance", "experience_relevance", 0.25),
                ("Education & Certs", "education_certs", 0.15),
                ("Project / Portfolio", "project_portfolio", 0.20),
                ("Communication Quality", "communication_quality", 0.10),
            ]
            
            for dim_name, dim_key, weight in dims:
                dim_data = s.get(dim_key, {})
                raw = dim_data.get("raw_score", 0)
                justification = dim_data.get("justification", "N/A")
                
                col_a, col_b, col_c = st.columns([2, 1, 4])
                with col_a:
                    st.markdown(f"**{dim_name}** ({int(weight*100)}%)")
                with col_b:
                    st.progress(raw / 10)
                    st.caption(f"{raw:.1f}/10")
                with col_c:
                    st.caption(justification)

            # Summary
            st.markdown(f"**Summary:** {s.get('overall_summary', 'N/A')}")
            
            if s.get("embedding_similarity") is not None:
                st.caption(f"Semantic Similarity: {s['embedding_similarity']*100:.1f}%")

    # -- Download Report --
    st.divider()
    report_html = results.get("report_html", "")
    if report_html:
        st.download_button(
            label="📥 Download Full Report (HTML)",
            data=report_html,
            file_name=f"shortlist_report_{datetime.now().strftime('%Y%m%d')}.html",
            mime="text/html",
            type="primary",
        )


def _render_override_panel(results):
    """Render the human-in-the-loop override panel."""
    st.markdown("### ✏️ Human-in-the-Loop Score Override")
    st.info(
        "As HR, you can override any candidate's score with a reason. "
        "All overrides are logged in the audit trail for accountability."
    )

    scores = results.get("candidate_scores", [])
    if not scores:
        return

    candidate_names = [s.get("candidate_name", f"Candidate {i}") for i, s in enumerate(scores)]
    selected = st.selectbox("Select candidate to override:", candidate_names)

    if selected:
        idx = candidate_names.index(selected)
        score_data = scores[idx]
        current_score = score_data.get("total_weighted_score", 0)
        current_rec = score_data.get("recommendation", "N/A")

        st.markdown(f"**Current Score:** {current_score:.2f}/10 — **{current_rec}**")

        col1, col2 = st.columns(2)
        with col1:
            new_score = st.slider(
                "New total score:",
                min_value=0.0,
                max_value=10.0,
                value=float(current_score),
                step=0.5,
                key=f"override_score_{idx}",
            )
        with col2:
            override_reason = st.text_area(
                "Reason for override:",
                placeholder="e.g., Strong cultural fit demonstrated in phone screen",
                key=f"override_reason_{idx}",
            )

        if st.button("💾 Apply Override", key=f"override_btn_{idx}"):
            if not override_reason.strip():
                st.error("Please provide a reason for the override.")
            else:
                # Apply override
                score_data["is_overridden"] = True
                score_data["original_score"] = current_score
                score_data["total_weighted_score"] = new_score
                score_data["override_reason"] = override_reason
                
                # Update recommendation
                from security.output_validator import output_validator
                score_data["recommendation"] = output_validator._get_recommendation(new_score)

                # Log override
                audit_logger.log_score_override(
                    candidate_name=selected,
                    original_score=current_score,
                    new_score=new_score,
                    reason=override_reason,
                )

                # Re-sort
                results["candidate_scores"].sort(
                    key=lambda s: s.get("total_weighted_score", 0),
                    reverse=True,
                )

                st.success(
                    f"✅ Override applied: {selected} — "
                    f"{current_score:.2f} → {new_score:.2f} ({score_data['recommendation']})"
                )
                st.rerun()


def _render_audit_trail():
    """Render the audit trail viewer."""
    st.markdown("### 📜 Audit Trail")
    st.caption("Complete log of all agent actions, scores, and overrides.")

    entries = audit_logger.get_session_log()

    if not entries:
        st.info("No audit entries yet. Run the agent to generate logs.")
        return

    # Filter by action type
    actions = sorted(set(e.get("action", "") for e in entries))
    selected_actions = st.multiselect(
        "Filter by action:",
        actions,
        default=actions,
    )

    filtered = [e for e in entries if e.get("action") in selected_actions]

    for entry in filtered:
        severity = entry.get("severity", "INFO")
        icon = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(severity, "📝")
        action = entry.get("action", "")
        ts = entry.get("timestamp", "")
        details = entry.get("details", {})

        with st.expander(f"{icon} {action} — {ts}", expanded=False):
            st.json(details)

    # Export button
    if entries:
        st.download_button(
            "📥 Export Audit Log (JSON)",
            data=audit_logger.export_session(),
            file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
