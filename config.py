"""
Configuration Management Module
================================
Centralizes all configuration with validation, defaults, and security.
Loads from .env file using python-dotenv. Never exposes raw secrets in logs.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ── Project Paths ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")
LOGS_DIR = PROJECT_ROOT / "logs"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SAMPLE_DATA_DIR = PROJECT_ROOT / "sample_data"

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ── LLM Configuration ─────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = 0.1  # Low temperature for consistent, deterministic scoring
LLM_MAX_RETRIES = 3

# ── Embedding Configuration ───────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Local, free, fast

# ── Security Configuration ─────────────────────────────────────
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "30"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ── Logging ────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── Scoring Rubric Weights ─────────────────────────────────────
SCORING_WEIGHTS = {
    "skills_match": 0.30,
    "experience_relevance": 0.25,
    "education_certs": 0.15,
    "project_portfolio": 0.20,
    "communication_quality": 0.10,
}

# ── Scoring Thresholds ─────────────────────────────────────────
HIRE_THRESHOLD = 7.0        # Weighted score >= 7.0 → Recommend Hire
NO_HIRE_THRESHOLD = 4.0     # Weighted score < 4.0 → No Hire
# Between thresholds → Maybe / Human Review

# ── Validation ─────────────────────────────────────────────────
def validate_config():
    """Validate critical configuration at startup."""
    errors = []
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
        errors.append("OPENAI_API_KEY is not set. Please configure it in your .env file.")
    if errors:
        raise EnvironmentError(
            "Configuration errors detected:\n" + "\n".join(f"  • {e}" for e in errors)
        )
