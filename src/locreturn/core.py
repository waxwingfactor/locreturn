"""Pure, deterministic source-qualified three-way reconciliation.

Missing target values use None internally; catalog values can only be strings.
No normalization, runtime syntax interpretation, or implicit deletion occurs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

MAX_ENTRIES = 10_000
MAX_TEXT = 65_536
MAX_KEY = 1_024
MAX_FILE = 32 * 1024 * 1024
CONFLICTS = {"source-changed", "source-removed", "target-conflict"}


class Invalid(ValueError):
    """A user input violates the supported contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Invalid(message)


def text(value: Any, label: str, limit: int = MAX_TEXT) -> str:
    require(isinstance(value, str), f"{label}: expected a string")
    require(len(value) <= limit, f"{label}: exceeds {limit} characters")
    require(not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
            f"{label}: unpaired Unicode surrogate")
    return value


def shape(value: Any, keys: set[str], label: str) -> dict:
    require(isinstance(value, dict), f"{label}: expected an object")
    require(set(value) == keys, f"{label}: expected fields {', '.join(sorted(keys))}")
    return value


def catalog(value: Any, label: str) -> dict[str, str]:
    require(isinstance(value, dict), f"{label}: expected a flat key-to-string JSON object")
    require(len(value) <= MAX_ENTRIES, f"{label}: exceeds {MAX_ENTRIES} entries")
    for key, val in value.items():
        text(key, f"{label} key", MAX_KEY)
        require(bool(key), f"{label}: empty keys are unsupported")
        text(val, f"{label} value")
    return value


