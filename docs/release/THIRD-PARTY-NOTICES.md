# Third-party component inventory (H05 preparation)

Generated: 2026-09-18T11:09:55.627504Z from `backend/requirements.lock` (installed metadata) and
`frontend/package-lock.json` (production dependencies). Raw data:
`artifacts/evidence/p1-wp48/h05/third-party-inventory.json`.

- Python locked components: **101**, license label detected for **85**,
  **16** without a reliable metadata label: clr-loader, colorama, greenlet, jeepney, pefile, pyqt6, pyqt6-qt6, pyqt6-sip, pyqt6-webengine, pyqt6-webengine-qt6, pythonnet, pywin32-ctypes, qtpy, secretstorage, tzdata, winloop.
- npm production components: **37**, license label detected for **37**.
- Copyleft-flagged Python components to review before any commercial/packaged distribution:
  certifi (MPL-2.0), orjson (MPL-2.0 AND (Apache-2.0 OR MIT)), pyinstaller (GPLv2-or-later with a special exception which allows to use PyInstaller to build).
  `pyqt6*` is the notable dual GPLv3/commercial dependency (its metadata carries no license
  label in this environment) and directly affects a paid distribution decision.

**Status: inventory only — not a license decision.** Per the recorded H05 owner disposition
(2026-09-08), the product's root `LICENSE` text has not been chosen, no hypothetical license
(e.g. MIT) is added, and third-party notices/attributions must be completed in an owner/legal
review before any commercial or packaged distribution. This document is factual preparation
for that review, not legal advice and not an approval.
