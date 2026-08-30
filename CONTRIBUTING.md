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

## 🧪 Testing Protocol

Before submitting a Pull Request or pushing changes:

1. Run the complete backend Pytest suite:
   ```bash
   pytest backend/tests -v --tb=short
   ```
   **Requirement**: 100% pass rate across all existing test files.

2. Run the frontend TypeScript compilation check:
   ```bash
   cd frontend
   npm run build
   ```
   **Requirement**: 0 TypeScript compiler errors and clean Vite chunk generation.