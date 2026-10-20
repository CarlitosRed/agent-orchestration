import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hygiene  # noqa: E402

WORD = "zebrafish"
WORD_HASH = hashlib.sha256(WORD.encode()).hexdigest()


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


class Repo:
    def __init__(self, test, files, config):
        self.root = tempfile.mkdtemp()
        test.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "Tester")
        self.write(".orchestration/hygiene.json", json.dumps(config))
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")

    def write(self, rel, text):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)

    def check(self):
        lines = []
        code = hygiene.run(self.root, os.path.join(self.root, ".orchestration", "hygiene.json"), out=lines.append)
        return code, "\n".join(lines)


class VendorWordTests(unittest.TestCase):
    CFG = {"vendor_words": ["acme"], "vendor_free_paths": ["rules/*", "templates/*"]}

    def test_vendor_name_in_a_vendor_free_path_fails_with_file_and_line(self):
        code, out = Repo(self, {"rules/r.md": "ok\nUse Acme here\n"}, self.CFG).check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL vendor-words: rules/r.md:2:", out)

    def test_vendor_name_in_vendors_folder_is_allowed(self):
        code, _ = Repo(self, {"vendors/acme.md": "Acme\n", "rules/r.md": "clean\n"}, self.CFG).check()
        self.assertEqual(code, 0)

    def test_whole_words_only(self):
        code, _ = Repo(self, {"rules/r.md": "acmeware is a different word\n"}, self.CFG).check()
        self.assertEqual(code, 0)


class LogRowTests(unittest.TestCase):
    CFG = {"log_files": [{"path": "docs/decisions.md", "max_chars": 40, "since": "2026-10-20"}]}

    def rows(self, *rows):
        return {"docs/decisions.md": "# log\n| date | d |\n" + "\n".join(rows) + "\n"}

    def test_old_long_row_is_grandfathered(self):
        code, _ = Repo(self, self.rows("| 2026-10-19 | " + "x" * 200 + " |"), self.CFG).check()
        self.assertEqual(code, 0)

    def test_new_long_row_fails(self):
        code, out = Repo(self, self.rows("| 2026-10-20 | " + "x" * 200 + " |"), self.CFG).check()
        self.assertEqual(code, 1)
        self.assertIn("docs/decisions.md:3: row is", out)

    def test_new_short_row_passes(self):
        code, _ = Repo(self, self.rows("| 2026-10-21 | short |"), self.CFG).check()
        self.assertEqual(code, 0)

    def test_untracked_log_file_fails(self):
        code, out = Repo(self, {"x.md": "x\n"}, self.CFG).check()
        self.assertEqual(code, 1)
        self.assertIn("log file is not tracked", out)


class DerivableNumberTests(unittest.TestCase):
    CFG = {"no_derivable_numbers": {"paths": ["README.md"], "patterns": [r"\b\d+ tests?\b", r"\bR1-R\d+"]}}

    def test_count_in_readme_fails(self):
        code, out = Repo(self, {"README.md": "fine\nthe gate (231 tests)\n"}, self.CFG).check()
        self.assertEqual(code, 1)
        self.assertIn("README.md:2: derivable number '231 tests'", out)

    def test_rule_range_fails(self):
        code, _ = Repo(self, {"README.md": "rules R1-R27\n"}, self.CFG).check()
        self.assertEqual(code, 1)

    def test_prose_without_numbers_passes(self):
        code, _ = Repo(self, {"README.md": "all offline tests pass\n"}, self.CFG).check()
        self.assertEqual(code, 0)


class NameSweepTests(unittest.TestCase):
    def cfg(self, exempt=()):
        return {"sweep": {"hash_file": ".orchestration/sweep-hashes.txt", "exempt_files": list(exempt)}}

    def repo(self, files, exempt=()):
        files = dict(files)
        files[".orchestration/sweep-hashes.txt"] = f"# a test word, hash only\n{WORD_HASH}\n"
        return Repo(self, files, self.cfg(exempt))

    def test_word_in_any_file_type_fails_without_printing_the_word(self):
        code, out = self.repo({"data/x.json": '{"a": "Hello, Zebrafish!"}\n'}).check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL name-sweep: data/x.json:1:", out)
        self.assertNotIn(WORD, out.lower())

    def test_case_and_possessive_are_caught(self):
        code, _ = self.repo({"a.md": "ZEBRAFISH's tank\n"}).check()
        self.assertEqual(code, 1)

    def test_exempt_file_is_skipped(self):
        code, _ = self.repo({"audits/old.md": f"{WORD}\n", "ok.md": "clean\n"}, exempt=["audits/old.md"]).check()
        self.assertEqual(code, 0)

    def test_a_longer_word_containing_it_is_not_a_hit(self):
        code, _ = self.repo({"a.md": "zebrafishes and zebrafishtank\n"}).check()
        self.assertEqual(code, 0)

    def test_binary_file_is_ignored(self):
        r = self.repo({"ok.md": "clean\n"})
        with open(os.path.join(r.root, "blob.bin"), "wb") as stream:
            stream.write(b"\x89PNG\r\n\x1a\n\x00\x00" + WORD.encode())
        git(r.root, "add", "-A")
        self.assertEqual(r.check()[0], 0)


