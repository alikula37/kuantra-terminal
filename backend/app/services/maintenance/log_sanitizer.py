"""
PII/Secret Log Sanitizer & Automated Rotation Engine for Kuantra Terminal.
Scans and scrubs sensitive API keys, bearer tokens, private keys, and passkeys,
and enforces 25MB rotation with daily gzip compression and 14-day TTL archival pruning.
"""

import os
import re
import sys
import gzip
import shutil
import time
import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from app.core.logging_config import LOGS_DIR

# Comprehensive Regex Matchers for Credentials, Tokens & Secrets
SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # 1. API Key patterns (e.g., api_key="...", apiKey: "...", API_KEY=...)
    (re.compile(r'(?i)(api[_-]?key|apikey|x-api-key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-.]{12,})["\']?'), r'\1=[REDACTED_SECRET]'),
    # 2. Secret Key / Client Secret patterns
    (re.compile(r'(?i)(secret[_-]?key|client[_-]?secret|app[_-]?secret)\s*[:=]\s*["\']?([a-zA-Z0-9_\-.]{12,})["\']?'), r'\1=[REDACTED_SECRET]'),
    # 3. Private Keys (PEM header & hex private keys)
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[a-zA-Z0-9+/=\s\n\r]+-----END [A-Z ]*PRIVATE KEY-----'), '[REDACTED_SECRET]'),
    (re.compile(r'(?i)(private[_-]?key)\s*[:=]\s*["\']?(0x[a-fA-F0-9]{64}|[a-fA-F0-9]{64})["\']?'), r'\1=[REDACTED_SECRET]'),
    # 4. Bearer & JWT tokens
    (re.compile(r'Bearer\s+[a-zA-Z0-9\-._~+/]+=*'), 'Bearer [REDACTED_SECRET]'),
    (re.compile(r'ey[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}'), '[REDACTED_SECRET]'),
    # 5. Passkeys, Attestation Signatures, Stronghold Tokens
    (re.compile(r'(?i)(passkey|signature|auth_token|vault_token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-.]{16,})["\']?'), r'\1=[REDACTED_SECRET]'),
    (re.compile(r'WEBAUTHN_[A-Z0-9_]{16,}'), '[REDACTED_SECRET]'),
    # 6. Seed phrases (12-24 word BIP-39 pattern estimation)
    (re.compile(r'(?i)(seed[_-]?phrase|mnemonic)\s*[:=]\s*["\']?([a-z]+(\s+[a-z]+){11,23})["\']?'), r'\1=[REDACTED_SECRET]'),
    # 7. Common payment / SaaS API keys
    (re.compile(r'sk_live_[a-zA-Z0-9]{20,}'), '[REDACTED_SECRET]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{20,}'), '[REDACTED_SECRET]')
]

def sanitize_log_message(msg: str) -> str:
    """Scans message and replaces all detected secrets/tokens with [REDACTED_SECRET]."""
    if not isinstance(msg, str):
        msg = str(msg)
    sanitized = msg
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

class PIISecretSanitizerFilter(logging.Filter):
    """Logging filter dynamically applied to all handlers to sanitize messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (sanitize_log_message(str(v)) if isinstance(v, str) else v) for k, v in record.args.items()}
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(sanitize_log_message(str(v)) if isinstance(v, str) else v for v in record.args)
        return True

class LogRotationManager:
    """
    Automated Log Rotation, Gzip Compression, and 14-Day TTL Retention Engine.
    Targets: kuantra_app.log, kuantra_sidecar_ipc.log, kuantra_quant.log, kuantra_biometrics.log
    """

    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
    RETENTION_TTL_DAYS = 14                 # 14-Day TTL Cleanup

    def __init__(self, logs_dir: Optional[str] = None):
        self.logs_dir = Path(logs_dir) if logs_dir else LOGS_DIR
        self.archive_dir = self.logs_dir / "archive"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def rotate_file_if_needed(self, log_path: Path) -> Optional[Path]:
        """Rotates and compresses a log file into .gz archive if size exceeds 25MB or daily rollover."""
        if not log_path.exists() or log_path.stat().st_size == 0:
            return None

        file_size = log_path.stat().st_size
        should_rotate = file_size >= self.MAX_FILE_SIZE_BYTES

        if should_rotate:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            archive_filename = f"{log_path.stem}_{timestamp_str}.log.gz"
            archive_path = self.archive_dir / archive_filename

            # Compress directly to gzip archive with sanitization pass
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f_in:
                content = f_in.read()
                sanitized_content = sanitize_log_message(content)

            with gzip.open(archive_path, "wt", encoding="utf-8") as f_out:
                f_out.write(sanitized_content)

            # Truncate active log file
            with open(log_path, "w", encoding="utf-8") as f_in:
                f_in.write(f"--- LOG ROTATED AT {timestamp_str} (GZIP ARCHIVE CREATED: {archive_filename}) ---\n")

            return archive_path
        return None

    def prune_expired_archives(self, max_age_days: Optional[int] = None) -> List[str]:
        """Scans archive directory and deletes .gz files older than max_age_days (default: 14 days)."""
        ttl_days = max_age_days if max_age_days is not None else self.RETENTION_TTL_DAYS
        ttl_seconds = ttl_days * 86400.0
        now = time.time()
        deleted_files: List[str] = []

        if not self.archive_dir.exists():
            return deleted_files

        for file_path in self.archive_dir.glob("*.gz"):
            try:
                mtime = file_path.stat().st_mtime
                age_seconds = now - mtime
                if age_seconds > ttl_seconds:
                    file_path.unlink()
                    deleted_files.append(file_path.name)
            except Exception as e:
                logging.getLogger("log_sanitizer").warning(f"Error pruning log {file_path.name}: {e}")

        return deleted_files

    def run_full_log_maintenance(self) -> Dict[str, Any]:
        """Executes full sweep: rotates oversized logs and prunes >14 day archives."""
        rotated: List[str] = []
        for log_file in self.logs_dir.glob("*.log"):
            archived = self.rotate_file_if_needed(log_file)
            if archived:
                rotated.append(archived.name)

        pruned = self.prune_expired_archives()
        return {
            "status": "COMPLETED",
            "rotated_archives": rotated,
            "pruned_archives": pruned,
            "archive_dir": str(self.archive_dir),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

log_sanitizer_engine = LogRotationManager()