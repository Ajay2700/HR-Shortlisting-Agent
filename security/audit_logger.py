"""
Audit Logger
==============
Comprehensive audit trail for all agent actions.
Logs every decision, score, and override for compliance and traceability.

Security Requirement: Full audit trail enables:
  - Accountability for hiring decisions
  - Detection of bias patterns
  - Compliance with HR regulations
  - Debugging and continuous improvement
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class AuditLogger:
    """Structured audit logging for agent operations."""

    def __init__(self):
        self.log_dir = config.LOGS_DIR
        self.log_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"audit_{self.session_id}.jsonl"
        self.entries: list[dict] = []

    def log(
        self,
        action: str,
        details: dict,
        severity: str = "INFO",
    ):
        """
        Log an audit event.
        
        Args:
            action: Action type (e.g., 'JD_PARSED', 'CANDIDATE_SCORED', 'SCORE_OVERRIDDEN')
            details: Action-specific details (no PII in logs!)
            severity: Log level
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "action": action,
            "severity": severity,
            "details": details,
        }
        self.entries.append(entry)

        # Write to JSONL file (append mode for crash safety)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        # Also log to standard logger
        log_func = getattr(logger, severity.lower(), logger.info)
        log_func(f"[AUDIT] {action}: {json.dumps(details, default=str)[:200]}")

    def log_jd_parsed(self, job_title: str, num_requirements: int):
        """Log JD parsing event."""
        self.log("JD_PARSED", {
            "job_title": job_title,
            "num_requirements": num_requirements,
        })

    def log_candidate_processed(self, candidate_name: str, source: str, source_file: str):
        """Log candidate profile processing (no PII details)."""
        self.log("CANDIDATE_PROCESSED", {
            "candidate_name": candidate_name,
            "source": source,
            "source_file": source_file,
        })

    def log_candidate_scored(
        self,
        candidate_name: str,
        total_score: float,
        recommendation: str,
        dimension_scores: dict,
    ):
        """Log scoring result."""
        self.log("CANDIDATE_SCORED", {
            "candidate_name": candidate_name,
            "total_score": total_score,
            "recommendation": recommendation,
            "dimension_scores": dimension_scores,
        })

    def log_score_override(
        self,
        candidate_name: str,
        original_score: float,
        new_score: float,
        reason: str,
        overridden_by: str = "HR",
    ):
        """Log human override of a score."""
        self.log("SCORE_OVERRIDDEN", {
            "candidate_name": candidate_name,
            "original_score": original_score,
            "new_score": new_score,
            "reason": reason,
            "overridden_by": overridden_by,
        }, severity="WARNING")

    def log_security_event(self, event_type: str, details: dict):
        """Log security-related events (injection attempts, PII detections)."""
        self.log("SECURITY_EVENT", {
            "event_type": event_type,
            **details,
        }, severity="WARNING")

    def log_report_generated(self, report_path: str, num_candidates: int):
        """Log report generation."""
        self.log("REPORT_GENERATED", {
            "report_path": report_path,
            "num_candidates": num_candidates,
        })

    def get_session_log(self) -> list[dict]:
        """Return all entries from the current session."""
        return self.entries.copy()

    def export_session(self) -> str:
        """Export current session log as JSON string."""
        return json.dumps(self.entries, indent=2, default=str)


# Singleton
audit_logger = AuditLogger()
