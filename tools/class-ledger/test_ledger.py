"""Tests for the class ledger. Offline, throw-away temp folders only.

Run:  python -m unittest discover -s tools/class-ledger -p "test_ledger.py" -v
"""
import io
import json
import os
import shutil
import tempfile
import unittest

import ledger as L

REV_A = "Independent Reviewer · Alpha"
REV_B = "Independent Reviewer · Beta"
BUILD_B = "Build Engineer · Beta"
BUILD_A = "Build Engineer · Alpha"
ORCH = "Orchestrator · Alpha"
GEN = "any token that is a valid word in both supported languages"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-test-")
        self.path = os.path.join(self.dir, "pr-7.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = L.main([argv[0], self.path, *argv[1:]], out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, f"{argv[0]} failed: {err}")
        return out

    def refused(self, *argv):
        before = self.raw()
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 1, f"expected refusal, got {code}: {out}{err}")
        self.assertIn("REFUSED", err)
        self.assertEqual(before, self.raw(), "a refused command must not write")
        return err

    def raw(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path, "rb") as fh:
            return fh.read()

    def data(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def metrics(self):
        return json.loads(self.ok("report", "--json"))

    def init(self, budget=3):
        self.ok("init", "--pr", "7", "--budget", str(budget), "--head", "a" * 40)

    def find(self, cls, by=REV_A, sev="P2", file="app/words.py:10", gen=None, extra=()):
        args = ["add-finding", "--class", cls, "--by", by, "--severity", sev, "--file", file,
                "--counterexample", "word 'x' passes", "--repro", "python probe.py x"]
        if gen:
            args += ["--generator", gen]
        return self.run_cli(*args, *extra)

    def found(self, *a, **k):
        code, out, err = self.find(*a, **k)
        self.assertEqual(code, 0, err)
        return out

    def close(self, cls, by=BUILD_B, extra=()):
        return self.run_cli("close-class", cls, "--by", by, "--evidence", "comment 123",
                            "--sweep-cmd", "python sweep.py --all-words", *extra)


class InitTests(Base):
    def test_init_creates_round_one(self):
        self.init()
        d = self.data()
        self.assertEqual((d["round"], d["budget"], d["pr"]), (1, 3, "7"))

    def test_init_twice_refused(self):
        self.init()
        self.refused("init", "--pr", "7")

    def test_bad_budget(self):
        code, _, _ = self.run_cli("init", "--pr", "7", "--budget", "0")
        self.assertEqual(code, 2)

    def test_missing_ledger_is_error(self):
        code, _, err = self.run_cli("status")
        self.assertEqual(code, 2)
        self.assertIn("init first", err)

    def test_wrong_schema_is_error(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"schema_version": 99}, fh)
        self.assertEqual(self.run_cli("status")[0], 2)

    def test_corrupt_file_is_error(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(self.run_cli("status")[0], 2)

    def test_file_is_sorted_and_diffable(self):
        self.init()
        self.found("dual-token", gen=GEN)
        text = self.raw().decode("utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\r", text)
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def test_unknown_command_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(L.main(["frobnicate"], out=out, err=err), 2)


class FindingTests(Base):
    def setUp(self):
        super().setUp()
        self.init()

    def test_new_class_needs_generator(self):
        code, _, err = self.find("dual-token")
        self.assertEqual(code, 2)
        self.assertIn("generator", err)

    def test_bad_slug(self):
        code, _, _ = self.find("Dual Token", gen=GEN)
        self.assertEqual(code, 2)

    def test_bad_severity(self):
        code, _, _ = self.find("dual-token", sev="P0", gen=GEN)
        self.assertEqual(code, 2)

    def test_empty_counterexample(self):
        code, _, _ = self.run_cli("add-finding", "--class", "c", "--by", REV_A, "--severity", "P2", "--file", "f",
                                  "--counterexample", "  ", "--repro", "r", "--generator", GEN)
        self.assertEqual(code, 2)

    def test_new_class_then_instance(self):
        self.found("dual-token", gen=GEN)
        out = self.found("dual-token", file="app/words.py:22")
        self.assertIn("instance of open class", out)
        m = self.metrics()
        self.assertEqual(m["instances_per_class"], {"dual-token": 2})
        self.assertEqual(m["per_round"]["1"], {"findings": 2, "new_classes": 1, "instances": 1, "reopens": 0, "duplicates": 0})

    def test_severity_raises_to_worst(self):
        self.found("dual-token", sev="P3", gen=GEN)
        self.found("dual-token", sev="P1", file="x:1")
        self.found("dual-token", sev="P2", file="x:2")
        self.assertEqual(self.data()["classes"]["dual-token"]["severity"], "P1")

    def test_vendor_parsed_from_signature(self):
        self.found("dual-token", gen=GEN)
        self.assertEqual(self.data()["findings"][0]["vendor"], "alpha")

    def test_both_vendors_marks_priority(self):
        self.found("dual-token", by=REV_A, gen=GEN)
        self.found("dual-token", by=REV_B, file="app/words.py:30")
        self.assertEqual(self.metrics()["both_vendor_classes"], ["dual-token"])

    def test_one_vendor_twice_is_not_both(self):
        self.found("dual-token", gen=GEN)
        self.found("dual-token", file="x:2")
        self.assertEqual(self.metrics()["both_vendor_classes"], [])

    def test_lookalike_generator_refused(self):
        self.found("dual-token", gen=GEN)
        err = self.refused("add-finding", "--class", "shared-words", "--by", REV_A, "--severity", "P2",
                           "--file", "other.py:1", "--counterexample", "c", "--repro", "r",
                           "--generator", "any word that is valid in both languages")
        self.assertIn("dual-token", err)

    def test_same_location_refused(self):
        self.found("dual-token", gen=GEN)
        code, _, err = self.find("encoding-bom", gen="any file written with a byte order mark")
        self.assertEqual(code, 1)
        self.assertIn("same file:line", err)

    def test_distinct_from_overrides_lookalike(self):
        self.found("dual-token", gen=GEN)
        out = self.found("encoding-bom", gen="any file written with a byte order mark",
                         extra=("--distinct-from", "dual-token"))
        self.assertIn("new class", out)
        self.assertEqual(self.data()["classes"]["encoding-bom"]["distinct_from"], ["dual-token"])

    def test_distinct_from_unknown_class(self):
        code, _, _ = self.find("x", gen=GEN, extra=("--distinct-from", "nope"))
        self.assertEqual(code, 2)

    def test_unrelated_new_class_allowed(self):
        self.found("dual-token", gen=GEN)
        self.found("unpinned-version", file="docs/a.md:3", gen="any version number in docs with no pinned source")
        self.assertEqual(self.metrics()["classes_opened"], 2)


class LifecycleTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.found("dual-token", gen=GEN)
        self.found("dual-token", file="app/words.py:22")

    def to_round2(self):
        # Sorting happens before the builder closes; a closed class does not block the next round.
        self.ok("new-round", "--head", "b" * 40)

    def test_close_needs_evidence_and_sweep(self):
        code, _, _ = self.run_cli("close-class", "dual-token", "--by", BUILD_B, "--evidence", "",
                                  "--sweep-cmd", "s")
        self.assertEqual(code, 2)
        code, _, _ = self.run_cli("close-class", "dual-token", "--by", BUILD_B, "--evidence", "e",
                                  "--sweep-cmd", " ")
        self.assertEqual(code, 2)

    def test_close_records_and_hashes_output(self):
        out_file = os.path.join(self.dir, "sweep.txt")
        with open(out_file, "wb") as fh:
            fh.write(b"0 instances\nchecked 4120 words\n")
        code, _, err = self.close("dual-token", extra=("--sweep-output", out_file))
        self.assertEqual(code, 0, err)
        c = self.data()["classes"]["dual-token"]
        self.assertEqual(c["state"], "closed")
        self.assertEqual(c["closures"][0]["sweep_output"]["lines"], 2)
        self.assertEqual(len(c["closures"][0]["sweep_output"]["sha256"]), 64)

    def test_close_missing_output_file(self):
        code, _, _ = self.close("dual-token", extra=("--sweep-output", os.path.join(self.dir, "nope")))
        self.assertEqual(code, 2)

    def test_close_twice_refused(self):
        self.assertEqual(self.close("dual-token")[0], 0)
        self.assertEqual(self.close("dual-token")[0], 1)

    def test_close_unknown(self):
        self.assertEqual(self.close("nope")[0], 1)

    def test_instance_after_close_is_reopen_not_new(self):
        self.close("dual-token")
        self.to_round2()
        out = self.found("dual-token", file="app/menu.py:5")
        self.assertIn("REOPEN", out)
        d = self.data()
        self.assertEqual(d["classes"]["dual-token"]["state"], "reopened")
        self.assertEqual(d["findings"][-1]["kind"], "reopen")
        m = self.metrics()
        self.assertEqual(m["reopen_count"], 1)
        self.assertEqual(m["classes_opened"], 1)
        self.assertEqual(m["per_round"]["2"], {"findings": 1, "new_classes": 0, "instances": 0, "reopens": 1, "duplicates": 0})
        self.assertEqual(m["needs_different_agent"], ["dual-token"])
        self.assertFalse(m["exit_ready"])

    def test_reopened_class_same_closer_refused(self):
        self.close("dual-token")
        self.to_round2()
        self.found("dual-token", file="app/menu.py:5")
        err = self.refused("close-class", "dual-token", "--by", BUILD_B, "--evidence", "e", "--sweep-cmd", "s")
        self.assertIn("DIFFERENT agent", err)

    def test_reopened_same_closer_case_and_spacing_refused(self):
        self.close("dual-token")
        self.found("dual-token", file="app/menu.py:5")
        code, _, _ = self.close("dual-token", by="build engineer  ·  BETA")
        self.assertEqual(code, 1)

    def test_reopened_class_different_closer_ok(self):
        self.close("dual-token")
        self.found("dual-token", file="app/menu.py:5")
        self.assertEqual(self.close("dual-token", by=BUILD_A)[0], 0)
        c = self.data()["classes"]["dual-token"]
        self.assertEqual(c["closers"], [BUILD_B, BUILD_A])
        self.assertEqual(self.metrics()["needs_different_agent"], [])

    def test_second_reopen_needs_a_third_agent(self):
        self.close("dual-token")
        self.found("dual-token", file="a:1")
        self.close("dual-token", by=BUILD_A)
        self.found("dual-token", file="a:2")
        self.assertEqual(self.data()["classes"]["dual-token"]["reopen_count"], 2)
        self.assertEqual(self.close("dual-token", by=BUILD_A)[0], 1)
        self.assertEqual(self.close("dual-token", by=BUILD_B)[0], 1)
        self.assertEqual(self.close("dual-token", by="Platform Engineer · Alpha")[0], 0)

    def test_renamed_class_dodge_refused_in_round2(self):
        self.close("dual-token")
        self.to_round2()
        code, _, err = self.find("bilingual-word", file="app/menu.py:5",
                                 gen="any token that is a word in both languages",
                                 extra=("--new-reason", "different file"))
        self.assertEqual(code, 1)
        self.assertIn("dual-token", err)

    def test_new_class_in_round2_needs_reason(self):
        self.close("dual-token")
        self.to_round2()
        code, _, err = self.find("unpinned-version", file="docs/a.md:3",
                                 gen="any version number in docs with no pinned source")
        self.assertEqual(code, 2)
        self.assertIn("new-reason", err)

    def test_new_class_in_round2_listed_for_review(self):
        self.close("dual-token")
        self.to_round2()
        self.found("unpinned-version", file="docs/a.md:3", gen="any version number in docs with no pinned source",
                   extra=("--new-reason", "docs pins, not tokens"))
        m = self.metrics()
        self.assertEqual(m["new_classes_after_round_1"],
                         [{"class": "unpinned-version", "round": 2, "reason": "docs pins, not tokens",
                           "distinct_from": []}])
        self.assertIn("confirm each", self.ok("status"))

    def test_verify_needs_different_generator(self):
        self.close("dual-token")
        self.to_round2()
        err = self.refused("verify-class", "dual-token", "--by", REV_A, "--generator-used", "  ANY token that is "
                           "a valid word in both supported LANGUAGES ", "--evidence", "e")
        self.assertIn("DIFFERENT", err)
        self.ok("verify-class", "dual-token", "--by", REV_A, "--generator-used",
                "every dictionary entry of language 2 checked against language 1 list", "--evidence", "notes r2")
        self.assertEqual(len(self.data()["classes"]["dual-token"]["verifications"]), 1)

    def test_verify_open_class_refused(self):
        self.refused("verify-class", "dual-token", "--by", REV_A, "--generator-used", "x", "--evidence", "e")

    def test_exit_ready_after_clean_round(self):
        self.close("dual-token")
        self.to_round2()
        self.ok("verify-class", "dual-token", "--by", REV_A, "--generator-used", "other", "--evidence", "e")
        m = self.metrics()
        self.assertTrue(m["exit_ready"])
        self.assertEqual(m["classes_closed"], 1)

    def test_not_exit_ready_with_open_p2(self):
        self.assertFalse(self.metrics()["exit_ready"])
        self.assertEqual(self.metrics()["blocking_classes"], ["dual-token"])

    def test_noted_p2_does_not_block_but_new_class_in_round_does(self):
        self.ok("sort", "dual-token", "--bucket", "noted", "--by", ORCH)
        m = self.metrics()
        self.assertEqual(m["blocking_classes"], [])
        self.assertFalse(m["exit_ready"])  # round 1 itself raised a new class
        self.ok("new-round", "--head", "c" * 40)
        self.assertTrue(self.metrics()["exit_ready"])

    def test_open_p3_does_not_block(self):
        self.found("typo", sev="P3", file="docs/x.md:1", gen="any misspelt heading")
        self.ok("sort", "typo", "--bucket", "act", "--by", ORCH)
        self.assertEqual(self.metrics()["blocking_classes"], ["dual-token"])


class SortTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.found("dual-token", gen=GEN)

    def test_bad_bucket(self):
        code, _, _ = self.run_cli("sort", "dual-token", "--bucket", "maybe", "--by", ORCH)
        self.assertEqual(code, 2)

    def test_dismiss_needs_reason(self):
        code, _, _ = self.run_cli("sort", "dual-token", "--bucket", "dismissed", "--by", ORCH)
        self.assertEqual(code, 2)

    def test_dismiss_and_restore(self):
        self.ok("sort", "dual-token", "--bucket", "dismissed", "--by", ORCH, "--reason", "spec allows it")
        self.assertEqual(self.data()["classes"]["dual-token"]["state"], "dismissed")
        self.assertEqual(self.metrics()["classes_dismissed"], 1)
        self.ok("sort", "dual-token", "--bucket", "act", "--by", ORCH)
        self.assertEqual(self.data()["classes"]["dual-token"]["state"], "open")

    def test_finding_on_dismissed_is_recorded_not_reopen(self):
        self.ok("sort", "dual-token", "--bucket", "dismissed", "--by", ORCH, "--reason", "r")
        out = self.found("dual-token", file="x:9")
        self.assertIn("DISMISSED", out)
        self.assertEqual(self.metrics()["reopen_count"], 0)

    def test_sort_closed_refused(self):
        self.ok("sort", "dual-token", "--bucket", "act", "--by", ORCH)
        self.close("dual-token")
        self.refused("sort", "dual-token", "--bucket", "noted", "--by", ORCH)

    def test_buckets_counted(self):
        self.ok("sort", "dual-token", "--bucket", "consider", "--by", ORCH)
        self.assertEqual(self.metrics()["buckets"]["consider"], 1)


class RoundTests(Base):
    def setUp(self):
        super().setUp()
        self.init(budget=3)

    def test_unsorted_blocks_new_round(self):
        self.found("dual-token", gen=GEN)
        err = self.refused("new-round", "--head", "b" * 40)
        self.assertIn("dual-token", err)

    def test_consider_blocks_new_round(self):
        self.found("dual-token", gen=GEN)
        self.ok("sort", "dual-token", "--bucket", "consider", "--by", ORCH)
        self.refused("new-round", "--head", "b" * 40)

    def test_closed_unsorted_does_not_block(self):
        self.found("dual-token", gen=GEN)
        self.close("dual-token")
        self.ok("new-round", "--head", "b" * 40)

    def test_budget_then_final_round_then_owner(self):
        self.ok("new-round", "--head", "b" * 40)
        self.ok("new-round", "--head", "c" * 40)
        err = self.refused("new-round", "--head", "d" * 40)
        self.assertIn("escalation-sweep", err)
        self.ok("new-round", "--head", "d" * 40, "--escalation-sweep", "comment 555")
        self.assertTrue(self.metrics()["over_budget"])
        err = self.refused("new-round", "--head", "e" * 40, "--escalation-sweep", "again")
        self.assertIn("owner", err)
        self.ok("new-round", "--head", "e" * 40, "--owner-decision", "owner comment 600")
        self.assertEqual(self.data()["rounds"][-1]["owner_decision"], "owner comment 600")

    def test_findings_stamped_with_round(self):
        self.found("dual-token", gen=GEN)
        self.ok("sort", "dual-token", "--bucket", "act", "--by", ORCH)
        self.ok("new-round", "--head", "b" * 40)
        self.found("dual-token", file="x:2")
        self.assertEqual([f["round"] for f in self.data()["findings"]], [1, 2])


class MergeTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.found("dual-token", by=REV_A, gen=GEN)
        self.found("record-shape", by=REV_B, sev="P1", file="runner.py:40",
                   gen="any runner record missing a field the reader expects")

    def test_merge_moves_findings_and_vendors(self):
        self.ok("merge-classes", "record-shape", "--into", "dual-token", "--by", ORCH, "--reason", "same root")
        d = self.data()
        self.assertEqual(d["classes"]["record-shape"]["state"], "merged")
        self.assertEqual(d["classes"]["dual-token"]["severity"], "P1")
        self.assertEqual(sorted(d["classes"]["dual-token"]["raised_by_vendors"]), ["alpha", "beta"])
        m = self.metrics()
        self.assertEqual(m["classes_opened"], 1)
        self.assertEqual(m["classes_merged"], 1)
        self.assertEqual(m["instances_per_class"], {"dual-token": 2})

    def test_finding_on_merged_class_refused(self):
        self.ok("merge-classes", "record-shape", "--into", "dual-token", "--by", ORCH, "--reason", "r")
        code, _, err = self.find("record-shape", file="z:1")
        self.assertEqual(code, 1)
        self.assertIn("merged", err)

    def test_merge_into_self(self):
        code, _, _ = self.run_cli("merge-classes", "dual-token", "--into", "dual-token", "--by", ORCH,
                                  "--reason", "r")
        self.assertEqual(code, 2)

    def test_merge_needs_reason(self):
        code, _, _ = self.run_cli("merge-classes", "record-shape", "--into", "dual-token", "--by", ORCH,
                                  "--reason", "")
        self.assertEqual(code, 2)


class DuplicateTests(Base):
    def setUp(self):
        super().setUp()
        self.init()
        self.found("dual-token", by=REV_A, gen=GEN)

    def test_same_instance_other_vendor_same_round_counts_once(self):
        out = self.found("dual-token", by=REV_B)
        self.assertIn("same instance as F1", out)
        m = self.metrics()
        self.assertEqual(m["instances_per_class"], {"dual-token": 1})
        self.assertEqual(m["both_vendor_classes"], ["dual-token"])
        self.assertEqual(m["per_round"]["1"]["duplicates"], 1)

    def test_counterexample_compared_ignoring_case_and_spacing(self):
        code, _, err = self.run_cli("add-finding", "--class", "dual-token", "--by", REV_B, "--severity", "P2",
                                    "--file", "app/words.py:10", "--counterexample", "  WORD 'x'   passes",
                                    "--repro", "other probe")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.data()["findings"][-1]["kind"], "duplicate")

    def test_same_instance_after_close_in_later_round_is_reopen(self):
        self.ok("sort", "dual-token", "--bucket", "act", "--by", ORCH)
        self.close("dual-token")
        self.ok("new-round", "--head", "b" * 40)
        out = self.found("dual-token", by=REV_A)
        self.assertIn("REOPEN", out)
        self.assertEqual(self.metrics()["reopen_count"], 1)

    def test_different_file_is_not_duplicate(self):
        self.found("dual-token", by=REV_B, file="app/words.py:11")
        self.assertEqual(self.metrics()["instances_per_class"], {"dual-token": 2})


class OutputTests(Base):
    def test_status_and_report_text(self):
        self.init()
        self.found("dual-token", gen=GEN)
        out = self.ok("status")
        self.assertIn("dual-token", out)
        self.assertIn("exit ready: no", out)
        rep = self.ok("report")
        self.assertTrue(rep.lstrip().startswith("{"))
        self.assertIn("class", rep)

    def test_non_ascii_survives(self):
        self.init()
        self.found("café-x".encode("ascii", "ignore").decode() or "cafe", gen="any word like café")
        self.assertIn("café", self.raw().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
