import json
import os
import unittest

from round_history import extract_rounds, flag_recurring, flag_explicit_reopen_language, jaccard, report, words

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


class WordsAndJaccardTests(unittest.TestCase):
    def test_short_and_stopword_tokens_are_dropped(self):
        self.assertEqual(words("the a of to it is"), set())

    def test_identical_text_scores_one(self):
        self.assertEqual(jaccard("missing order record", "missing order record"), 1.0)

    def test_disjoint_text_scores_zero(self):
        self.assertEqual(jaccard("missing order record", "completely unrelated sentence here"), 0.0)

    def test_empty_text_scores_zero_not_a_crash(self):
        self.assertEqual(jaccard("", "missing order record"), 0.0)
        self.assertEqual(jaccard("the a of", "missing order record"), 0.0)  # all-stopword text


class ExtractRoundsTests(unittest.TestCase):
    def test_non_verdict_comments_are_not_rounds(self):
        comments = [
            {"author": "a", "created": "t1", "body": "**Carlos:** go: plan for the thing."},
            {"author": "a", "created": "t2", "body": "**Claude · builder:** built and pushed. Head abc1234."},
        ]
        self.assertEqual(extract_rounds(comments), [])

    def test_verdict_comment_on_same_line_as_signature(self):
        comments = [{"author": "a", "created": "t1",
                     "body": "**Codex · PR review:** Not approved at 1234567890abcdef1234567890abcdef12345678 - round 1."}]
        rounds = extract_rounds(comments)
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["verdict"], "Not approved")
        self.assertEqual(rounds[0]["signer"], "Codex · PR review:")
        self.assertEqual(rounds[0]["sha"], "1234567890abcdef1234567890abcdef12345678")

    def test_verdict_comment_on_its_own_line(self):
        comments = [{"author": "a", "created": "t1",
                     "body": "**Codex · PR review:**\nApproved at abcdef1 - round 2."}]
        rounds = extract_rounds(comments)
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["verdict"], "Approved")

    def test_rounds_are_numbered_in_order_skipping_non_rounds(self):
        comments = [
            {"author": "a", "created": "t1", "body": "**Carlos:** go"},
            {"author": "a", "created": "t2", "body": "**Codex · PR review:** Not approved at 1111111 - r1."},
            {"author": "a", "created": "t3", "body": "**Claude · builder:** fixed, head 2222222."},
            {"author": "a", "created": "t4", "body": "**Codex · PR review:** Approved at 3333333 - r2."},
        ]
        rounds = extract_rounds(comments)
        self.assertEqual([r["index"] for r in rounds], [1, 2])
        self.assertEqual(rounds[0]["sha"], "1111111")
        self.assertEqual(rounds[1]["sha"], "3333333")


class RealFixtureTests(unittest.TestCase):
    """Real comment history from advance-po-reader#38 and #35 (CarlitosRed/advance-po-reader, now public),
    the two PRs docs/framework-map.md names as instance-chasing examples. Fetched 2026-10-16 via
    `python round_history.py fetch`. Counts below are what actually happened, not a synthetic scenario."""

    def test_pr38_five_rounds_approved_on_round_five(self):
        rounds = extract_rounds(load("pr38.json"))
        r = report(rounds)
        self.assertEqual(r["total_rounds"], 5)
        self.assertTrue(r["approved"])
        self.assertEqual(r["rounds_to_approval"], 5)

    def test_pr38_explicit_reopen_language_matches_the_recorded_history(self):
        # Round 2 says the bilingual class is "still open in the reverse direction"; round 3 explicitly
        # says the language-label class "remains open". Round 4 (the renamed-word finding) and round 5
        # (approval) do not use reopen language, even though round 4 is the same underlying class under a
        # different name - the exact gap F3's own report named as unmitigated (docs/f3-report.md).
        rounds = extract_rounds(load("pr38.json"))
        flagged = flag_explicit_reopen_language(rounds)
        self.assertEqual(flagged, [2, 3])

    def test_pr38_word_overlap_heuristic_does_not_catch_the_reworded_recurrence(self):
        # Documents, not asserts as a success: class-ledger's own 0.5 Jaccard threshold, applied to real
        # review prose rather than the short one-line generators it was built for, finds nothing here -
        # consistent with F3's own "Unsure" note that a reworded generator evades word-overlap matching.
        rounds = extract_rounds(load("pr38.json"))
        self.assertEqual(flag_recurring(rounds), [])

    def test_pr35_three_rounds_not_yet_approved(self):
        rounds = extract_rounds(load("pr35.json"))
        r = report(rounds)
        self.assertEqual(r["total_rounds"], 3)
        self.assertFalse(r["approved"])
        self.assertIsNone(r["rounds_to_approval"])

    def test_pr35_round_three_is_an_explicit_reopen(self):
        # Round 3's finding title is literally "B02 remains open (reopened): impossible producer states
        # still convert" - the clearest possible case, and the detector catches it.
        rounds = extract_rounds(load("pr35.json"))
        self.assertEqual(flag_explicit_reopen_language(rounds), [3])


if __name__ == "__main__":
    unittest.main()
