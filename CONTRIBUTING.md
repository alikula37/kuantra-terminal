# Contributing to Kuantra Terminal

Thank you for your interest in contributing to **Kuantra Terminal** — the institutional desktop algorithmic trading suite and AI Swarm ecosystem.

To maintain our strict standards of execution reliability, security isolation, and sub-millisecond responsiveness, all contributions must adhere to the protocols outlined below.

---

## 🌿 Git Branching Strategy

- **`main`**: Production-ready branch. Every commit on `main` must pass 100% of automated test suites and compile cleanly across Windows, macOS, and Linux.
- **`feat/<feature-name>`**: Development of new features or phase extensions.
- **`fix/<bug-description>`**: Targeted bug fixes and security patches.
- **`perf/<optimization>`**: Quantitative latency and memory optimizations.

---

## 📝 Conventional Commits Standard

We strictly enforce the **Conventional Commits** specification:

```
<type>(<scope>): <short descriptive summary>

[optional body describing technical rationale and design decisions]
```

### Supported Types:
- `feat`: New user-facing or architectural capability
- `fix`: Bug resolution or test repair
- `docs`: Documentation, architecture blueprints, and runbooks
- `test`: Addition or refinement of automated unit/integration tests
- `refactor`: Code restructuring without functional alterations
- `perf`: Performance enhancement or memory allocation optimization

---

## 🔍 Code Quality & Linting Standards

### 1. Python Backend
- **Python Version**: `3.11.0+`
- **Linting & Formatting**: Clean PEP 8 compliance.
- **Type Annotations**: Full `typing` coverage (`Dict[str, Any]`, `Optional[T]`, `List[T]`, `Tuple[...]`).
- **Zero Placeholder Policy**: No `// TODO`, `pass`, or mock stubs in production paths.

### 2. Frontend React / TypeScript
- **TypeScript**: `5.0+` with strict mode (`"strict": true` in `tsconfig.json`).
- **No Implicit Any**: Explicit interfaces and props definitions for all components and hooks.
- **Tailwind CSS**: Use theme-aware CSS custom properties (`--bg-primary`, `--bg-surface`, `--color-gain`, `--color-loss`).

---

## 🖥️ Development Workflow

Kuantra Terminal is a **single-process desktop app**: a pywebview window hosting the React bundle
with the FastAPI backend dispatched in-process over ASGI. There is no local HTTP port between the
UI and the backend in the packaged app, and no Rust toolchain is involved.

### 1. One-time setup
```bash
pip install -r backend/requirements.txt -r backend/requirements-desktop.txt
npm --prefix frontend install
```

### 2. Day-to-day loops

**Browser loop** — fastest iteration; the frontend falls back to real `fetch`/`WebSocket` against
uvicorn on `:8000` when `window.pywebview` is absent:
```bash
npm run dev              # Vite dev server on :5173
python backend/main.py   # FastAPI on :8000
```

**Desktop loop** — a real pywebview window and the real Python bridge, with Vite hot reload:
```bash
npm run desktop          # python backend/desktop_main.py --dev-url http://localhost:5173
```

### 3. Building and packaging
```bash
python scripts/build_desktop.py   # frontend build + PyInstaller freeze into dist/
python scripts/smoke_desktop.py   # headless self-test of the frozen app

bash scripts/package_macos.sh     # dist/Kuantra-Terminal-<ver>-aarch64.dmg
bash scripts/package_windows.sh   # dist/Kuantra-Terminal-<ver>-Setup.exe (needs NSIS on PATH)
bash scripts/package_linux.sh     # dist/Kuantra-Terminal-<ver>-x86_64.AppImage
```
Platform prerequisites and details: [`docs/BUILD_MACOS.md`](docs/BUILD_MACOS.md),
[`docs/BUILD_WINDOWS.md`](docs/BUILD_WINDOWS.md), [`docs/BUILD_LINUX.md`](docs/BUILD_LINUX.md).

### 4. Local state
Never write long-lived state into the install tree. The app uses a per-user data directory
(`~/Library/Application Support/Kuantra Terminal`, `%LOCALAPPDATA%\Kuantra Terminal`,
`$XDG_DATA_HOME/kuantra-terminal`), overridable with `KUANTRA_DATA_DIR`; a dev checkout keeps
using `backend/data`. Bump the version in `backend/app/version.py` only — everything else reads it
from there.

---

## 🧪 Testing Protocol

Before submitting a Pull Request or pushing changes:

1. Run the complete backend Pytest suite against a throwaway data directory:
   ```bash
   KUANTRA_DATA_DIR="$(mktemp -d)" python -m pytest backend/tests -q
   ```
   **Requirement**: 100% pass rate across all existing test files.

2. Run the frontend unit tests and i18n parity check:
   ```bash
   npm --prefix frontend test
   npm run check:i18n
   ```
   **Requirement**: all vitest specs pass and `tr.json` / `en.json` / `de.json` stay in full parity.

3. Run the frontend TypeScript compilation check:
   ```bash
   cd frontend
   npm run build
   ```
   **Requirement**: 0 TypeScript compiler errors and clean Vite chunk generation.

4. For changes that touch the desktop shell or packaging, build and smoke the frozen app:
   ```bash
   python scripts/build_desktop.py && python scripts/smoke_desktop.py
   ```
   **Requirement**: exit code 0 and a passing `dist/smoke.json` report.