"""
Rotating Log Management & PII Redaction Filter for Kuantra Terminal.
Enforces 10MB/50MB log file rotation and zero-leak scrubbing of API keys, tokens, and sensitive credentials.
"""

import os
import sys
import re
import zipfile
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from app.core.paths import DATA_DIR

LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = LOGS_DIR / "kuantra_backend.log"

# Regex Patterns for PII, Secrets & API Tokens
PATTERNS = [
    (r'(?i)(?:api_?key|secret|token|password|auth|bearer)[\s:=]+["'']?([a-zA-Z0-9_\-\.]{12,})["'']?', r'\1', '[REDACTED_SECRET]'),
    (r'sk_live_[a-zA-Z0-9]{20,}', None, '[REDACTED_STRIPE_KEY]'),
    (r'ghp_[a-zA-Z0-9]{20,}', None, '[REDACTED_GITHUB_TOKEN]'),
    (r'Bearer\s+[a-zA-Z0-9\-\._~+/]+=*', None, 'Bearer [REDACTED_TOKEN]'),
    (r'["'']?(?:password|api_key|secret_key|private_key)["'']?\s*:\s*["''][^"'']+["'']', None, '"secret": "[REDACTED]"'),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', None, '[REDACTED_EMAIL]'),
]

def redact_sensitive_text(text: str) -> str:
    """Scans and scrubs API tokens, bearer headers, and PII from log messages."""
    redacted = text
    for pattern, capture_group, replacement in PATTERNS:
        if capture_group:
            def repl(m):
                full = m.group(0)
                secret_part = m.group(1)
                return full.replace(secret_part, replacement)
            redacted = re.sub(pattern, repl, redacted)
        else:
            redacted = re.sub(pattern, replacement, redacted)
    return redacted

class PiiRedactionFilter(logging.Filter):
    """Logging filter that redacts sensitive secrets in record messages."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (redact_sensitive_text(str(v)) if isinstance(v, str) else v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_sensitive_text(str(v)) if isinstance(v, str) else v for v in record.args)
        return True

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures root logger with 10MB rotating file handler and PII scrubber."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    redaction_filter = PiiRedactionFilter()

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    root_logger.addHandler(console_handler)

    # 2. 10MB Rotating File Handler (Max 5 backup files = 50MB)
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE_PATH),
        maxBytes=10 * 1024 * 1024, # 10 MB
        backupCount=5,              # 5 backups = 50MB max
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)
    root_logger.addHandler(file_handler)

    root_logger.info("Kuantra Logging System initialized with 10MB rotation & PII Scrubbing.")
    return root_logger

def export_logs_zip(output_zip_path: Optional[str] = None) -> str:
    """Packages redacted log files into a zip file for support export."""
    target_zip = output_zip_path or str(LOGS_DIR / "kuantra_diagnostics_redacted.zip")
    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(str(LOGS_DIR)):
            for file in files:
                if file.endswith(".log"):
                    file_path = os.path.join(root, file)
                    # Read content, re-verify scrub, write to zip
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        clean_content = redact_sensitive_text(f.read())
                    z.writestr(file, clean_content)
    return target_zip

logger = setup_logging()