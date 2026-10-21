import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import relay

SHA = "a" * 40


def write(tmp, name, data):
    path = Path(tmp) / name
    path.write_bytes(data)
    return str(path)


class BuildTests(unittest.TestCase):
    def build(self, text="- [P2] real finding", **kw):
        args = dict(role="Independent Reviewer", vendor="Codex", verdict="not-approved", sha=SHA, review_text=text,
                    relayer="the Orchestrator")
        args.update(kw)
        return relay.build(**args)

    def test_verdict_is_first_words_after_signature(self):
        body = self.build()
        self.assertTrue(body.startswith(f"**Independent Reviewer · Codex:** Not approved at {SHA}\n"))

    def test_approved_wording(self):
        self.assertIn(f"Approved at {SHA}", self.build(verdict="approved").split("\n")[0])

    def test_finding_text_is_quoted_unchanged(self):
        body = self.build("line one\n\nline two")
        self.assertIn("> line one\n>\n> line two", body)

    def test_empty_review_refused(self):
        for text in ("", "   \n\n  "):
            with self.assertRaises(relay.RelayError):
                self.build(text)

    def test_bad_sha_refused(self):
        for sha in ("abc", "A" * 40, "a" * 39, SHA + "0"):
            with self.assertRaises(relay.RelayError):
                self.build(sha=sha)

    def test_bad_verdict_refused(self):
        with self.assertRaises(relay.RelayError):
            self.build(verdict="lgtm")

    def test_note_goes_after_the_quote(self):
        body = self.build(note_text="Orchestrator's note: fixed.")
        self.assertTrue(body.rstrip().endswith("Orchestrator's note: fixed."))

    def test_no_bom_in_body(self):
        self.assertFalse(self.build().startswith("﻿"))


