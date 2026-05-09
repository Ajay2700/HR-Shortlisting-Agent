"""
FastAPI Backend — HR Shortlisting Agent
=======================================
Industry-grade REST API powering the React frontend.

Error contract
--------------
Every response is JSON with:
  { ok: bool, result?: ..., error?: ErrorDetail }

ErrorDetail:
  { code: str, message: str, details?: str }

Error codes
  CONFIG_ERROR      – missing / invalid API key or env variable
  VALIDATION_ERROR  – bad input (empty JD, unsupported file type, too large)
  PARSE_ERROR       – could not extract text from an uploaded document
  QUOTA_EXCEEDED    – LLM API quota exhausted (pipeline ran in fallback mode)
  PIPELINE_ERROR    – unexpected agent failure
  NOT_FOUND         – requested resource does not exist
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config as cfg
from config import validate_config, LLM_MODEL, OPENAI_API_KEY
from core.document_parser import document_parser
from security.audit_logger import audit_logger
from security.input_sanitizer import input_sanitizer
from security.output_validator import output_validator
from agent.graph import run_agent


# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────
MAX_JD_CHARS       = 80_000
MAX_RESUME_SIZE_MB = 10
ALLOWED_RESUME_EXT = {".pdf", ".docx"}
ALLOWED_JD_EXT     = {".txt", ".pdf", ".docx"}
ALLOWED_LI_EXT     = {".json"}
SAMPLE_DIR         = Path(__file__).parent / "sample_data"


# ── App ─────────────────────────────────────────────────────────
app = FastAPI(
    title="HR Shortlisting Agent API",
    version="2.0.0",
    description="Industry-grade candidate shortlisting API with structured errors and audit trail.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Error helpers ────────────────────────────────────────────────
def err(code: str, message: str, details: str = "") -> dict:
    return {"ok": False, "error": {"code": code, "message": message, "details": details}}


def is_quota_error(exc: Exception) -> bool:
    return "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower()


# ── Input validation helpers ─────────────────────────────────────
def _check_file_size(file_bytes: bytes, name: str, max_mb: int = MAX_RESUME_SIZE_MB) -> None:
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(f"File '{name}' is {size_mb:.1f} MB — limit is {max_mb} MB.")


def _check_extension(name: str, allowed: set[str]) -> None:
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise ValueError(
            f"File '{name}' has unsupported type '{ext}'. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """System health check — returns model name and API key status."""
    return {
        "ok": True,
        "version": "2.0.0",
        "model": LLM_MODEL,
        "api_key_configured": bool(OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here"),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/audit", tags=["System"])
def get_audit():
    """Fetch the current session audit trail."""
    entries = audit_logger.get_session_log()
    return {
        "ok": True,
        "count": len(entries),
        "entries": entries,
    }


@app.get("/samples/jd", tags=["Demo"])
def get_sample_jd():
    """Return the bundled sample Job Description text."""
    jd_path = SAMPLE_DIR / "sample_jd.txt"
    if not jd_path.exists():
        return err("NOT_FOUND", "Sample JD file not found on server.")
    return {"ok": True, "jd_text": jd_path.read_text(encoding="utf-8")}


@app.post("/samples/run", tags=["Demo"])
def run_with_samples(jd_text: str = Form(default="")):
    """
    Run the pipeline against all bundled LinkedIn sample profiles.
    Optionally supply a custom JD; falls back to the bundled sample.
    """
    # Resolve JD
    if not jd_text.strip():
        jd_path = SAMPLE_DIR / "sample_jd.txt"
        if not jd_path.exists():
            return err("NOT_FOUND", "Sample JD not found. Please upload a JD.")
        jd_text = jd_path.read_text(encoding="utf-8")

    # Load all sample LinkedIn profiles
    li_dir = SAMPLE_DIR / "linkedin"
    if not li_dir.exists() or not list(li_dir.glob("*.json")):
        return err("NOT_FOUND", "Sample LinkedIn profiles not found on server.")

    linkedin_profiles: dict[str, dict] = {}
    for jf in sorted(li_dir.glob("*.json")):
        try:
            linkedin_profiles[jf.name] = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Skipping malformed sample file {jf.name}: {e}")

    try:
        validate_config()
    except Exception as e:
        return err("CONFIG_ERROR", "API key not configured.", str(e))

    try:
        result = run_agent(jd_text=jd_text, resume_texts={}, linkedin_profiles=linkedin_profiles)
        warnings = [w for w in result.get("errors", []) if w]
        return {
            "ok": True,
            "result": result,
            "warnings": warnings,
            "fallback_mode": any("heuristic" in w.lower() for w in warnings),
        }
    except Exception as e:
        logger.exception("Sample pipeline failed")
        if is_quota_error(e):
            return err("QUOTA_EXCEEDED",
                       "Your OpenAI API quota or rate limit has been exceeded. "
                       "Please review billing/limits in your OpenAI account.",
                       str(e))
        return err("PIPELINE_ERROR", "Unexpected pipeline failure.", str(e))


@app.post("/run", tags=["Core"])
async def run_shortlisting(
    jd_text: str = Form(default=""),
    jd_file: UploadFile | None = File(default=None),
    resume_files: list[UploadFile] = File(default=[]),
    linkedin_files: list[UploadFile] = File(default=[]),
):
    """
    Run the full shortlisting pipeline.

    Accepts JD as text or uploaded file, plus one or more resumes and/or
    LinkedIn JSON exports. Returns ranked candidates and a downloadable report.
    """
    # ── Config check ────────────────────────────────────────────
    try:
        validate_config()
    except Exception as e:
        return err("CONFIG_ERROR",
                   "Server configuration error: OpenAI API key is missing or invalid.",
                   str(e))

    # ── Resolve JD ───────────────────────────────────────────────
    resolved_jd = jd_text.strip()
    if not resolved_jd and jd_file is not None:
        try:
            jd_bytes = await jd_file.read()
            safe_name = input_sanitizer.validate_file_name(jd_file.filename or "jd.txt")
            _check_extension(safe_name, ALLOWED_JD_EXT)
            _check_file_size(jd_bytes, safe_name)
            suffix = Path(safe_name).suffix.lower()
            if suffix == ".txt":
                resolved_jd = jd_bytes.decode("utf-8", errors="ignore")
            else:
                resolved_jd = document_parser.parse(safe_name, jd_bytes)
        except ValueError as e:
            return err("VALIDATION_ERROR", str(e))
        except Exception as e:
            return err("PARSE_ERROR",
                       f"Could not extract text from the JD file '{jd_file.filename}'.",
                       str(e))

    if not resolved_jd:
        return err("VALIDATION_ERROR",
                   "Job Description is required. Paste JD text or upload a TXT/PDF/DOCX file.")

    if len(resolved_jd) > MAX_JD_CHARS:
        return err("VALIDATION_ERROR",
                   f"Job Description is too long ({len(resolved_jd):,} chars). "
                   f"Maximum allowed: {MAX_JD_CHARS:,} characters.")

    # ── Parse resumes ────────────────────────────────────────────
    resume_texts: dict[str, str] = {}
    parse_errors: list[str] = []

    for f in resume_files or []:
        fname = f.filename or "resume.pdf"
        try:
            file_bytes = await f.read()
            safe_name = input_sanitizer.validate_file_name(fname)
            _check_extension(safe_name, ALLOWED_RESUME_EXT)
            _check_file_size(file_bytes, safe_name)
            text = document_parser.parse(safe_name, file_bytes)
            if not text.strip():
                parse_errors.append(f"'{fname}' appears to be empty or unreadable — skipped.")
            else:
                resume_texts[safe_name] = text
                logger.info(f"Parsed resume '{safe_name}': {len(text)} chars")
        except ValueError as e:
            return err("VALIDATION_ERROR", str(e))
        except Exception as e:
            parse_errors.append(f"Could not read '{fname}': {e}")
            logger.warning(f"Resume parse failed for '{fname}': {e}")

    # ── Parse LinkedIn profiles ───────────────────────────────────
    linkedin_profiles: dict[str, dict] = {}

    for f in linkedin_files or []:
        fname = f.filename or "linkedin.json"
        try:
            file_bytes = await f.read()
            safe_name = input_sanitizer.validate_file_name(fname)
            _check_extension(safe_name, ALLOWED_LI_EXT)
            _check_file_size(file_bytes, safe_name)
            payload = json.loads(file_bytes.decode("utf-8", errors="ignore"))
            if not isinstance(payload, dict):
                parse_errors.append(f"'{fname}' is not a valid JSON object — skipped.")
            else:
                linkedin_profiles[safe_name] = payload
                logger.info(f"Loaded LinkedIn profile '{safe_name}': {payload.get('name','?')}")
        except json.JSONDecodeError as e:
            return err("PARSE_ERROR",
                       f"'{fname}' is not valid JSON. Please export your LinkedIn data correctly.",
                       str(e))
        except ValueError as e:
            return err("VALIDATION_ERROR", str(e))
        except Exception as e:
            parse_errors.append(f"Could not load '{fname}': {e}")

    # ── Guard: at least one candidate ───────────────────────────
    if not resume_texts and not linkedin_profiles:
        msg = "No valid candidate files were loaded."
        if parse_errors:
            msg += " Errors: " + " | ".join(parse_errors)
        else:
            msg += " Please upload at least one PDF/DOCX resume or LinkedIn JSON."
        return err("VALIDATION_ERROR", msg)

    # ── Run pipeline ─────────────────────────────────────────────
    logger.info(
        f"Pipeline start — {len(resume_texts)} resumes, {len(linkedin_profiles)} LinkedIn profiles"
    )
    try:
        result = run_agent(
            jd_text=resolved_jd,
            resume_texts=resume_texts,
            linkedin_profiles=linkedin_profiles,
        )
    except Exception as e:
        logger.exception("Agent pipeline crashed")
        if is_quota_error(e):
            return err("QUOTA_EXCEEDED",
                       "Your OpenAI API quota or rate limit has been exceeded. "
                       "Please review billing/limits in your OpenAI account.",
                       str(e))
        return err("PIPELINE_ERROR",
                   "An unexpected error occurred while running the pipeline. Check server logs.",
                   str(e))

    # ── Post-process: collect pipeline warnings ──────────────────
    pipeline_warnings = list(result.get("errors", []))
    if parse_errors:
        pipeline_warnings = parse_errors + pipeline_warnings

    quota_warnings = [w for w in pipeline_warnings if "RESOURCE_EXHAUSTED" in w or "quota" in w.lower()]
    fallback_mode  = any("heuristic" in w.lower() for w in pipeline_warnings)

    scores = result.get("candidate_scores", [])
    if not scores:
        return err("PIPELINE_ERROR",
                   "Pipeline completed but produced no candidate scores. "
                   "Check that your resumes/profiles contain parseable text.",
                   " | ".join(pipeline_warnings[:5]))

    logger.info(f"Pipeline complete — {len(scores)} candidates scored")

    return {
        "ok": True,
        "result": result,
        "warnings": pipeline_warnings,
        "fallback_mode": fallback_mode,
        "quota_warnings": len(quota_warnings) > 0,
        "candidates_parsed": len(resume_texts) + len(linkedin_profiles),
        "candidates_scored": len(scores),
    }


# ── Score override ───────────────────────────────────────────────
class OverrideRequest(BaseModel):
    candidate_name: str
    new_score: float
    reason: str
    scores: list[dict]           # full scores list from the last /run response


@app.post("/override", tags=["Core"])
def apply_override(req: OverrideRequest):
    """
    Apply a human override to a candidate's total score.
    Recalculates recommendation and logs to the audit trail.
    """
    if not req.candidate_name.strip():
        return err("VALIDATION_ERROR", "candidate_name is required.")
    if not (0.0 <= req.new_score <= 10.0):
        return err("VALIDATION_ERROR", "new_score must be between 0.0 and 10.0.")
    if not req.reason.strip():
        return err("VALIDATION_ERROR", "A reason is required for score overrides.")

    updated = False
    scores = [dict(s) for s in req.scores]

    for s in scores:
        if s.get("candidate_name") == req.candidate_name:
            original = s.get("total_weighted_score", 0.0)
            s["is_overridden"]       = True
            s["original_score"]      = original
            s["total_weighted_score"] = req.new_score
            s["override_reason"]     = req.reason
            s["recommendation"]      = output_validator._get_recommendation(req.new_score)
            updated = True
            audit_logger.log_score_override(
                candidate_name=req.candidate_name,
                original_score=original,
                new_score=req.new_score,
                reason=req.reason,
            )
            logger.info(
                f"Override applied: {req.candidate_name} "
                f"{original:.2f} → {req.new_score:.2f} | {req.reason}"
            )
            break

    if not updated:
        return err("NOT_FOUND",
                   f"Candidate '{req.candidate_name}' not found in the provided scores list.")

    # Re-sort by score descending
    scores.sort(key=lambda s: s.get("total_weighted_score", 0), reverse=True)
    return {"ok": True, "scores": scores}
