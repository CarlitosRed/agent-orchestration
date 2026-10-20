"""Tests for the blinded-eval assignment tool. Offline, throw-away temp folders only.

Run:  python -m unittest discover -s tools/blinded-eval -p "test_blind.py" -v
"""
import io
import json
import os
import shutil
import tempfile
import unittest

import blind as B


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="blind-test-")
        self.out = os.path.join(self.dir, "eval-1")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def file(self, name, text):
        full = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
        return full

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = B.main(list(argv), out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, f"{argv[0]} failed: {err}")
        return out

    def refused(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 1, f"expected refusal, got {code}: {out}{err}")
        self.assertIn("REFUSED", err)
        return err


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class AssignTests(Base):
    def test_assign_creates_both_variants_with_real_content(self):
        # deliberately named old.md / new.md - the whole point is the blinded copy must not keep this name
        a = self.file("old.md", "old version")
        b = self.file("new.md", "new version")
        self.ok("assign", "--a", a, "--b", b, "--out", self.out, "--seed", "1")
        v1 = _read(self.out, "variant-1", "content.md")
        v2 = _read(self.out, "variant-2", "content.md")
        self.assertEqual({v1, v2}, {"old version", "new version"})

    def test_a_file_sources_original_name_is_not_leaked_into_the_blinded_copy(self):
        a = self.file("old.md", "old version")
        b = self.file("new.md", "new version")
        self.ok("assign", "--a", a, "--b", b, "--out", self.out, "--seed", "1")
        for slot in ("variant-1", "variant-2"):
            names = os.listdir(os.path.join(self.out, slot))
            self.assertNotIn("old.md", names)
            self.assertNotIn("new.md", names)
            self.assertEqual(names, ["content.md"])

    def test_assign_seals_a_mapping_file(self):
        a = self.file("old.md", "old")
        b = self.file("new.md", "new")
        self.ok("assign", "--a", a, "--b", b, "--out", self.out, "--seed", "1")
        mapping_path = os.path.join(self.out, ".mapping.json")
        self.assertTrue(os.path.exists(mapping_path))
        with open(mapping_path, encoding="utf-8") as f:
            mapping = json.load(f)
        self.assertEqual(set(mapping), {"variant-1", "variant-2"})
        self.assertEqual({mapping["variant-1"]["label"], mapping["variant-2"]["label"]}, {"a", "b"})

    def test_assign_refuses_an_existing_out_dir(self):
        a = self.file("old.md", "old")
        b = self.file("new.md", "new")
        os.makedirs(self.out)
        self.refused("assign", "--a", a, "--b", b, "--out", self.out)

    def test_assign_errors_on_missing_source(self):
        b = self.file("new.md", "new")
        code, out, err = self.run_cli("assign", "--a", os.path.join(self.dir, "missing.md"),
                                       "--b", b, "--out", self.out)
        self.assertEqual(code, 2, out + err)
        self.assertFalse(os.path.exists(self.out))

    def test_works_with_directories_not_just_files(self):
        a_dir = os.path.join(self.dir, "skill-a")
        b_dir = os.path.join(self.dir, "skill-b")
        os.makedirs(a_dir)
        os.makedirs(b_dir)
        with open(os.path.join(a_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("a content")
        with open(os.path.join(b_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("b content")
        self.ok("assign", "--a", a_dir, "--b", b_dir, "--out", self.out, "--seed", "1")
        v1 = _read(self.out, "variant-1", "SKILL.md")
        v2 = _read(self.out, "variant-2", "SKILL.md")
        self.assertEqual({v1, v2}, {"a content", "b content"})

    def test_same_seed_is_deterministic(self):
        a = self.file("old.md", "old")
        b = self.file("new.md", "new")
        out1 = os.path.join(self.dir, "eval-a")
        out2 = os.path.join(self.dir, "eval-b")
        self.ok("assign", "--a", a, "--b", b, "--out", out1, "--seed", "42")
        self.ok("assign", "--a", a, "--b", b, "--out", out2, "--seed", "42")
        with open(os.path.join(out1, ".mapping.json"), encoding="utf-8") as fh:
            m1 = json.load(fh)
        with open(os.path.join(out2, ".mapping.json"), encoding="utf-8") as fh:
            m2 = json.load(fh)
        self.assertEqual(m1["variant-1"]["label"], m2["variant-1"]["label"])

    def test_different_seeds_can_produce_different_assignments(self):
        a = self.file("old.md", "old")
        b = self.file("new.md", "new")
        labels = set()
        for seed in range(10):
            out = os.path.join(self.dir, f"eval-{seed}")
            self.ok("assign", "--a", a, "--b", b, "--out", out, "--seed", str(seed))
            with open(os.path.join(out, ".mapping.json"), encoding="utf-8") as fh:
                m = json.load(fh)
            labels.add(m["variant-1"]["label"])
        self.assertEqual(labels, {"a", "b"}, "across 10 different seeds, both assignments should occur")


class RevealTests(Base):
    def test_reveal_shows_the_real_mapping(self):
        a = self.file("old.md", "old")
        b = self.file("new.md", "new")
        self.ok("assign", "--a", a, "--b", b, "--out", self.out, "--seed", "1")
        out = self.ok("reveal", "--out", self.out)
        self.assertIn("variant-1:", out)
        self.assertIn("variant-2:", out)
        self.assertIn(os.path.abspath(a), out)
        self.assertIn(os.path.abspath(b), out)

    def test_reveal_without_assign_is_an_error(self):
        os.makedirs(self.out)
        code, out, err = self.run_cli("reveal", "--out", self.out)
        self.assertEqual(code, 2, out + err)
        self.assertIn("no mapping found", err)


if __name__ == "__main__":
    unittest.main()
