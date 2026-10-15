"""Constructed offline round trip. Run with the installed product's Python.

Uses only a temporary directory, creates no persistent project files, performs
no network access. This example demonstrates mechanics, not linguistic advice.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory(prefix="locreturn-demo-") as tmp:
        root = Path(tmp)

        def write(name, value):
            (root / name).write_text(json.dumps(value), encoding="utf-8")

        def read(name):
            return json.loads((root / name).read_text(encoding="utf-8"))

        def run(*args, expected=0):
            result = subprocess.run([sys.executable, "-m", "locreturn", *args],
                                    cwd=root, text=True, capture_output=True)
            if result.returncode != expected:
                raise RuntimeError(result.stdout + result.stderr)
            print(result.stdout.strip())

        write("en.json", {"save": "Save", "help": "Help", "cancel": "Cancel"})
        write("fr.json", {"save": "Sauver", "cancel": "Annuler", "orphan": "Retained"})
        run("pack", "--source", "en.json", "--target", "fr.json", "--source-locale", "en", "--target-locale", "fr", "--out", "job")
        task = read("job/task.json")
        task["entries"]["save"]["translation"] = "Enregistrer"
        task["entries"]["help"]["translation"] = "Aide"
        write("job/task.json", task)
        # A concurrent local correction makes 'save' a real target conflict.
        write("fr.json", {"save": "Local correction", "cancel": "Annuler", "orphan": "Retained"})
        common = ["--source", "en.json", "--target", "fr.json", "--baseline", "job/baseline.json", "--returned", "job/task.json"]
        run("plan", *common, "--out", "review", expected=3)
        run("apply", *common, "--plan", "review/plan.json", "--out", "blocked", expected=2)
        if (root / "blocked").exists():
            raise AssertionError("unresolved conflict created final output")
        decisions = read("review/decisions.json")
        decisions["entries"]["save"] = {"action": "keep", "text": None, "reason": "Constructed reviewer preserves local correction"}
        write("review/decisions.json", decisions)
        run("apply", *common, "--plan", "review/plan.json", "--decisions", "review/decisions.json", "--out", "merged")
        output = read("merged/target.json")
        if output != {"save": "Local correction", "help": "Aide", "cancel": "Annuler", "orphan": "Retained"}:
            raise AssertionError(output)
        # A plan cannot be applied after even an unrelated source edit.
        write("en.json", {"save": "Save now", "help": "Help", "cancel": "Cancel"})
        run("apply", *common, "--plan", "review/plan.json", "--decisions", "review/decisions.json", "--out", "stale", expected=2)
        if (root / "stale").exists():
            raise AssertionError("stale plan created output")
        print("Constructed round trip passed: safe edit, concurrent correction, orphan preservation, unresolved and stale refusal.")


if __name__ == "__main__":
    main()
