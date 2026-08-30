# Security Policy & Vulnerability Disclosure

At **Kuantra Terminal**, security and cryptographic data isolation are foundational pillars. Because our terminal orchestrates institutional trading credentials and Direct Market Access (DMA) routes, we employ defense-in-depth security architectures.

---

## 🛡️ Reporting a Vulnerability

If you discover a security vulnerability or sensitive information exposure within Kuantra Terminal, please disclose it responsibly:

- **Email**: `security@kuantra.internal` or open a private GitHub Security Advisory.
- **Acknowledgment SLA**: Within **24 hours**.
- **Assessment & Patch Timeline**: Critical vulnerabilities will be patched within **72 hours**.

Please **do not** report security vulnerabilities via public GitHub issues.

---

## 🔐 Core Security Architectures

### 1. Stronghold Vault & Zero-Plaintext Storage
- All exchange API keys (TwelveData, Polygon, Binance, OKX, FIX DMA) and LLM credentials are encrypted in-memory using **AES-256-GCM**.
- Key derivation utilizes **Argon2id / PBKDF2-HMAC-SHA256** with 100,000 iterations and a unique per-installation cryptographic salt.
- Credentials are never logged to disk, transmitted in plaintext, or serialized in core dumps.

### 2. Automatic PII & Secret Scrubbing
- The rotating log manager continuously filters output streams with high-entropy regex scanners.
- Patterns matching `sk_live_...`, `Bearer ...`, API secret signatures, and account balances are automatically replaced with `[REDACTED_SECRET]` before disk flushing.

### 3. FIDO2 / WebAuthn Hardware Passkey Gating
- High-value order dispatches exceeding **$50,000** require interactive WebAuthn hardware passkey confirmation (TouchID, FaceID, or YubiKey FIDO2 enclave).

### 4. 1-Tap Emergency Circuit-Breaker
- The wearable panic kill-switch immediately cancels open orders, flattens positions at market, and revokes active broker session tokens into a `READ_ONLY_LOCKDOWN` state.