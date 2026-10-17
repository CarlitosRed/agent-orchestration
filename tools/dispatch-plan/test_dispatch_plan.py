import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import dispatch_plan as d

HERE = Path(__file__).parent


def worker(name, scope=None, dependencies=(), readonly=False):
    return {"id": name, "role": "Independent Reviewer" if readonly else "Build Engineer",
            "provider": "provider-a", "model": "selected-model", "access": "read-only" if readonly else "write",
            "workspace_id": "workspace-" + name, "branch_id": None if readonly else "branch-" + name,
            "write_scopes": [] if readonly else [scope or "code/" + name], "depends_on": list(dependencies),
            "output": "A scoped report or patch", "proof": "Record immutable head and check output"}


def plan(*jobs, parallel=2):
    return {"schema_version": 1, "base_sha": "a" * 40, "goal": "Implement one approved task",
            "integration_check": "Run the project integration command", "max_parallel": parallel,
            "jobs": list(jobs) or [worker("builder")]}


class OwnershipTests(unittest.TestCase):
    def test_disjoint_writers_have_a_bounded_batch(self):
        result = d.validate(plan(worker("one"), worker("two"), worker("three")))
        self.assertEqual(result["proposed_batches"], [["one", "three"], ["two"]])

    def test_duplicate_worker_ids_are_refused(self):
        with self.assertRaisesRegex(d.Conflict, "duplicate worker"):
            d.validate(plan(worker("one"), worker("one")))

    def test_shared_branch_is_refused_even_with_disjoint_scopes(self):
        one, two = worker("one"), worker("two")
        two["branch_id"] = one["branch_id"]
        with self.assertRaisesRegex(d.Conflict, "branch ID"):
            d.validate(plan(one, two))

    def test_writer_workspace_is_exclusive_against_writers_and_readers(self):
        for readonly in (False, True):
            one, two = worker("one"), worker("two", readonly=readonly)
            two["workspace_id"] = one["workspace_id"]
            with self.subTest(readonly=readonly), self.assertRaisesRegex(d.Conflict, "workspace"):
                d.validate(plan(one, two))

    def test_readonly_jobs_can_share_a_workspace(self):
        one, two = worker("one", readonly=True), worker("two", readonly=True)
        two["workspace_id"] = one["workspace_id"]
        self.assertTrue(d.validate(plan(one, two))["valid"])

    def test_scope_equality_and_ancestor_overlap_are_symmetric(self):
        for left, right in (("code", "code"), ("code", "code/parser"), ("code/parser", "code")):
            with self.subTest(left=left, right=right), self.assertRaisesRegex(d.Conflict, "overlap"):
                d.validate(plan(worker("one", left), worker("two", right)))

    def test_scope_segment_boundaries_do_not_confuse_siblings(self):
        self.assertTrue(d.validate(plan(worker("one", "code/parser"), worker("two", "code/parser_extra")))["valid"])

    def test_explicit_dependency_orders_shared_resource_reuse(self):
        one, two = worker("one", "code"), worker("two", "code", ["one"])
        two["workspace_id"], two["branch_id"] = one["workspace_id"], one["branch_id"]
        self.assertEqual(d.validate(plan(two, one))["proposed_batches"], [["one"], ["two"]])

    def test_transitive_dependency_orders_resource_reuse(self):
        result = d.validate(plan(worker("one", "code"), worker("two", "other", ["one"]),
                                 worker("three", "code/parser", ["two"])))
        self.assertEqual(result["proposed_batches"], [["one"], ["two"], ["three"]])

    def test_incidental_serial_batching_does_not_replace_a_dependency(self):
        with self.assertRaises(d.Conflict):
            d.validate(plan(worker("one", "code"), worker("two", "code"), parallel=1))


class DependencyTests(unittest.TestCase):
    def test_unknown_self_and_cyclic_dependencies_are_refused(self):
        samples = [plan(worker("one", dependencies=["missing"])),
                   plan(worker("one", dependencies=["one"])),
                   plan(worker("one", dependencies=["two"]), worker("two", dependencies=["one"]))]
        for value in samples:
            with self.subTest(value=value), self.assertRaises(d.Conflict):
                d.validate(value)

    def test_dependency_must_be_a_duplicate_free_list(self):
        for deps in (None, "one", [None], ["one", "one"]):
            value = plan()
            value["jobs"][0]["depends_on"] = deps
            with self.subTest(deps=deps), self.assertRaises(d.Broken):
                d.validate(value)

    def test_provider_and_model_labels_do_not_change_ownership_rules(self):
        for provider, model in (("provider-a", "selected-model"), ("provider-a", "other-model"),
                                ("provider-b", "other-model")):
            one, two = worker("one", "code"), worker("two", "code")
            two["provider"], two["model"] = provider, model
            with self.subTest(provider=provider, model=model), self.assertRaises(d.Conflict):
                d.validate(plan(one, two))

    def test_single_and_multiple_provider_labels_are_reported_without_approval_claim(self):
        one, two = worker("one"), worker("two")
        self.assertEqual(d.validate(plan(one, two))["declared_provider_labels"], ["provider-a"])
        two["provider"], two["model"] = "provider-b", "other-model"
        result = d.validate(plan(one, two))
        self.assertEqual(result["declared_provider_labels"], ["provider-a", "provider-b"])
        self.assertNotIn("approved", result)
        self.assertNotIn("cross_vendor", result)


