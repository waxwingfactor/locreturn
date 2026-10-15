"""Independent hostile-input and review-integrity acceptance tests.

These test the public CLI path where possible. They intentionally exercise
boundaries rather than repeating the ordinary reconciliation decision matrix.
"""

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from locreturn import cli, core, files


class AdversarialAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = {"hello": "Hello", "empty": "Empty"}
        self.target = {"hello": "Bonjour", "orphan": "Preserved"}
        self.context = {"hello": "Friendly greeting"}
        self.base, self.returned = core.pack(
            self.source, self.target, "en", "fr", self.context
        )
        self.returned["entries"]["hello"]["translation"] = "Salut"
        self.current_source = dict(self.source)
        self.current_target = dict(self.target)
        self.current_context = dict(self.context)

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")
        return path

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(list(map(str, args)))
        return code, stdout.getvalue(), stderr.getvalue()

    def input_paths(self):
        return {
            "source": self.write("source.json", self.current_source),
            "target": self.write("target.json", self.current_target),
            "context": self.write("context.json", self.current_context),
            "baseline": self.write("baseline.json", self.base),
            "returned": self.write("returned.json", self.returned),
        }

    def make_plan(self):
        return core.plan(self.base, self.returned, self.current_source,
                         self.current_target, self.current_context)

    def apply_cli(self, paths, reviewed_plan, output_name="applied"):
        plan_path = self.write("reviewed-plan.json", reviewed_plan)
        args = ["apply", "--plan", plan_path, "--out", self.root / output_name]
        for name, path in paths.items():
            args.extend(["--" + name, path])
        return self.run_cli(*args)

    def assert_invalid_file(self, raw):
        path = self.root / "bad.json"
        path.write_bytes(raw)
        with self.assertRaises(core.Invalid):
            files.read_json(path)

    def test_duplicate_keys_rejected_at_every_depth(self):
        for raw in (b'{"a":"one","a":"two"}',
                    b'{"entries":{"a":{"translation":"x","translation":"y"}}}'):
            with self.subTest(raw=raw):
                self.assert_invalid_file(raw)

    def test_nonfinite_literals_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.assert_invalid_file(('{"a":' + value + '}').encode())

    def test_invalid_encoding_and_json_rejected(self):
        for raw in (b'{"a":"\xff"}', b'{"a":}', b'\xef\xbb\xbf{}', b'{'):
            with self.subTest(raw=raw):
                self.assert_invalid_file(raw)

    def test_extreme_nesting_is_controlled_error(self):
        paths = self.input_paths()
        paths["source"].write_bytes(b'[' * 3000 + b'0' + b']' * 3000)
        code, stdout, stderr = self.apply_cli(paths, self.make_plan())
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error", json.loads(stderr))
        self.assertNotIn("Traceback", stderr)
        self.assertFalse((self.root / "applied").exists())

    def test_catalog_rejects_all_nonstring_values(self):
        for value in (None, True, 1, 1.5, [], {}, ["x"]):
            with self.subTest(value=value), self.assertRaises(core.Invalid):
                core.pack({"a": value}, {}, "en", "fr")

    def test_catalog_rejects_nonobject_top_level(self):
        for value in ([], None, "text", 1):
            with self.subTest(value=value), self.assertRaises(core.Invalid):
                core.pack(value, {}, "en", "fr")

    def test_unpaired_surrogates_rejected_in_keys_and_values(self):
        for source in ({"x": "\ud800"}, {"\udfff": "x"}):
            with self.subTest(source=repr(source)), self.assertRaises(core.Invalid):
                core.pack(source, {}, "en", "fr")

    def test_text_key_and_entry_limits_enforced(self):
        candidates = ({"x": "x" * (core.MAX_TEXT + 1)},
                      {"x" * (core.MAX_KEY + 1): "x"},
                      {"": "x"},
                      {str(i): "x" for i in range(core.MAX_ENTRIES + 1)})
        for source in candidates:
            with self.subTest(size=len(source)), self.assertRaises(core.Invalid):
                core.pack(source, {}, "en", "fr")

    def test_combined_union_limit_enforced(self):
        self.current_target = {f"orphan-{i}": "x" for i in range(core.MAX_ENTRIES)}
        with self.assertRaises(core.Invalid):
            self.make_plan()

    def test_context_keys_must_exist_in_current_source(self):
        self.current_context["unknown"] = "context"
        with self.assertRaises(core.Invalid):
            self.make_plan()

    def test_edited_task_identity_fields_are_rejected(self):
        for name, value in (("source", "Different source"),
                            ("context", "Different context"),
                            ("previous_target", "Different translation")):
            returned = copy.deepcopy(self.returned)
            returned["entries"]["hello"][name] = value
            with self.subTest(field=name), self.assertRaises(core.Invalid):
                core.plan(self.base, returned, self.source, self.target, self.context)

    def test_edited_job_and_locale_are_rejected(self):
        for name in ("job_id", "source_locale", "target_locale"):
            returned = copy.deepcopy(self.returned)
            returned[name] = "tampered"
            with self.subTest(field=name), self.assertRaises(core.Invalid):
                core.plan(self.base, returned, self.source, self.target, self.context)

    def test_unknown_task_keys_and_fields_are_rejected(self):
        for mutation in ("key", "row-field", "top-field"):
            returned = copy.deepcopy(self.returned)
            if mutation == "key":
                returned["entries"]["not-exported"] = copy.deepcopy(returned["entries"]["hello"])
            elif mutation == "row-field":
                returned["entries"]["hello"]["extra"] = "ignored?"
            else:
                returned["extra"] = "ignored?"
            with self.subTest(mutation=mutation), self.assertRaises(core.Invalid):
                core.plan(self.base, returned, self.source, self.target, self.context)

    def test_context_addition_removal_and_change_invalidate_incoming(self):
        for old_context, new_context in (({}, {"hello": "new"}),
                                          ({"hello": "old"}, {}),
                                          ({"hello": "old"}, {"hello": "new"})):
            base, returned = core.pack(self.source, self.target, "en", "fr", old_context)
            returned["entries"]["hello"]["translation"] = "Salut"
            p = core.plan(base, returned, self.source, self.target, new_context)
            row = next(row for row in p["rows"] if row["key"] == "hello")
            with self.subTest(old=old_context, new=new_context):
                self.assertEqual(row["status"], "source-changed")
                self.assertTrue(row["source_changed"])

    def test_returned_source_unicode_is_compared_without_normalizing(self):
        self.current_source["hello"] = "Hello\u0301"
        p = self.make_plan()
        row = next(row for row in p["rows"] if row["key"] == "hello")
        self.assertEqual(row["status"], "source-changed")

    def test_untrusted_baseline_edit_without_resealing_fails(self):
        self.base["source"]["hello"] = "New meaning"
        with self.assertRaises(core.Invalid):
            self.make_plan()

    def test_plan_tamper_is_rejected_without_output(self):
        p = self.make_plan()
        p["rows"][0]["incoming"] = "Injected"
        code, _, error = self.apply_cli(self.input_paths(), p)
        self.assertEqual(code, 2, error)
        self.assertFalse((self.root / "applied").exists())

    def test_numeric_type_plan_tamper_is_rejected(self):
        p = self.make_plan()
        # Python's structural equality considers False == 0 and True == 1.
        p["conflicts"] = False
        code, _, error = self.apply_cli(self.input_paths(), p)
        self.assertEqual(code, 2, error)
        self.assertFalse((self.root / "applied").exists())

    def test_every_changed_plan_input_rejects_stale_apply(self):
        original_plan = self.make_plan()
        for changed in ("source", "target", "context", "returned", "baseline"):
            paths = self.input_paths()
            value = json.loads(paths[changed].read_text())
            if changed in ("source", "target", "context"):
                value["hello"] = "Changed after plan"
            elif changed == "returned":
                value["entries"]["hello"]["translation"] = "Autre"
            else:
                value["target"]["hello"] = "Changed after plan"
            self.write(paths[changed].name, value)
            output_name = "applied-" + changed
            code, _, error = self.apply_cli(paths, original_plan, output_name)
            with self.subTest(changed=changed):
                self.assertEqual(code, 2, error)
                self.assertFalse((self.root / output_name).exists())

    def test_semantic_key_reordering_does_not_stale_plan(self):
        p = self.make_plan()
        paths = self.input_paths()
        paths["source"].write_text('{ "empty": "Empty", "hello": "Hello" }\n')
        code, _, error = self.apply_cli(paths, p)
        self.assertEqual(code, 0, error)

    def test_existing_output_directory_never_overwritten(self):
        out = self.root / "existing"
        out.mkdir()
        sentinel = out / "target.json"
        sentinel.write_bytes(b"keep me")
        with self.assertRaises(FileExistsError):
            files.write_bundle(out, {"target.json": {"changed": "yes"}})
        self.assertEqual(sentinel.read_bytes(), b"keep me")

    def test_existing_output_file_never_overwritten(self):
        out = self.root / "existing"
        out.write_bytes(b"keep me")
        with self.assertRaises(FileExistsError):
            files.write_bundle(out, {"target.json": {}})
        self.assertEqual(out.read_bytes(), b"keep me")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_output_symlink_never_followed(self):
        existing = self.root / "protected"
        existing.mkdir()
        out = self.root / "link"
        out.symlink_to(existing, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            files.write_bundle(out, {"target.json": {}})
        self.assertEqual(list(existing.iterdir()), [])

    def test_serialization_failure_creates_no_bundle(self):
        out = self.root / "invalid"
        with self.assertRaises(ValueError):
            files.write_bundle(out, {"first.json": {}, "second.json": {"v": float("nan")}})
        self.assertFalse(out.exists())

    def test_generated_size_limit_creates_no_bundle(self):
        out = self.root / "oversized"
        with mock.patch.object(files, "MAX_FILE", 8), self.assertRaises(core.Invalid):
            files.write_bundle(out, {"first.json": {"v": "too large"}})
        self.assertFalse(out.exists())

    def test_midwrite_failure_cleans_only_created_bundle(self):
        out = self.root / "failed"
        with mock.patch.object(files.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                files.write_bundle(out, {"first.json": {}, "second.json": {}})
        self.assertFalse(out.exists())

    def test_input_size_limit(self):
        path = self.write("large.json", {"v": "too large"})
        with mock.patch.object(files, "MAX_FILE", 8), self.assertRaises(core.Invalid):
            files.read_json(path)

    def test_directory_input_is_rejected(self):
        with self.assertRaises((OSError, core.Invalid)):
            files.read_json(self.root)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs unavailable")
    def test_fifo_input_is_rejected_without_waiting_for_writer(self):
        path = self.root / "fifo"
        os.mkfifo(path)
        with self.assertRaises(core.Invalid):
            files.read_json(path)

    def test_terminal_control_characters_are_escaped_in_review(self):
        source = {"danger\x1b[2J": "Line\nTwo\t\x1b[2J"}
        base, returned = core.pack(source, {}, "en", "fr")
        rendered = files.review_text(core.plan(base, returned, source, {}))
        self.assertNotIn("\x1b", rendered)
        self.assertIn("\\u001b", rendered)

    def test_invalid_input_cli_emits_controlled_error_and_no_output(self):
        paths = self.input_paths()
        paths["returned"].write_bytes(b'{"a":')
        code, stdout, stderr = self.apply_cli(paths, self.make_plan())
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error", json.loads(stderr))
        self.assertNotIn("Traceback", stderr)
        self.assertFalse((self.root / "applied").exists())

    def test_relocated_input_bundle_is_usable(self):
        paths = self.input_paths()
        relocated = self.root / "relocated"
        relocated.mkdir()
        moved_paths = {}
        for name, path in paths.items():
            destination = relocated / path.name
            path.rename(destination)
            moved_paths[name] = destination
        code, _, error = self.apply_cli(moved_paths, self.make_plan())
        self.assertEqual(code, 0, error)


if __name__ == "__main__":
    unittest.main()
