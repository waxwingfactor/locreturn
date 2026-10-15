import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name)
        self.write("en.json", {"save": "Save", "cancel": "Cancel"})
        self.write("fr.json", {"save": "Ancien"})

    def write(self, name, value):
        (self.cwd / name).write_text(json.dumps(value), encoding="utf-8")

    def load(self, name):
        return json.loads((self.cwd / name).read_text(encoding="utf-8"))

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, "-m", "locreturn", *args], cwd=self.cwd,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def pack(self):
        self.cli("pack", "--source", "en.json", "--target", "fr.json",
                 "--source-locale", "en", "--target-locale", "fr", "--out", "job")

    def common(self):
        return ["--source", "en.json", "--target", "fr.json", "--baseline", "job/baseline.json", "--returned", "job/task.json"]

    def test_end_to_end_review_and_apply(self):
        self.pack()
        task = self.load("job/task.json")
        task["entries"]["save"]["translation"] = "Enregistrer"
        task["entries"]["cancel"]["translation"] = "Annuler"
        self.write("job/task.json", task)
        self.write("fr.json", {"save": "Local correction"})
        self.cli("plan", *self.common(), "--out", "review", code=3)
        self.cli("apply", *self.common(), "--plan", "review/plan.json", "--out", "blocked", code=2)
        self.assertFalse((self.cwd / "blocked").exists())
        decisions = self.load("review/decisions.json")
        decisions["entries"]["save"] = {"action": "keep", "text": None, "reason": "Preserve local correction"}
        self.write("review/decisions.json", decisions)
        self.cli("apply", *self.common(), "--plan", "review/plan.json", "--decisions", "review/decisions.json", "--out", "merged")
        self.assertEqual(self.load("merged/target.json"), {"save": "Local correction", "cancel": "Annuler"})
        self.assertEqual(self.load("fr.json"), {"save": "Local correction"})

    def test_stale_input_produces_no_output(self):
        self.pack()
        self.cli("plan", *self.common(), "--out", "review")
        self.write("en.json", {"save": "Save now", "cancel": "Cancel"})
        result = self.cli("apply", *self.common(), "--plan", "review/plan.json", "--out", "merged", code=2)
        self.assertIn("stale", result.stderr)
        self.assertFalse((self.cwd / "merged").exists())

    def test_existing_output_not_overwritten(self):
        self.pack()
        before = (self.cwd / "job/task.json").read_bytes()
        self.cli("pack", "--source", "en.json", "--target", "fr.json", "--source-locale", "en", "--target-locale", "fr", "--out", "job", code=2)
        self.assertEqual(before, (self.cwd / "job/task.json").read_bytes())

    def test_unsupported_input_fails_without_output(self):
        for data in ({"nested": {"key": "value"}}, {"n": 5}, ["array"], {"x": None}, {"x": True}):
            self.write("en.json", data)
            self.cli("pack", "--source", "en.json", "--target", "fr.json", "--source-locale", "en", "--target-locale", "fr", "--out", "bad", code=2)
            self.assertFalse((self.cwd / "bad").exists())

    def test_help_and_version(self):
        self.assertIn("locreturn 1.0.0", self.cli("--version").stdout)
        self.assertIn("pack", self.cli("--help").stdout)


if __name__ == "__main__":
    unittest.main()
