"""
Report Generator Node
=======================
Generates a professional HTML shortlist report using Jinja2 templates.
"""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Template

import config
from agent.state import AgentState
from models.score_schema import CandidateScore, ShortlistReport
from security.audit_logger import audit_logger

logger = logging.getLogger(__name__)


def generate_report(state: AgentState) -> dict:
    """Generate HTML shortlist report from scored candidates."""
    logger.info("NODE: Report Generator — Creating shortlist report")

    scores_data = state.get("candidate_scores", [])
    parsed_jd = state.get("parsed_jd", {})
    errors = list(state.get("errors", []))

    if not scores_data:
        return {
            "errors": errors + ["No scores to generate report"],
            "current_stage": "error",
        }

    # Build ShortlistReport
    shortlisted = [s for s in scores_data if s.get("recommendation") in ("STRONG HIRE", "HIRE")]
    report = ShortlistReport(
        job_title=parsed_jd.get("job_title", "Unknown"),
        company=parsed_jd.get("company", ""),
        total_candidates=len(scores_data),
        shortlisted_count=len(shortlisted),
        candidates=[CandidateScore.model_validate(s) for s in scores_data],
        model_used=config.LLM_MODEL,
        timestamp=datetime.now().isoformat(),
    )

    # Generate HTML
    html = _render_html_report(report, parsed_jd)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"shortlist_report_{timestamp}.html"
    report_path = config.OUTPUT_DIR / report_filename
    report_path.write_text(html, encoding="utf-8")

    audit_logger.log_report_generated(str(report_path), len(scores_data))
    logger.info(f"Report saved: {report_path}")

    return {
        "report": report.model_dump(),
        "report_html": html,
        "report_path": str(report_path),
        "current_stage": "report_generated",
    }


def _render_html_report(report: ShortlistReport, jd_data: dict) -> str:
    """Render HTML report using inline Jinja2 template."""
    template = Template(HTML_REPORT_TEMPLATE)
    return template.render(
        report=report,
        jd=jd_data,
        now=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        enumerate=enumerate,
    )


HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shortlist Report — {{ report.job_title }}</title>
<style>
  :root {
    --primary: #1a1a2e;
    --accent: #e94560;
    --accent2: #0f3460;
    --bg: #f8f9fa;
    --card: #ffffff;
    --text: #2d3436;
    --text-light: #636e72;
    --success: #00b894;
    --warning: #fdcb6e;
    --danger: #d63031;
    --maybe: #6c5ce7;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }
  .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
  
  /* Header */
  .header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--accent2) 100%);
    color: white;
    padding: 40px;
    border-radius: 16px;
    margin-bottom: 30px;
    box-shadow: 0 10px 40px rgba(26, 26, 46, 0.3);
  }
  .header h1 { font-size: 28px; margin-bottom: 8px; }
  .header .subtitle { opacity: 0.85; font-size: 16px; }
  
  /* Stats Grid */
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
  }
  .stat-card {
    background: var(--card);
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border-top: 4px solid var(--accent);
  }
  .stat-card .number { font-size: 36px; font-weight: 700; color: var(--primary); }
  .stat-card .label { font-size: 13px; color: var(--text-light); text-transform: uppercase; letter-spacing: 1px; }
  
  /* Candidate Cards */
  .candidate {
    background: var(--card);
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    overflow: hidden;
  }
  .candidate-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid #eee;
  }
  .candidate-rank {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--primary);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    margin-right: 16px;
    flex-shrink: 0;
  }
  .candidate-name { font-size: 20px; font-weight: 600; }
  .candidate-source { font-size: 12px; color: var(--text-light); }
  
  .badge {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .badge-strong-hire { background: var(--success); color: white; }
  .badge-hire { background: #55efc4; color: #00695c; }
  .badge-maybe { background: var(--maybe); color: white; }
  .badge-no-hire { background: var(--danger); color: white; }
  
  .score-big {
    font-size: 28px;
    font-weight: 700;
    color: var(--primary);
    margin: 0 16px;
  }
  
  /* Dimensions Table */
  .dimensions { padding: 20px 24px; }
  .dimensions table { width: 100%; border-collapse: collapse; }
  .dimensions th {
    text-align: left;
    padding: 10px 12px;
    background: var(--bg);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-light);
  }
  .dimensions td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
  
  .score-bar {
    height: 8px;
    background: #eee;
    border-radius: 4px;
    overflow: hidden;
    width: 100px;
    display: inline-block;
    vertical-align: middle;
    margin-right: 8px;
  }
  .score-bar-fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--accent) 0%, var(--success) 100%);
  }
  
  .summary-text {
    padding: 16px 24px;
    background: var(--bg);
    font-style: italic;
    color: var(--text-light);
    font-size: 14px;
  }
  
  .overridden {
    background: #fff3cd;
    padding: 8px 16px;
    border-radius: 6px;
    margin: 8px 24px;
    font-size: 13px;
    border-left: 4px solid var(--warning);
  }
  
  /* Footer */
  .footer {
    text-align: center;
    padding: 30px;
    color: var(--text-light);
    font-size: 12px;
  }
  
  @media print {
    .container { padding: 0; }
    .candidate { break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Candidate Shortlist Report</h1>
    <div class="subtitle">{{ report.job_title }}{% if report.company %} — {{ report.company }}{% endif %}</div>
    <div class="subtitle" style="margin-top:8px;">Generated: {{ now }} | Model: {{ report.model_used }} | Agent v{{ report.agent_version }}</div>
  </div>

  <div class="stats">
    <div class="stat-card">
      <div class="number">{{ report.total_candidates }}</div>
      <div class="label">Total Candidates</div>
    </div>
    <div class="stat-card">
      <div class="number">{{ report.shortlisted_count }}</div>
      <div class="label">Shortlisted</div>
    </div>
    <div class="stat-card">
      <div class="number">{{ report.total_candidates - report.shortlisted_count }}</div>
      <div class="label">Not Recommended</div>
    </div>
    <div class="stat-card">
      <div class="number">{{ "%.1f"|format(report.candidates[0].total_weighted_score) if report.candidates else "N/A" }}</div>
      <div class="label">Top Score</div>
    </div>
  </div>

  {% for candidate in report.candidates %}
  <div class="candidate">
    <div class="candidate-header">
      <div style="display:flex;align-items:center;">
        <div class="candidate-rank">{{ loop.index }}</div>
        <div>
          <div class="candidate-name">{{ candidate.candidate_name }}</div>
          <div class="candidate-source">Source: {{ candidate.candidate_source }} ({{ candidate.source_file }})</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;">
        <div class="score-big">{{ "%.2f"|format(candidate.total_weighted_score) }}</div>
        {% set rec = candidate.recommendation.replace(" ", "-").lower() %}
        <span class="badge badge-{{ rec }}">{{ candidate.recommendation }}</span>
      </div>
    </div>

    {% if candidate.is_overridden %}
    <div class="overridden">
      ⚠️ Score overridden by HR | Original: {{ "%.2f"|format(candidate.original_score) }} | Reason: {{ candidate.override_reason }}
    </div>
    {% endif %}

    <div class="dimensions">
      <table>
        <thead>
          <tr><th>Dimension</th><th>Weight</th><th>Score</th><th>Weighted</th><th>Justification</th></tr>
        </thead>
        <tbody>
          {% for dim in candidate.all_dimensions %}
          <tr>
            <td><strong>{{ dim.dimension }}</strong></td>
            <td>{{ "%.0f"|format(dim.weight * 100) }}%</td>
            <td>
              <div class="score-bar"><div class="score-bar-fill" style="width:{{ dim.raw_score * 10 }}%"></div></div>
              {{ "%.1f"|format(dim.raw_score) }}/10
            </td>
            <td>{{ "%.2f"|format(dim.weighted_score) }}</td>
            <td>{{ dim.justification }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if candidate.embedding_similarity is not none %}
    <div style="padding: 8px 24px; font-size: 12px; color: #636e72;">
      Semantic Similarity: {{ "%.1f"|format(candidate.embedding_similarity * 100) }}%
    </div>
    {% endif %}

    <div class="summary-text">{{ candidate.overall_summary }}</div>
  </div>
  {% endfor %}

  <div class="footer">
    <p>Generated by HR Resume & LinkedIn Shortlisting Agent v{{ report.agent_version }}</p>
    <p>This report is AI-assisted. All recommendations should be reviewed by HR before final decisions.</p>
    <p>Security: PII masked during LLM processing | Audit trail logged | Output validated</p>
  </div>
</div>
</body>
</html>"""
