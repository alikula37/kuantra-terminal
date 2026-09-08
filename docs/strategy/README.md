# Strategy: current sources and reference routing

Start at [AGENTS.md](../../AGENTS.md). The five-file startup set is AGENTS,
[PRODUCT](PRODUCT.md), [one roadmap](PRODUCTION-READINESS-PLAN.md),
[STATUS](STATUS.md), and the active WP linked from STATUS.

Do not load all documents recursively. Read code/tests and only task-relevant references:

- [Accepted ADRs](adr/): identity, storage, execution authority, Windows renderer.
- [Local CI policy](LOCAL-CI-POLICY.md): validation and merge/release boundaries.
- [WP template](WORK-PACKAGE-TEMPLATE.md): when creating a bounded task.
- [Development governance](DEVELOPMENT-GOVERNANCE.md): detailed process reference.
- [Mac build](../BUILD_MACOS.md), [Windows build](../BUILD_WINDOWS.md),
  [Linux build](../BUILD_LINUX.md), [migration](../MACOS_MIGRATION.md): relevant operations only.
- [Archive and outstanding criteria](../archive/README.md): historical audit/implementation
  evidence, never the default next-work queue.

`docs/documentation.json` is the machine-readable role/path registry, not a second
roadmap. Check it with `python3.11 scripts/check_docs.py`. STATUS is the current progress
source. Roadmap scope marked Proposed stays proposed until the owner decides otherwise.
