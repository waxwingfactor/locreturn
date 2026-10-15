import copy
import itertools
import unittest

from locreturn import core


class MergeTests(unittest.TestCase):
    def setup_job(self, old=None, incoming="nouveau", current=None, source="Save", context=None):
        old = {} if old is None else {"key": old}
        current = {} if current is None else {"key": current}
        b, r = core.pack({"key": "Save"}, old, "en", "fr", context)
        r["entries"]["key"]["translation"] = incoming
        p = core.plan(b, r, {"key": source}, current, context)
        return b, r, p, current

    def test_complete_target_three_way_matrix(self):
        # Exhaustive missing/empty/nonempty baseline/current/incoming combinations.
        values = [None, "", "ancien", "nouveau"]
        for original, current, incoming in itertools.product(values, repeat=3):
            with self.subTest(original=original, current=current, incoming=incoming):
                _, _, p, t = self.setup_job(original, incoming, current)
                status = p["rows"][0]["status"]
                expected = ("skipped" if incoming is None else
                            "unchanged-return" if incoming == original else
                            "already-current" if incoming == current else
                            "ready" if current == original else "target-conflict")
                self.assertEqual(status, expected)
                if status != "target-conflict":
                    result, _ = core.apply(p, p, t)
                    value = incoming if status == "ready" else current
                    self.assertEqual(result, {} if value is None else {"key": value})

    def test_source_drift_precedes_convergence(self):
        _, _, p, t = self.setup_job("old", "new", "new", source="Save now")
        self.assertEqual(p["rows"][0]["status"], "source-changed")
        with self.assertRaises(core.Invalid):
            core.apply(p, p, t)

    def test_unchanged_return_keeps_local_even_when_source_changed(self):
        _, _, p, t = self.setup_job("old", "old", "local", source="Save now")
        self.assertTrue(p["rows"][0]["source_changed"])
        self.assertEqual(core.apply(p, p, t)[0], t)

    def test_custom_resolves_new_source(self):
        _, _, p, t = self.setup_job("old", "new", "local", source="Save now")
        d = core.decision_template(p)
        d["entries"]["key"] = {"action": "custom", "text": "Enregistrer maintenant", "reason": "Reviewed against new source"}
        result, receipt = core.apply(p, p, t, d)
        self.assertEqual(result["key"], "Enregistrer maintenant")
        self.assertEqual(receipt["resolved_conflicts"], 1)
        self.assertEqual(receipt["decisions"], d["entries"])
        self.assertEqual(receipt["output_sha256"], core.digest(result))

    def test_source_changed_disallows_incoming(self):
        _, _, p, t = self.setup_job("old", "new", "local", source="Save now")
        d = core.decision_template(p)
        d["entries"]["key"] = {"action": "incoming", "text": None, "reason": "ignore drift"}
        with self.assertRaises(core.Invalid):
            core.apply(p, p, t, d)

    def test_target_conflict_choices(self):
        for action, value in (("incoming", "new"), ("keep", "local"), ("custom", "reviewed")):
            _, _, p, t = self.setup_job("old", "new", "local")
            d = core.decision_template(p)
            d["entries"]["key"] = {"action": action, "text": "reviewed" if action == "custom" else None, "reason": "Reviewed"}
            self.assertEqual(core.apply(p, p, t, d)[0]["key"], value)

    def test_new_and_orphan_keys_preserved(self):
        b, r = core.pack({"a": "A"}, {"a": "ancien", "orphan": "keep"}, "en", "fr")
        t = {"a": "ancien", "orphan": "keep", "new": "local"}
        p = core.plan(b, r, {"a": "A", "new": "New"}, t)
        self.assertEqual(core.apply(p, p, t)[0], t)
        self.assertEqual(p["counts"], {"new-source": 1, "orphan-target": 1, "skipped": 1})

    def test_source_removal_requires_keep_decision(self):
        b, r = core.pack({"a": "A"}, {"a": "ancien"}, "en", "fr")
        r["entries"]["a"]["translation"] = "new"
        p = core.plan(b, r, {}, {"a": "local"})
        self.assertEqual(p["rows"][0]["status"], "source-removed")
        d = core.decision_template(p)
        d["entries"]["a"] = {"action": "keep", "text": None, "reason": "Retain orphan; prune separately"}
        self.assertEqual(core.apply(p, p, {"a": "local"}, d)[0], {"a": "local"})

    def test_partial_return_is_explicitly_supported(self):
        b, r = core.pack({"a": "A", "b": "B"}, {}, "en", "fr")
        del r["entries"]["b"]
        r["entries"]["a"]["translation"] = "Un"
        p = core.plan(b, r, b["source"], {})
        self.assertEqual(p["counts"], {"ready": 1, "not-returned": 1})
        self.assertEqual(core.apply(p, p, {})[0], {"a": "Un"})

    def test_decision_reason_and_exact_scope(self):
        _, _, p, t = self.setup_job("old", "new", "local")
        good = core.decision_template(p)
        good["entries"]["key"] = {"action": "keep", "text": None, "reason": "reviewed"}
        variants = []
        for field, value in (("reason", "  "), ("text", "unexpected"), ("action", "delete")):
            d = copy.deepcopy(good)
            d["entries"]["key"][field] = value
            variants.append(d)
        d = copy.deepcopy(good)
        d["entries"]["unknown"] = d["entries"]["key"]
        variants.append(d)
        d = copy.deepcopy(good)
        d["entries"] = {}
        variants.append(d)
        for d in variants:
            with self.subTest(d=d), self.assertRaises(core.Invalid):
                core.apply(p, p, t, d)

    def test_semantic_order_stability(self):
        b1, r1 = core.pack({"a": "A", "b": "B"}, {}, "en", "fr")
        b2, r2 = core.pack({"b": "B", "a": "A"}, {}, "en", "fr")
        self.assertEqual(b1, b2)
        self.assertEqual(r1, r2)
        self.assertEqual(core.plan(b1, r1, b1["source"], {}), core.plan(b2, r2, b2["source"], {}))

    def test_unicode_and_multiline_exact_no_normalization(self):
        b, r = core.pack({"a": "Cafe\u0301\n🙂"}, {}, "en", "ar")
        r["entries"]["a"]["translation"] = "مرحبا\n🙂"
        p = core.plan(b, r, b["source"], {})
        self.assertEqual(core.apply(p, p, {})[0]["a"], "مرحبا\n🙂")
        p2 = core.plan(b, r, {"a": "Café\n🙂"}, {})
        self.assertEqual(p2["rows"][0]["status"], "source-changed")


if __name__ == "__main__":
    unittest.main()
