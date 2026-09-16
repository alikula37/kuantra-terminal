# Bundled report fonts

- `Vera.ttf`, `VeraBd.ttf` — Bitstream Vera Sans (regular, bold), copied unmodified
  from the installed `reportlab` package (`reportlab/fonts/`), version shipped with
  reportlab 5.0.1.
- `LICENSE.txt` — the Bitstream Vera license text shipped by reportlab
  (`reportlab/fonts/bitstream-vera-license.txt`).

The Bitstream Vera license permits use, modification, bundling and redistribution,
including in commercial software; the fonts themselves may not be sold on their own.
The fonts are embedded into generated PDFs and are collected into the packaged app
(`packaging/kuantra.spec` includes `**/*.ttf`).

Verified Turkish glyph coverage (ğ ş ı İ ç ö ü Ç Ş Ğ) for both faces before bundling.