class EncodingAndHashTests(unittest.TestCase):
    def sweep_repo(self, files, hash_text=None):
        files = dict(files)
        files[".orchestration/sweep-hashes.txt"] = hash_text if hash_text is not None else f"{WORD_HASH}\n"
        cfg = {"vendor_words": ["acme"], "vendor_free_paths": ["rules/*"],
               "sweep": {"hash_file": ".orchestration/sweep-hashes.txt", "exempt_files": []}}
        return Repo(self, files, cfg)

    def test_utf16_with_a_byte_order_mark_is_still_checked(self):
        r = self.sweep_repo({"ok.md": "clean\n"})
        for rel, text in (("rules/r.md", "Acme\n"), ("notes.md", f"{WORD}\n")):
            path = os.path.join(r.root, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as stream:
                stream.write(b"\xff\xfe" + text.encode("utf-16-le"))
        git(r.root, "add", "-A")
        code, out = r.check()
        self.assertEqual(code, 1)
        self.assertIn("FAIL vendor-words: rules/r.md:1:", out)
        self.assertIn("FAIL name-sweep: notes.md:1:", out)

    def test_utf8_with_a_byte_order_mark_is_still_checked(self):
        r = self.sweep_repo({"ok.md": "clean\n"})
        with open(os.path.join(r.root, "bom.md"), "wb") as stream:
            stream.write(b"\xef\xbb\xbf" + f"{WORD}\n".encode())
        git(r.root, "add", "-A")
        self.assertEqual(r.check()[0], 1)

    def test_a_file_that_is_neither_text_nor_clearly_binary_is_reported(self):
        r = self.sweep_repo({"ok.md": "clean\n"})
        with open(os.path.join(r.root, "latin.md"), "wb") as stream:
            stream.write(b"caf\xe9 " + WORD.encode())
        git(r.root, "add", "-A")
        code, out = r.check()
        self.assertEqual(code, 1)
        self.assertIn("latin.md: is not UTF-8 or UTF-16 text", out)

    def test_a_truncated_hash_is_refused_and_not_printed(self):
        with self.assertRaises(hygiene.ConfigError) as ctx:
            self.sweep_repo({"a.md": f"{WORD}\n"}, hash_text=WORD_HASH[:-1] + "\n").check()
        self.assertIn("sweep-hashes.txt:1", str(ctx.exception))
        self.assertNotIn(WORD_HASH[:10], str(ctx.exception))

    def test_a_non_hex_hash_is_refused(self):
        with self.assertRaises(hygiene.ConfigError):
            self.sweep_repo({"a.md": "x\n"}, hash_text="# note\n" + "z" * 64 + "\n").check()

    def test_uppercase_hex_and_trailing_comments_are_accepted(self):
        code, _ = self.sweep_repo({"a.md": "clean\n"}, hash_text=f"{WORD_HASH.upper()}  # a note\n").check()
        self.assertEqual(code, 0)


class ConfigTests(unittest.TestCase):
    def test_unknown_config_field_is_refused(self):
        r = Repo(self, {"a.md": "x\n"}, {"vendor_word": ["typo"]})
        with self.assertRaises(hygiene.ConfigError):
            r.check()

    def test_underscore_fields_are_comments(self):
        code, _ = Repo(self, {"a.md": "x\n"}, {"_about": "note", "vendor_words": []}).check()
        self.assertEqual(code, 0)

    def refused(self, config):
        r = Repo(self, {"a.md": "99 tests\n"}, config)
        with self.assertRaises(hygiene.ConfigError):
            r.check()

    def test_an_enabled_derivable_numbers_check_must_be_complete(self):
        self.refused({"no_derivable_numbers": {"paths": ["a.md"]}})
        self.refused({"no_derivable_numbers": {"patterns": ["\\d+ tests"]}})
        self.refused({"no_derivable_numbers": {"paths": ["a.md"], "patterns": []}})
        self.refused({"no_derivable_numbers": {"paths": [], "patterns": ["x"]}})
        self.refused({"no_derivable_numbers": {}})

    def test_derivable_numbers_wrong_types_and_bad_regex_are_refused(self):
        self.refused({"no_derivable_numbers": {"paths": "a.md", "patterns": ["x"]}})
        self.refused({"no_derivable_numbers": {"paths": ["a.md"], "patterns": [5]}})
        self.refused({"no_derivable_numbers": {"paths": ["a.md"], "patterns": ["("]}})

    def test_a_complete_derivable_numbers_check_still_works(self):
        r = Repo(self, {"a.md": "99 tests\n"}, {"no_derivable_numbers": {"paths": ["a.md"], "patterns": ["\\d+ tests"]}})
        self.assertEqual(r.check()[0], 1)

    def test_sweep_must_name_its_hash_file(self):
        self.refused({"sweep": {"exempt_files": []}})
        self.refused({"sweep": {}})
        self.refused({"sweep": {"hash_file": 5}})
        self.refused({"sweep": {"hash_file": "h.txt", "exempt_files": "a.md"}})

    def test_cli_exit_codes(self):
        r = Repo(self, {"a.md": "x\n"}, {})
        script = os.path.join(HERE, "hygiene.py")
        ok = subprocess.run([sys.executable, "-B", script, "check", "--root", r.root], capture_output=True)
        self.assertEqual(ok.returncode, 0)
        bad = subprocess.run([sys.executable, "-B", script, "check", "--root", r.root, "--config", os.path.join(r.root, "nope.json")],
                             capture_output=True)
        self.assertEqual(bad.returncode, 2)
        not_git = subprocess.run([sys.executable, "-B", script, "check", "--root", tempfile.gettempdir(), "--config",
                                  os.path.join(r.root, ".orchestration", "hygiene.json")], capture_output=True)
        self.assertEqual(not_git.returncode, 2)


if __name__ == "__main__":
    unittest.main()
