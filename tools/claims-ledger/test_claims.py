"""Tests for the claims ledger. Offline, throw-away temp folders only.

Run:  python -m unittest discover -s tools/claims-ledger -p "test_claims.py" -v
"""
import io
import os
import shutil
import subprocess
import tempfile
import unittest

import claims as C


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="claims-test-")
        self.path = os.path.join(self.dir, "claims.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def doc(self, name, text):
        full = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
        return full

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = C.main([argv[0], self.path, *argv[1:]], out=out, err=err)
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

    def init(self):
        self.ok("init")

    def add(self, slug, doc, line, claim, condition="x holds", pointer="app.py:1", exception="none", by="Build Engineer · Alpha"):
        return self.run_cli("add", "--slug", slug, "--doc", doc, "--line", str(line), "--claim", claim,
                             "--condition", condition, "--condition-pointer", pointer,
                             "--exception", exception, "--by", by)

    def added(self, *a, **k):
        code, out, err = self.add(*a, **k)
        self.assertEqual(code, 0, err)
        return out


class QuantifierDetectionTests(unittest.TestCase):
    def test_finds_each_listed_quantifier_word(self):
        for word in C.QUANTIFIER_WORDS:
            text = f"A retry {word} makes a new run happen here."
            found = list(C.quantifier_sentences(text))
            self.assertEqual(len(found), 1, (word, found))

    def test_plain_sentence_is_not_flagged(self):
        text = "The server starts on the configured port. It reads the config file first."
        self.assertEqual(list(C.quantifier_sentences(text)), [])

    def test_line_numbers_are_one_indexed_and_correct(self):
        text = "line one, nothing here.\nline two, this is always true.\nline three, nothing here either."
        found = list(C.quantifier_sentences(text))
        self.assertEqual(found, [(2, "line two, this is always true.")])

    def test_multiple_sentences_on_one_line_are_split(self):
        text = "First part is fine. Second part is never true. Third part is fine too."
        found = list(C.quantifier_sentences(text))
        self.assertEqual(len(found), 1)
        self.assertIn("never", found[0][1])


class InitAndAddTests(Base):
    def test_init_creates_empty_ledger(self):
        self.init()
        data = C.load(self.path)
        self.assertEqual(data["claims"], [])

    def test_init_twice_refused(self):
        self.init()
        self.refused("init")

    def test_add_then_duplicate_slug_refused(self):
        self.init()
        self.added("retry-new-run", "docs/x.md", 10, "A retry always makes a new run.")
        code, out, err = self.add("retry-new-run", "docs/x.md", 11, "Something else.")
        self.assertEqual(code, 1, out + err)
        self.assertIn("REFUSED", err)

    def test_add_needs_condition(self):
        self.init()
        code, out, err = self.add("a", "docs/x.md", 1, "It always works.", condition="  ")
        self.assertEqual(code, 1)
        self.assertIn("condition", err)

    def test_add_needs_exception(self):
        self.init()
        code, out, err = self.add("a", "docs/x.md", 1, "It always works.", exception=" ")
        self.assertEqual(code, 1)
        self.assertIn("exception", err)

    def test_states_parsed_from_comma_list(self):
        self.init()
        self.run_cli("add", "--slug", "s1", "--doc", "docs/x.md", "--line", "1", "--claim", "It is always true.",
                     "--condition", "c", "--condition-pointer", "a.py:1", "--exception", "none",
                     "--states", "a,b,c", "--by", "Build Engineer · Alpha")
        data = C.load(self.path)
        self.assertEqual(data["claims"][0]["states"], ["a", "b", "c"])


class ScanAndCheckTests(Base):
    def test_check_passes_when_every_quantifier_sentence_is_claimed(self):
        self.init()
        d = self.doc("docs/x.md", "A retry always makes a new run.\nNothing else interesting here.\n")
        self.added("s1", d, 1, "A retry always makes a new run.")
        self.ok("check", "--doc", d)

    def test_check_refuses_an_unclaimed_sentence(self):
        self.init()
        d = self.doc("docs/x.md", "A retry always makes a new run.\n")
        err = self.refused("check", "--doc", d)
        self.assertIn("always makes a new run", err)

    def test_scan_never_refuses_just_reports(self):
        self.init()
        d = self.doc("docs/x.md", "A retry always makes a new run.\n")
        out = self.ok("scan", "--doc", d)
        self.assertIn("1 unclaimed", out)

    def test_matching_is_by_text_not_line_number(self):
        self.init()
        d = self.doc("docs/x.md", "Intro paragraph.\n\nA retry always makes a new run.\n")
        self.added("s1", d, 99, "A retry always makes a new run.")  # wrong line on purpose
        self.ok("check", "--doc", d)

    def test_whitespace_differences_still_match(self):
        self.init()
        d = self.doc("docs/x.md", "A retry   always    makes  a  new  run.\n")
        # irregular internal spacing in the doc vs how it was claimed; normalize collapses both the same way
        self.added("s1", d, 1, "A retry always makes a new run.")
        out = self.ok("scan", "--doc", d)
        self.assertIn("every quantifier sentence has a claims-ledger row", out)

    def test_a_sentence_split_across_lines_is_a_known_miss(self):
        # documented limitation: quantifier_sentences does not join sentences across a line break
        self.init()
        d = self.doc("docs/x.md", "A retry always makes\na clean run.\n")
        self.added("s1", d, 1, "A retry always makes a clean run.")
        out = self.ok("scan", "--doc", d)
        self.assertIn("1 unclaimed", out, "if this starts passing, the line-splitting limitation was fixed; "
                      "update docs/claims-ledger-design.md and this test together")

    def test_editing_a_claimed_sentence_makes_it_unclaimed_again(self):
        self.init()
        d = self.doc("docs/x.md", "A retry always makes a new run.\n")
        self.added("s1", d, 1, "A retry always makes a new run.")
        self.ok("check", "--doc", d)
        with open(d, "w", encoding="utf-8") as f:
            f.write("A retry always makes a brand new run.\n")
        self.refused("check", "--doc", d)

    def test_unknown_doc_file_is_an_error_not_a_pass(self):
        self.init()
        code, out, err = self.run_cli("check", "--doc", os.path.join(self.dir, "missing.md"))
        self.assertEqual(code, 2)
        self.assertIn("no such doc file", err)


class GitScopedTests(Base):
    """--since REF: scope detection to lines changed since a git ref, not the whole file. Real git repos,
    throw-away temp folders - no mocking git itself."""

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, check=True)

    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")

    def commit(self, message="commit"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def test_changed_lines_empty_when_nothing_changed(self):
        d = self.doc("docs/x.md", "Plain line one.\nPlain line two.\n")
        self.commit()
        self.assertEqual(C.changed_lines(d, "HEAD"), set())

    def test_changed_lines_finds_an_added_line(self):
        d = self.doc("docs/x.md", "Plain line one.\n")
        self.commit()
        with open(d, "a", encoding="utf-8") as f:
            f.write("A new line that is always true.\n")
        self.assertEqual(C.changed_lines(d, "HEAD"), {2})

    def test_changed_lines_bad_ref_is_an_error(self):
        d = self.doc("docs/x.md", "Plain line one.\n")
        self.commit()
        with self.assertRaises(C.Broken):
            C.changed_lines(d, "not-a-real-ref")

    def test_check_since_ignores_a_preexisting_unclaimed_sentence(self):
        d = self.doc("docs/x.md", "This always was unclaimed and never fixed.\nPlain line.\n")
        self.commit()
        self.init()
        # no claim added - this sentence predates the ref, so --since must not flag it
        with open(d, "a", encoding="utf-8") as f:
            f.write("Plain unrelated line.\n")
        self.ok("check", "--doc", d, "--since", "HEAD")

    def test_check_since_still_catches_a_newly_added_unclaimed_sentence(self):
        d = self.doc("docs/x.md", "Plain line one.\n")
        self.commit()
        self.init()
        with open(d, "a", encoding="utf-8") as f:
            f.write("This is a new claim that is always true.\n")
        err = self.refused("check", "--doc", d, "--since", "HEAD")
        self.assertIn("always true", err)

    def test_check_without_since_still_scans_the_whole_file(self):
        d = self.doc("docs/x.md", "This always was unclaimed and never fixed.\n")
        self.commit()
        self.init()
        self.refused("check", "--doc", d)  # no --since: whole-file behavior unchanged


if __name__ == "__main__":
    unittest.main()
