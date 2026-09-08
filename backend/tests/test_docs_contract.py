"""Isolated contract tests; no application data, network or desktop required."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("check_docs", Path(__file__).parents[2] / "scripts" / "check_docs.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        names = ["AGENTS.md", "docs/product.md", "docs/roadmap.md", "docs/status.md", "docs/wp.md"]
        self.registry = {"schema_version": 1, "documents": dict(zip(names, checker.CURRENT_ROLES)), "startup": names, "archived_unchecked_counts": {"docs/archive/work-packages/old.md": 1}}
        for name, role in self.registry["documents"].items():
            self.put(name, f"<!-- doc-role: {role} -->\n" + ("status: Ready\n" if name.endswith("wp.md") else ""))
        self.put("docs/status.md", "<!-- doc-role: current-status -->\n[Active](wp.md)\n")
        self.registry["documents"]["docs/archive/work-packages/old.md"] = "archived"
        self.put("docs/archive/work-packages/old.md", "<!-- doc-role: archived -->\n- [ ] Still open\n")
        self.save()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def save(self):
        self.put("docs/documentation.json", json.dumps(self.registry))

    def reject(self, text):
        with self.assertRaisesRegex(checker.DocumentationError, text):
            checker.run_checks(self.root)

    def test_valid_contract(self):
        self.assertEqual(checker.run_checks(self.root)["startup_documents"], 5)

    def test_duplicate_roadmap(self):
        self.registry["documents"]["docs/other.md"] = "current-roadmap"
        self.put("docs/other.md", "<!-- doc-role: current-roadmap -->")
        self.save()
        self.reject("exactly one current-roadmap")

    def test_unregistered_plan(self):
        self.put("docs/hidden.md", "<!-- doc-role: current-roadmap -->")
        self.reject("unregistered")

    def test_archive_in_startup(self):
        self.registry["startup"][-1] = "docs/archive/work-packages/old.md"
        self.save()
        self.reject("archived mandatory startup")

    def test_broken_link(self):
        self.put("AGENTS.md", "<!-- doc-role: agent-entry -->\n[Missing](gone.md)")
        self.reject("broken local link")

    def test_missing_selected_wp(self):
        (self.root / "docs/wp.md").unlink()
        self.reject("missing document")

    def test_status_must_link_active(self):
        self.put("docs/status.md", "<!-- doc-role: current-status -->")
        self.reject("STATUS must link")

    def test_archiving_does_not_close_acceptance(self):
        self.put("docs/archive/work-packages/old.md", "<!-- doc-role: archived -->\n- [x] Still open\n")
        self.reject("unchecked criteria changed")

    def test_reference_cannot_claim_current_role(self):
        self.registry["documents"]["docs/other.md"] = "reference"
        self.put("docs/other.md", "<!-- doc-role: current-roadmap -->")
        self.save()
        self.reject("competing current role")

    def test_path_escape(self):
        self.registry["documents"]["../outside.md"] = "reference"
        self.save()
        self.reject("escapes repository")

    def test_completed_wp_cannot_remain_current(self):
        self.put("docs/wp.md", "<!-- doc-role: current-work-package -->\nstatus: Verified\n")
        self.reject("must be Ready")


if __name__ == "__main__":
    unittest.main()