class FormatTests(unittest.TestCase):
    def test_schema_and_parallel_types_are_strict(self):
        for key, values in (("schema_version", (True, 1.0, "1", 2, None)),
                            ("max_parallel", (False, 1.0, "2", 0, -1, None))):
            for bad in values:
                value = plan(); value[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(d.Broken):
                    d.validate(value)

    def test_each_plan_and_job_field_is_required_and_unknown_fields_fail(self):
        for location, expected in (("plan", d.PLAN_FIELDS), ("job", d.JOB_FIELDS)):
            for key in expected:
                value = plan()
                target = value if location == "plan" else value["jobs"][0]
                del target[key]
                with self.subTest(location=location, key=key), self.assertRaises(d.Broken):
                    d.validate(value)
            value = plan()
            (value if location == "plan" else value["jobs"][0])["unexpected"] = "field"
            with self.assertRaises(d.Broken):
                d.validate(value)

    def test_sha_and_logical_id_grammars_reject_near_valid_values(self):
        for key, values in (("base_sha", ("a" * 39, "A" * 40, "a" * 41, "a" * 40 + "\n", None)),
                            ("id", ("MixedCase", " space", "trailing\n", "../path", "a/b", "a:b", "", None))):
            for bad in values:
                value = plan()
                (value if key == "base_sha" else value["jobs"][0])[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(d.Broken):
                    d.validate(value)

    def test_text_fields_are_required_but_not_claimed_as_executed_checks(self):
        for key in ("goal", "integration_check", "role", "provider", "model", "output", "proof"):
            for bad in (None, "", "  ", 1, "line\nbreak", "nul\x00byte", "line\x85break", "line\u2028break", "line\u2029break"):
                value = plan()
                (value if key in ("goal", "integration_check") else value["jobs"][0])[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(d.Broken):
                    d.validate(value)

    def test_invalid_writer_and_readonly_combinations_fail(self):
        for access, scopes, branch in (("write", [], "branch"), ("read-only", ["code"], None),
                                       ("read-only", [], "branch"), ("other", [], None)):
            value = plan(); value["jobs"][0].update(access=access, write_scopes=scopes, branch_id=branch)
            with self.subTest(access=access, scopes=scopes), self.assertRaises(d.Broken):
                d.validate(value)

    def test_scope_namespace_rejects_path_alias_syntax_and_duplicates(self):
        for scopes in (["Code"], ["code/../other"], ["code//parser"], ["c:/code"], ["code\\parser"],
                       ["code/"], ["code", "code"], [None], "code"):
            value = plan(); value["jobs"][0]["write_scopes"] = scopes
            with self.subTest(scopes=scopes), self.assertRaises(d.Broken):
                d.validate(value)

    def test_nonobject_empty_jobs_and_nonobject_job_fail(self):
        for value in (None, [], {}, dict(plan(), jobs=[]), dict(plan(), jobs=[None]), dict(plan(), jobs={})):
            with self.subTest(value=value), self.assertRaises(d.Broken):
                d.validate(value)

    def test_validation_does_not_mutate_the_input(self):
        value = plan(worker("one"), worker("two", dependencies=["one"]))
        before = copy.deepcopy(value)
        d.validate(value)
        self.assertEqual(value, before)


class CliTests(unittest.TestCase):
    def run_cli(self, path):
        return subprocess.run([sys.executable, "-B", str(HERE / "dispatch_plan.py"), "check", str(path)],
                              capture_output=True, text=True, encoding="utf-8")

    def test_actual_cli_exit_codes_and_no_plan_rewrites(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "plan.json"
            for value, expected in ((plan(), 0), (plan(worker("same"), worker("same")), 1), ({}, 2)):
                before = json.dumps(value).encode()
                path.write_bytes(before)
                result = self.run_cli(path)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(path.read_bytes(), before)

    def test_missing_invalid_utf8_duplicate_fields_and_decoder_limits_are_concise(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "plan.json"
            for payload in (None, b'{bad', b'\xff', b'{"jobs":[],"jobs":[]}',
                            ("[" * 5000 + "0" + "]" * 5000).encode(), ("[" + "8" * 6000 + "]").encode()):
                if payload is not None:
                    path.write_bytes(payload)
                with self.subTest(payload=None if payload is None else payload[:20]):
                    result = self.run_cli(path)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("ERROR:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_unicode_labels_are_json_safe_and_no_worker_is_launched(self):
        value = plan()
        value["jobs"][0]["model"] = "modelo-示例"
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "plan.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            result = self.run_cli(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("modelo-示例", json.loads(result.stdout)["declared_model_pairs"][0])
            self.assertEqual(list(Path(scratch).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
