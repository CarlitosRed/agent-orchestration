"""Tests for the verify-manifest helper. Offline, throw-away temp folders only.

Run:  python -m unittest discover -s tools/verify-manifest -p "test_manifest.py" -v
"""
import io
import json
import os
import shutil
import tempfile
import unittest

import manifest as M


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="verify-manifest-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, rel_path, content="hello"):
        full = os.path.join(self.dir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return full

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = M.main(list(argv), out=out, err=err)
        return code, out.getvalue(), err.getvalue()


class FindVerifyRoot(Base):
    def test_standard_layout_from_script_path(self):
        script = self.write(os.path.join(".orchestration", "verify", "doctor.py"), "# doctor")
        root = M.find_verify_root(script)
        self.assertEqual(os.path.normpath(root), os.path.normpath(self.dir))

    def test_from_a_directory_not_a_file(self):
        script = self.write(os.path.join(".orchestration", "verify", "doctor.py"), "# doctor")
        verify_dir = os.path.dirname(script)
        root = M.find_verify_root(verify_dir)
        self.assertEqual(os.path.normpath(root), os.path.normpath(self.dir))

    def test_deeper_nesting_under_verify_still_resolves(self):
        # Reproduces the class behind L49: a script one level deeper than usual must
        # not need a different hard-coded hop count to find root.
        script = self.write(os.path.join(".orchestration", "verify", "helpers", "doctor.py"), "# doctor")
        root = M.find_verify_root(script)
        self.assertEqual(os.path.normpath(root), os.path.normpath(self.dir))

    def test_no_orchestration_ancestor_raises(self):
        script = self.write(os.path.join("somewhere", "else.py"), "# x")
        with self.assertRaises(M.Broken):
            M.find_verify_root(script)

    def test_cli_find_root(self):
        script = self.write(os.path.join(".orchestration", "verify", "doctor.py"), "# doctor")
        code, out, err = self.run_cli("find-root", script)
        self.assertEqual(code, 0, err)
        self.assertEqual(os.path.normpath(out.strip()), os.path.normpath(self.dir))


class HashAndSurvival(Base):
    def test_sha256_of_known_content(self):
        path = self.write("a.txt", "hello")
        # sha256("hello") is a well-known test vector
        self.assertEqual(
            M.sha256_of(path),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )

    def test_build_entry_has_path_size_hash(self):
        path = self.write("a.txt", "hello")
        entry = M.build_entry(path)
        self.assertEqual(entry["path"], path)
        self.assertEqual(entry["size"], 5)
        self.assertEqual(entry["sha256"], M.sha256_of(path))

    def test_survival_clean_when_untouched(self):
        path = self.write("evidence/shot1.png", "pixels")
        entries = [M.build_entry(path)]
        self.assertEqual(M.verify_survival(entries, base_dir=self.dir), [])

    def test_survival_catches_missing_file(self):
        path = self.write("evidence/shot1.png", "pixels")
        entries = [M.build_entry(path)]
        os.remove(path)
        mismatches = M.verify_survival(entries, base_dir=self.dir)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["reason"], "missing")

    def test_survival_catches_changed_content(self):
        path = self.write("evidence/shot1.png", "pixels")
        entries = [M.build_entry(path)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("different pixels")
        mismatches = M.verify_survival(entries, base_dir=self.dir)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["reason"], "size")

    def test_survival_catches_same_size_different_hash(self):
        path = self.write("evidence/shot1.png", "pixels")
        entries = [M.build_entry(path)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("PIXELS")  # same length, different content
        mismatches = M.verify_survival(entries, base_dir=self.dir)
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["reason"], "hash")

    def test_cli_verify_survival_ok(self):
        path = self.write("evidence/shot1.png", "pixels")
        manifest_path = self.write("evidence/manifest.json", "")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"evidence": [M.build_entry(path)]}, f)
        code, out, err = self.run_cli("verify-survival", manifest_path, "--base", self.dir)
        self.assertEqual(code, 0, err)
        self.assertIn("ok", out)

    def test_cli_verify_survival_fails_on_mismatch(self):
        path = self.write("evidence/shot1.png", "pixels")
        entry = M.build_entry(path)
        manifest_path = self.write("evidence/manifest.json", "")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"evidence": [entry]}, f)
        os.remove(path)
        code, out, err = self.run_cli("verify-survival", manifest_path, "--base", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("missing", out)


if __name__ == "__main__":
    unittest.main()
