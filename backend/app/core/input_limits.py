"""Explicit resource limits for local untrusted-input boundaries.

These limits are product safety boundaries, not claims about upstream venue
completeness.  Callers must reject an input before parsing or writing it.
"""

MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 100_000
MAX_CSV_FIELD_BYTES = 256 * 1024

MAX_BROKER_JSON_BYTES = 10 * 1024 * 1024
MAX_WEBHOOK_BYTES = 64 * 1024

MAX_BRIDGE_BODY_BYTES = 10 * 1024 * 1024
MAX_BRIDGE_TEXT_BYTES = 256 * 1024
MAX_BRIDGE_FILES = 8

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2_048
MAX_ARCHIVE_MEMBER_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
