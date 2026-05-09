"""
PII Masking Service
====================
Detects and masks Personally Identifiable Information (PII) in text
before sending to cloud LLMs.

Security Mitigation: Resumes contain sensitive PII (emails, phones,
addresses). This service masks PII in prompts sent to external LLMs
while preserving it locally for report generation.

Uses regex-based detection (lightweight, no external dependencies)
with patterns covering common Indian and international PII formats.
"""

import re
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class PIIMask(NamedTuple):
    """A detected PII instance and its mask."""
    original: str
    masked: str
    pii_type: str


class PIIMasker:
    """Detect and mask PII in text for safe LLM processing."""

    # Compiled regex patterns for PII detection
    PATTERNS = {
        "email": re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ),
        "phone": re.compile(
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
        ),
        "aadhaar": re.compile(
            r'\b\d{4}\s?\d{4}\s?\d{4}\b'
        ),
        "pan": re.compile(
            r'\b[A-Z]{5}\d{4}[A-Z]\b'
        ),
        "url": re.compile(
            r'https?://(?:www\.)?[^\s<>\"\']+|www\.[^\s<>\"\']+',
            re.IGNORECASE,
        ),
        "address": re.compile(
            r'\b\d{1,5}\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Blvd|Boulevard|Nagar|Colony|Sector)\b',
            re.IGNORECASE,
        ),
    }

    # Replacement tokens
    MASKS = {
        "email": "[EMAIL_REDACTED]",
        "phone": "[PHONE_REDACTED]",
        "aadhaar": "[AADHAAR_REDACTED]",
        "pan": "[PAN_REDACTED]",
        "url": "[URL_REDACTED]",
        "address": "[ADDRESS_REDACTED]",
    }

    def mask_text(self, text: str) -> tuple[str, list[PIIMask]]:
        """
        Mask all detected PII in text.
        
        Args:
            text: Input text potentially containing PII
            
        Returns:
            Tuple of (masked_text, list of PIIMask detections)
        """
        masked = text
        detections: list[PIIMask] = []

        for pii_type, pattern in self.PATTERNS.items():
            matches = pattern.findall(masked)
            for match in matches:
                if len(match.strip()) < 5:  # Skip very short false positives
                    continue
                mask_token = self.MASKS[pii_type]
                detections.append(PIIMask(
                    original=match,
                    masked=mask_token,
                    pii_type=pii_type,
                ))
                masked = masked.replace(match, mask_token, 1)

        if detections:
            logger.info(
                f"Masked {len(detections)} PII instances: "
                f"{', '.join(d.pii_type for d in detections)}"
            )

        return masked, detections

    def unmask_text(self, masked_text: str, detections: list[PIIMask]) -> str:
        """Restore original PII from masked text (for local report generation only)."""
        restored = masked_text
        for det in detections:
            restored = restored.replace(det.masked, det.original, 1)
        return restored


# Singleton
pii_masker = PIIMasker()