class ReadTextTests(unittest.TestCase):
    def test_encodings(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "finding — dash\nsecond"
            cases = {
                "u8": text.encode("utf-8"),
                "u8bom": b"\xef\xbb\xbf" + text.encode("utf-8"),
                "u16bom": b"\xff\xfe" + text.encode("utf-16-le"),
                "u16nobom": text.encode("utf-16-le"),
                "crlf": text.replace("\n", "\r\n").encode("utf-8"),
                "u16le_nonascii_first": ("• [P2] keep the text\nnext").encode("utf-16-le"),
                "u16be_nobom": text.encode("utf-16-be"),
            }
            text_for = {"u16le_nonascii_first": "• [P2] keep the text\nnext"}
            for name, data in cases.items():
                self.assertEqual(relay.read_text(write(tmp, name, data)), text_for.get(name, text), name)


class PostTests(unittest.TestCase):
    URL = "https://example.test/pull/7#issuecomment-2"

    def fake(self, drop_text=False, later_comment=False, print_url=True):
        seen = {}

        def gh(args, stdin=None):
            if args[:2] == ["pr", "comment"]:
                path = args[args.index("--body-file") + 1]
                seen["body"] = Path(path).read_text(encoding="utf-8")
                return self.URL + "\n" if print_url else ""
            body = "" if drop_text else seen["body"]
            comments = [{"url": "https://example.test/pull/7#issuecomment-1", "body": "older"},
                        {"url": self.URL, "body": body}]
            if later_comment:
                comments.append({"url": "https://example.test/pull/7#issuecomment-3", "body": "someone else"})
            return json.dumps({"comments": comments})

        return gh, seen

    def test_posted_and_matches(self):
        gh, seen = self.fake()
        body = relay.build("Independent Reviewer", "Codex", "approved", SHA, "ok", "me")
        self.assertEqual(relay.post(7, body, gh=gh), self.URL)
        self.assertEqual(seen["body"], body)

    def test_a_comment_posted_by_someone_else_in_between_is_ignored(self):
        gh, _ = self.fake(later_comment=True)
        body = relay.build("Independent Reviewer", "Codex", "approved", SHA, "ok", "me")
        self.assertEqual(relay.post(7, body, gh=gh), self.URL)

    def test_no_printed_url_is_refused(self):
        gh, _ = self.fake(print_url=False)
        body = relay.build("Independent Reviewer", "Codex", "approved", SHA, "ok", "me")
        with self.assertRaises(relay.RelayError):
            relay.post(7, body, gh=gh)

    def test_read_back_mismatch_is_caught(self):
        gh, _ = self.fake(drop_text=True)
        body = relay.build("Independent Reviewer", "Codex", "approved", SHA, "ok", "me")
        with self.assertRaises(relay.RelayError):
            relay.post(7, body, gh=gh)

    def test_nothing_is_posted_for_an_empty_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = write(tmp, "r.txt", b"  \n")
            with mock.patch.object(relay, "run_gh") as gh:
                code = relay.main(["post", "7", "--vendor", "Codex", "--verdict", "approved", "--sha", SHA,
                                   "--review-file", empty, "--relayer", "me"])
        self.assertEqual(code, 1)
        gh.assert_not_called()


class AsAccountTests(unittest.TestCase):
    URL = "https://example.test/pull/7#issuecomment-2"

    def runner(self, token="tok-codex", token_owner="carlitosred-codex", pr_author="carlitosred-claude",
               comment_author="carlitosred-codex"):
        calls = []
        seen = {}

        def run(args, stdin=None, env=None):
            calls.append((args, (env or {}).get("GH_TOKEN"), (env or {}).get("GH_CONFIG_DIR")))
            if args[:2] == ["auth", "token"]:
                return token + "\n"
            if args[:2] == ["api", "user"]:
                return token_owner + "\n"
            if args[:2] == ["pr", "view"] and "author" in args:
                return pr_author + "\n"
            if args[:2] == ["pr", "comment"]:
                seen["body"] = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
                return self.URL + "\n"
            return json.dumps({"comments": [{"url": self.URL, "body": seen["body"], "author": {"login": comment_author}}]})

        return run, calls

    def body(self):
        return relay.build("Independent Reviewer", "Codex", "approved", SHA, "ok", "me")

    def test_posts_with_the_vendor_token_and_reads_the_author_back(self):
        run, calls = self.runner()
        gh = relay.gh_as("carlitosred-codex", "C:/cfg", runner=run)
        self.assertEqual(relay.post(7, self.body(), gh=gh, expect_author="carlitosred-codex"), self.URL)
        self.assertEqual(calls[0][2], "C:/cfg")
        self.assertTrue(all(token == "tok-codex" for _, token, _ in calls[1:]))

    def test_a_token_that_belongs_to_another_account_is_refused(self):
        run, _ = self.runner(token_owner="carlitosred-claude")
        with self.assertRaises(relay.RelayError):
            relay.gh_as("carlitosred-codex", runner=run)

    def test_a_missing_token_is_refused(self):
        run, _ = self.runner(token="")
        with self.assertRaises(relay.RelayError):
            relay.gh_as("carlitosred-codex", runner=run)

    def test_a_comment_by_the_wrong_account_is_caught(self):
        run, _ = self.runner(comment_author="carlitosred-claude")
        gh = relay.gh_as("carlitosred-codex", runner=run)
        with self.assertRaises(relay.RelayError):
            relay.post(7, self.body(), gh=gh, expect_author="carlitosred-codex")

    def test_the_pull_request_author_cannot_review_its_own_pr(self):
        run, calls = self.runner(pr_author="carlitosred-codex")
        with tempfile.TemporaryDirectory() as tmp:
            review = write(tmp, "r.txt", b"ok\n")
            with mock.patch.object(relay, "run_gh", run):
                with mock.patch.object(relay, "gh_as", lambda a, c=None: lambda args, stdin=None: run(args, stdin)):
                    code = relay.main(["post", "7", "--vendor", "Codex", "--verdict", "approved", "--sha", SHA,
                                       "--review-file", review, "--relayer", "me", "--as-account", "carlitosred-codex"])
        self.assertEqual(code, 1)
        self.assertFalse(any(args[:2] == ["pr", "comment"] for args, _, _ in calls))


if __name__ == "__main__":
    unittest.main()