def locale(value: Any) -> str:
    text(value, "locale", 64)
    require(bool(re.fullmatch(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*", value)),
            "locale: use a language tag such as en, fr-CA or pt_BR")
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(payload: dict, field: str) -> dict:
    return {**payload, field: digest(payload)}


def check_seal(value: dict, field: str, label: str) -> None:
    payload = {k: v for k, v in value.items() if k != field}
    require(value[field] == digest(payload), f"{label}: invalid {field}; keep the original trusted file")


def contexts(value: Any, source: dict) -> dict:
    catalog(value, "context")
    require(set(value) <= set(source), "context: keys must exist in source")
    return value


def pack(source: dict, target: dict, source_locale: str, target_locale: str,
         context: dict | None = None) -> tuple[dict, dict]:
    catalog(source, "source")
    catalog(target, "target")
    require(len(set(source) | set(target)) <= MAX_ENTRIES,
            f"combined catalog exceeds {MAX_ENTRIES} keys")
    locale(source_locale)
    locale(target_locale)
    require(source_locale.lower().replace("_", "-") != target_locale.lower().replace("_", "-"),
            "source and target locales must differ")
    context = contexts(context if context is not None else {}, source)
    baseline = seal({"schema": "locreturn.baseline.v1", "source_locale": source_locale,
                     "target_locale": target_locale, "source": source, "target": target,
                     "context": context}, "job_id")
    task = {"schema": "locreturn.return.v1", "job_id": baseline["job_id"],
            "source_locale": source_locale, "target_locale": target_locale,
            "entries": {k: {"source": source[k], "context": context.get(k),
                            "previous_target": target.get(k), "translation": None}
                        for k in sorted(source)}}
    return baseline, task


def baseline_check(base: Any) -> dict:
    shape(base, {"schema", "source_locale", "target_locale", "source", "target", "context", "job_id"}, "baseline")
    require(base["schema"] == "locreturn.baseline.v1", "unsupported baseline schema")
    rebuilt, _ = pack(base["source"], base["target"], base["source_locale"],
                      base["target_locale"], base["context"])
    require(base == rebuilt, "baseline: invalid job_id; keep the original trusted file")
    return base


def returned_check(returned: Any, base: dict) -> dict:
    shape(returned, {"schema", "job_id", "source_locale", "target_locale", "entries"}, "return")
    require(returned["schema"] == "locreturn.return.v1", "unsupported return schema")
    for key in ("job_id", "source_locale", "target_locale"):
        require(returned[key] == base[key], f"return: {key} does not match baseline")
    entries = returned["entries"]
    require(isinstance(entries, dict) and len(entries) <= MAX_ENTRIES, "return: invalid entries object")
    require(set(entries) <= set(base["source"]), "return: unknown keys; do not add or rename keys")
    for key, row in entries.items():
        shape(row, {"source", "context", "previous_target", "translation"}, "return entry")
        for field, expected in (("source", base["source"][key]),
                                ("context", base["context"].get(key)),
                                ("previous_target", base["target"].get(key))):
            require(row[field] == expected, f"return: modified {field}; edit translation only")
        if row["translation"] is not None:
            text(row["translation"], "translation")
    return returned


def plan(base: dict, returned: dict, source: dict, target: dict,
         context: dict | None = None) -> dict:
    baseline_check(base)
    returned_check(returned, base)
    catalog(source, "current source")
    catalog(target, "current target")
    context = contexts(context if context is not None else {}, source)
    rows = []
    keys = set(base["source"]) | set(source) | set(target) | set(base["target"])
    require(len(keys) <= MAX_ENTRIES, f"combined catalog exceeds {MAX_ENTRIES} keys")
    for key in sorted(keys):
        incoming = returned["entries"].get(key, {}).get("translation")
        original = base["target"].get(key)
        current = target.get(key)
        source_changed = (base["source"].get(key) != source.get(key)
                          or base["context"].get(key) != context.get(key))
        if key not in base["source"]:
            status = "new-source" if key in source else "orphan-target"
        elif key not in returned["entries"]:
            status = "not-returned"
        elif incoming is None:
            status = "skipped"
        elif incoming == original:
            status = "unchanged-return"
        elif key not in source:
            status = "source-removed"
        elif source_changed:
            status = "source-changed"
        elif incoming == current:
            status = "already-current"
        elif current == original:
            status = "ready"
        else:
            status = "target-conflict"
        rows.append({"key": key, "status": status, "source_changed": source_changed,
                     "base_source": base["source"].get(key), "current_source": source.get(key),
                     "base_context": base["context"].get(key), "current_context": context.get(key),
                     "base_target": original, "current_target": current, "incoming": incoming})
    counts = dict(sorted(Counter(r["status"] for r in rows).items()))
    return seal({"schema": "locreturn.plan.v1", "job_id": base["job_id"],
                 "source_locale": base["source_locale"], "target_locale": base["target_locale"],
                 "inputs": {"baseline": digest(base), "return": digest(returned),
                            "source": digest(source), "target": digest(target), "context": digest(context)},
                 "counts": counts, "conflicts": sum(r["status"] in CONFLICTS for r in rows),
                 "rows": rows}, "plan_id")


def decision_template(p: dict) -> dict:
    return {"schema": "locreturn.decisions.v1", "plan_id": p["plan_id"],
            "entries": {r["key"]: {"action": "unresolved", "text": None, "reason": ""}
                        for r in p["rows"] if r["status"] in CONFLICTS}}


def apply(p: dict, expected_plan: dict, target: dict, decisions: dict | None = None) -> tuple[dict, dict]:
    require(canonical(p) == canonical(expected_plan),
            "plan is stale or modified; regenerate and review a new plan")
    decisions = decisions if decisions is not None else decision_template(p)
    shape(decisions, {"schema", "plan_id", "entries"}, "decisions")
    require(decisions["schema"] == "locreturn.decisions.v1", "unsupported decisions schema")
    require(decisions["plan_id"] == p["plan_id"], "decisions refer to a different plan")
    needed = {r["key"] for r in p["rows"] if r["status"] in CONFLICTS}
    require(isinstance(decisions["entries"], dict) and set(decisions["entries"]) == needed,
            "decisions must contain exactly every conflict key")
    result = dict(target)
    changes = []
    for row in p["rows"]:
        key, status = row["key"], row["status"]
        action, value, reason = "keep", target.get(key), None
        if status == "ready":
            action, value = "incoming", row["incoming"]
        elif status in CONFLICTS:
            d = decisions["entries"][key]
            shape(d, {"action", "text", "reason"}, "decision")
            action = d["action"]
            allowed = {"keep"}
            if status != "source-removed":
                allowed.add("custom")
            if status == "target-conflict":
                allowed.add("incoming")
            require(action in allowed, f"decision action unresolved or disallowed for {status}")
            reason = text(d["reason"], "decision reason", 4096)
            require(bool(reason.strip()), "decision requires a nonempty review reason")
            if action == "custom":
                value = text(d["text"], "custom translation")
            else:
                require(d["text"] is None, "text must be null unless action is custom")
                if action == "incoming":
                    value = row["incoming"]
        if action != "keep":
            result[key] = value
        if result.get(key) != target.get(key):
            changes.append({"key": key, "before": target.get(key), "after": result[key],
                            "action": action, "reason": reason})
    receipt = seal({"schema": "locreturn.receipt.v1", "plan_id": p["plan_id"],
                    "job_id": p["job_id"], "inputs": p["inputs"],
                    "decisions_sha256": digest(decisions), "output_sha256": digest(result),
                    "changes": changes, "resolved_conflicts": len(needed),
                    "decisions": decisions["entries"]}, "receipt_id")
    return result, receipt
