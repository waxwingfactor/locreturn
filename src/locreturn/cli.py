"""Command-line interface. No network, subprocesses, or implicit file discovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import core
from .files import read_json, review_text, write_bundle


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Reconcile offline JSON translation returns against source and target baselines.")
    root.add_argument("--version", action="version", version=f"locreturn {__version__}")
    subs = root.add_subparsers(dest="command", required=True)
    pack = subs.add_parser("pack", help="create a trusted baseline and an editable translator task")
    pack.add_argument("--source-locale", required=True)
    pack.add_argument("--target-locale", required=True)
    for name in ("pack", "plan", "apply"):
        sub = pack if name == "pack" else subs.add_parser(name, help={"plan": "classify a return; exit 3 when conflicts need review", "apply": "verify a reviewed plan and emit a new target catalog"}[name])
        sub.add_argument("--source", type=Path, required=True, help="current flat source JSON")
        sub.add_argument("--target", type=Path, required=True, help="current flat target JSON (use {} for a new locale)")
        sub.add_argument("--context", type=Path, help="optional current key-to-context JSON")
        sub.add_argument("--out", type=Path, required=True, help="new output directory; never overwrites")
        if name != "pack":
            sub.add_argument("--baseline", type=Path, required=True)
            sub.add_argument("--returned", type=Path, required=True, help="edited task JSON")
        if name == "apply":
            sub.add_argument("--plan", type=Path, required=True, help="reviewed plan.json")
            sub.add_argument("--decisions", type=Path, help="completed decisions.json; required when conflicts exist")
    return root


def run(args: argparse.Namespace) -> tuple[dict, int]:
    source, target = read_json(args.source), read_json(args.target)
    context = read_json(args.context) if args.context else {}
    if args.command == "pack":
        baseline, task = core.pack(source, target, args.source_locale, args.target_locale, context)
        write_bundle(args.out, {"baseline.json": baseline, "task.json": task})
        return {"command": "pack", "job_id": baseline["job_id"], "entries": len(source)}, 0
    base, returned = read_json(args.baseline), read_json(args.returned)
    expected = core.plan(base, returned, source, target, context)
    if args.command == "plan":
        write_bundle(args.out, {"plan.json": expected,
                                "decisions.json": core.decision_template(expected),
                                "review.txt": review_text(expected)})
        return {"command": "plan", "plan_id": expected["plan_id"],
                "conflicts": expected["conflicts"], "counts": expected["counts"]}, 3 if expected["conflicts"] else 0
    p = read_json(args.plan)
    decisions = read_json(args.decisions) if args.decisions else None
    result, receipt = core.apply(p, expected, target, decisions)
    write_bundle(args.out, {"target.json": result, "receipt.json": receipt})
    return {"command": "apply", "plan_id": p["plan_id"], "changes": len(receipt["changes"]),
            "resolved_conflicts": receipt["resolved_conflicts"], "receipt_id": receipt["receipt_id"]}, 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        summary, code = run(args)
    except (core.Invalid, OSError, ValueError, TypeError, RecursionError) as exc:
        # JSON escaped error text avoids raw filenames/control codes on terminals.
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return code
