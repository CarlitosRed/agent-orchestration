"""Tests for the generic gate. Offline: a pretend `gh` (FakeGH) and throw-away local git repositories.

Run:  python -m unittest discover -s tools/gate -p "test_gate.py" -v
"""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import unittest

import gate as g

HEAD = "a" * 40
OLD = "b" * 40
BASE = "d" * 40
SEP = "\u00b7"
BOM = "\ufeff"

# A small invented example project: two vendors (Alpha, Beta), four tiers, a legacy signer per vendor.
RAW = {
    "schema_version": 1,
    "repo": "example-org/recipe-box",
    "base": "main",
    "tiers": [
        {"label": "tier-1", "level": 1, "approvals": 0, "allowed_paths": ["docs/*", "README.md"]},
        {"label": "tier-2", "level": 2, "approvals": 1, "plan_go": True, "body_headings": True},
        {"label": "tier-3", "level": 3, "approvals": 1, "plan_go": True, "body_headings": True,
         "owner_approval": True},
        {"label": "tier-4", "level": 4, "mergeable": False},
    ],
    "vendors": {
        "alpha": {"names": ["Alpha"], "branch_prefixes": ["alpha/"]},
        "beta": {"names": ["Beta"], "branch_prefixes": ["beta/", "bx/"]},
    },
    "legacy_signers": {"Atlas": "alpha", "Bolt": "beta", "Bee": "beta"},
    "owner_signers": ["Program Owner", "Pat"],
    "protected_paths": ["AGENTS.md", "ROLES.md", ".github/*", ".githooks/*", "tools/gate/*", "app/payments.py",
                        "reader.py", "scripts/*", "migrations/*", "*/migrations/*"],
    "protected_tier": 3,
    "required_checks": ["tests", "gate-tests", "scan"],
    "body_headings": ["Plan", "Evidence", "Cost"],
    "forbidden_globs": ["*.pdf", "*.png", "*.jpg", "*.gguf", "*.sqlite3", "*.pem", "*.key", ".env", ".env.*",
                        "data/*", "output/*", "tmp/*", ".venv/*"],
    "forbidden_head_prefixes": ["integration/"],
}


def cfg(**over):
    raw = json.loads(json.dumps(RAW))
    raw.update(over)
    return g.build_config(raw)


CFG = cfg()

REVIEW = f"Independent Reviewer {SEP} Alpha"       # alpha, new format
LEGACY_REVIEW = f"Atlas {SEP} PR review"            # alpha, legacy format
SAME_REVIEW = f"Independent Reviewer {SEP} Beta"    # beta: same vendor as the author
SAME_REVIEW_2 = f"Verification Engineer {SEP} Beta"  # beta: a second, distinct same-vendor identity
AUTHOR = f"Build Engineer {SEP} Beta"               # beta (branch beta/...)
MERGER = f"Release Manager {SEP} Beta"
OWNER = "Program Owner"
BODY = "## Plan\nwhat changes\n## Evidence\n10 passed\n## Cost\n$0\n"


def comment(name, text, when, minimized=False):
    body = f"**{name}:** {text}" if name else text
    return {"author": {"login": "shared"}, "body": body, "createdAt": when, "isMinimized": minimized}


def go(name=REVIEW, when="2026-10-04T09:00:00Z"):
    return comment(name, "go", when)


def approve(name=REVIEW, sha=HEAD, when="2026-10-04T10:00:00Z"):
    return comment(name, f"Approved at `{sha}`. Tests pass.", when)


def pr(**over):
    base = {
        "number": 7, "title": "Add tags", "state": "OPEN", "isDraft": False,
        "baseRefName": "main", "headRefName": "beta/add-tags", "headRefOid": HEAD, "baseRefOid": BASE,
        "author": {"login": "shared"},
        "labels": [{"name": "tier-2"}], "body": BODY,
        "files": [{"path": "app/tags.py"}],
        "statusCheckRollup": [
            {"__typename": "CheckRun", "name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "gate-tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "scan", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
        "comments": [go(), approve()],
        "reviews": [],
    }
    base.update(over)
    if "changedFiles" not in over:
        base["changedFiles"] = len(base["files"])
    return base


def rules(ev):
    return {r["rule"]: r["ok"] for r in ev["results"]}


def msg(ev, rule):
    return [r["msg"] for r in ev["results"] if r["rule"] == rule][0]


def files_pages(files, per_page=100):
    entries = []
    for f in files:
        e = {"filename": f["path"], "status": "renamed" if f.get("previous") else "added"}
        if f.get("previous"):
            e["previous_filename"] = f["previous"]
        entries.append(e)
    return "".join(json.dumps(entries[i:i + per_page]) for i in range(0, len(entries), per_page))


def n_files(count, special=None):
    special = special or {}
    return [{"path": special.get(i, f"app/f{i}.py")} for i in range(count)]


DROP = object()


class FakeGH:
    """api_out replaces what the file-list call prints; `after` overrides fields in the second look at the PR.
    A value of DROP removes the field."""
    def __init__(self, pull, api_out=None, after=None):
        self.pull, self.calls, self.api_out, self.after = pull, [], api_out, after
        self.views = 0

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "view"]:
            self.views += 1
            if self.views > 1 and self.after:
                again = dict(self.pull, **{k: v for k, v in self.after.items() if v is not DROP})
                for k, v in self.after.items():
                    if v is DROP:
                        again.pop(k, None)
                return json.dumps(again)
            return json.dumps(self.pull)
        if args[:2] == ["repo", "view"]:
            return "example-org/recipe-box\n"
        if args[0] == "api":
            if self.api_out is not None:
                return self.api_out
            return files_pages(self.pull.get("files") or [])
        return ""

    def merged(self):
        return [c for c in self.calls if c[:2] == ["pr", "merge"]]


def safe(gh, c=None):
    """True only when the whole path (fetch, then evaluate) lets the file list through."""
    c = c or cfg()
    try:
        got = g.fetch_pr(gh, c, 7)
    except g.GateError:
        return False
    return rules(g.evaluate(got, c))["files"]


def arr(*names):
    return json.dumps([{"filename": n, "status": "added"} for n in names])


def try_merge(gh, merged_as=AUTHOR, c=None, **kw):
    out = []
    try:
        code = g.cmd_merge(gh, c or cfg(), 7, merged_as, out=out.append, **kw)
    except g.GateError:
        code = 2
    return code, "\n".join(out)


# ================================================================ config schema

def by(login, c):
    """The same comment, posted from a given GitHub account."""
    c = dict(c)
    c["author"] = {"login": login}
    return c


class AccountTests(unittest.TestCase):
    """Optional GitHub logins per vendor and for the owner, and distinct_accounts. With none configured the gate
    trusts signature text on a shared account exactly as before (every test above)."""

    OWNER_LOGIN = "pat-human"

    def c(self, **over):
        vendors = json.loads(json.dumps(RAW["vendors"]))
        vendors["alpha"]["logins"] = ["alpha-bot"]
        vendors["beta"]["logins"] = ["Beta-Bot"]
        base = dict(vendors=vendors, owner_logins=[self.OWNER_LOGIN], distinct_accounts=True)
        base.update(over)
        return cfg(**base)

    def p(self, **over):
        base = dict(author={"login": "beta-bot"}, comments=[by("alpha-bot", go()), by("alpha-bot", approve())])
        base.update(over)
        return pr(**base)

    def test_a_reviewer_on_its_own_account_passes(self):
        ev = g.evaluate(self.p(), self.c())
        self.assertTrue(ev["passed"], g.format_report(ev, 7))

    def test_login_comparison_ignores_case(self):
        ev = g.evaluate(self.p(comments=[by("ALPHA-BOT", go()), by("Alpha-Bot", approve())]), self.c())
        self.assertTrue(ev["passed"], g.format_report(ev, 7))

    def test_a_vendor_signature_from_the_wrong_login_counts_for_nothing(self):
        ev = g.evaluate(self.p(comments=[by("beta-bot", go()), by("beta-bot", approve())]), self.c())
        r = rules(ev)
        self.assertFalse(r["review"])
        self.assertFalse(r["plan"])
        self.assertFalse(r["signals"])
        self.assertIn("not one of vendor alpha's configured logins", msg(ev, "signals"))

    def test_the_owner_line_from_an_agent_account_counts_for_nothing(self):
        owner = comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")
        p = self.p(labels=[{"name": "tier-3"}],
                   comments=[by("alpha-bot", go()), by("alpha-bot", approve()), by("alpha-bot", owner)])
        ev = g.evaluate(p, self.c())
        self.assertFalse(rules(ev)["owner"])
        self.assertFalse(rules(ev)["signals"])
        self.assertIn("not one of the owner's configured logins", msg(ev, "signals"))

    def test_the_owner_line_from_the_owner_login_counts(self):
        owner = comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")
        p = self.p(labels=[{"name": "tier-3"}],
                   comments=[by("alpha-bot", go()), by("alpha-bot", approve()), by(self.OWNER_LOGIN, owner)])
        ev = g.evaluate(p, self.c())
        self.assertTrue(ev["passed"], g.format_report(ev, 7))

    def test_unhold_only_counts_from_the_owner_login(self):
        hold = by("alpha-bot", comment(REVIEW, "hold", "2026-10-04T11:00:00Z"))
        unhold = comment(OWNER, "unhold", "2026-10-04T12:00:00Z")
        base = [by("alpha-bot", go()), by("alpha-bot", approve()), hold]
        self.assertFalse(rules(g.evaluate(self.p(comments=base + [by("alpha-bot", unhold)]), self.c()))["hold"])
        self.assertTrue(rules(g.evaluate(self.p(comments=base + [by(self.OWNER_LOGIN, unhold)]), self.c()))["hold"])

    def test_distinct_accounts_refuses_a_review_from_the_authors_own_account(self):
        c = cfg(distinct_accounts=True)
        same = g.evaluate(pr(author={"login": "me"}, comments=[by("me", go()), by("me", approve())]), c)
        self.assertFalse(rules(same)["review"])
        self.assertIn("PR author's account", msg(same, "review"))
        other = g.evaluate(pr(author={"login": "me"}, comments=[by("you", go()), by("you", approve())]), c)
        self.assertTrue(other["passed"], g.format_report(other, 7))

    def test_distinct_accounts_refuses_a_plan_go_from_the_authors_own_account(self):
        c = cfg(distinct_accounts=True)
        ev = g.evaluate(pr(author={"login": "me"}, comments=[by("me", go()), by("you", approve())]), c)
        self.assertFalse(rules(ev)["plan"])

    def test_an_unknown_account_does_not_count_when_accounts_must_be_distinct(self):
        c = cfg(distinct_accounts=True)
        no_login = go()
        no_login.pop("author")
        ev = g.evaluate(pr(author={"login": "me"}, comments=[no_login, approve(), by("you", approve())]), c)
        self.assertFalse(rules(ev)["plan"])

    def test_a_shared_account_still_works_when_nothing_is_configured(self):
        ev = g.evaluate(pr(author={"login": "me"}, comments=[by("me", go()), by("me", approve())]), CFG)
        self.assertTrue(ev["passed"], g.format_report(ev, 7))

    def test_config_refuses_bad_logins(self):
        def bad(**over):
            with self.assertRaises(g.ConfigError):
                self.c(**over)
        vendors = json.loads(json.dumps(RAW["vendors"]))
        vendors["alpha"]["logins"] = "alpha-bot"
        bad(vendors=vendors)
        vendors["alpha"]["logins"] = ["has space"]
        bad(vendors=vendors)
        vendors["alpha"]["logins"] = ["same-login"]
        vendors["beta"]["logins"] = ["Same-Login"]
        bad(vendors=vendors)
        vendors["beta"]["logins"] = ["beta-bot"]
        bad(vendors=vendors, owner_logins=["same-login"])
        bad(owner_logins="pat-human")
        bad(distinct_accounts="yes")


class ConfigSchemaTests(unittest.TestCase):
    def write(self, text, encoding="utf-8"):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "gate.json")
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_the_example_config_loads(self):
        c = g.load_config(self.write(json.dumps(RAW)))
        self.assertEqual([t.label for t in c.tiers], ["tier-1", "tier-2", "tier-3", "tier-4"])
        self.assertEqual(c.sha_min, 40)
        self.assertEqual(c.base, "main")

    def test_a_config_file_with_a_byte_order_mark_still_loads(self):
        self.assertEqual(g.load_config(self.write(json.dumps(RAW), encoding="utf-8-sig")).base, "main")

    def test_missing_file_is_an_error_not_hidden_defaults(self):
        with self.assertRaises(g.ConfigError):
            g.load_config(os.path.join(tempfile.gettempdir(), "no-such-dir-xyz", "gate.json"))

    def test_invalid_json_is_an_error(self):
        with self.assertRaises(g.ConfigError):
            g.load_config(self.write("{not json"))

    def test_each_required_field_is_required(self):
        for field in g.REQUIRED:
            raw = dict(RAW)
            del raw[field]
            with self.assertRaises(g.ConfigError, msg=field):
                g.build_config(raw)

    def test_unknown_field_is_refused_but_underscore_comments_are_fine(self):
        with self.assertRaises(g.ConfigError):
            g.build_config(dict(RAW, protected_path=["x"]))   # a typo must not silently drop protection
        self.assertEqual(g.build_config(dict(RAW, _about="notes")).base, "main")

    def test_defaults_fill_only_non_policy_knobs(self):
        raw = {k: RAW[k] for k in g.REQUIRED}
        raw["body_headings"] = RAW["body_headings"]    # the example tiers ask for headings
        c = g.build_config(raw)
        self.assertEqual(c.base, "main")
        self.assertEqual(c.max_file_mb, 5)
        self.assertIn(".env", c.forbidden_globs)
        self.assertEqual([k for _, k in c.magic][:2], ["PDF", "PNG image"])
        self.assertEqual(c.legacy, {})
        self.assertIsNone(c.approver_roles)

    def test_bad_tier_definitions_are_refused(self):
        bad = [
            [],
            [{"label": "t1"}],
            [{"level": 1}],
            [{"label": "t1", "level": "1"}],
            [{"label": "t1", "level": True}],
            [{"label": "t1", "level": 1, "approvals": -1}],
            [{"label": "t1", "level": 1, "approvals": 1.0}],
            [{"label": "t1", "level": 1, "plan_go": "yes"}],
            [{"label": "t1", "level": 1, "colour": "red"}],
            [{"label": "t1", "level": 1, "record": "one two"}],
            [{"label": "t1", "level": 1}, {"label": "t1", "level": 2}],
            [{"label": "t1", "level": 1}, {"label": "t2", "level": 1}],
            [{"label": "t1", "level": 1, "record": "x"}, {"label": "t2", "level": 2, "record": "x"}],
            [{"label": "t1", "level": 1, "allowed_paths": "docs/*"}],
        ]
        for tiers in bad:
            with self.assertRaises(g.ConfigError, msg=repr(tiers)):
                g.build_config(dict(RAW, tiers=tiers, protected_tier=1))

    def test_protected_tier_must_exist(self):
        for bad in (9, "3", None, True):
            with self.assertRaises(g.ConfigError, msg=repr(bad)):
                g.build_config(dict(RAW, protected_tier=bad))

    def test_bad_vendor_definitions_are_refused(self):
        bad = [
            {},
            {"alpha": {"branch_prefixes": ["alpha/"]}},
            {"alpha": {"names": [], "branch_prefixes": ["alpha/"]}},
            {"alpha": {"names": ["A" + SEP + "B"], "branch_prefixes": []}},
            {"alpha": {"names": ["Alpha"]}, "beta": {"names": ["alpha"]}},
            {"alpha": {"names": ["Alpha"], "branch_prefixes": ["x/"]}, "beta": {"names": ["Beta"], "branch_prefixes": ["x/y"]}},
            {"alpha": {"names": ["Alpha"], "branch_prefixes": [""]}},
            {"alpha": {"names": ["Alpha"], "extra": 1}},
        ]
        for vendors in bad:
            with self.assertRaises(g.ConfigError, msg=repr(vendors)):
                g.build_config(dict(RAW, vendors=vendors, legacy_signers={}))

    def test_signer_groups_must_be_disjoint_so_detection_is_unambiguous(self):
        for over in ({"legacy_signers": {"Build Engineer": "beta"}},
                     {"owner_signers": ["Independent Reviewer"]},
                     {"owner_signers": ["atlas"]},
                     {"roles": ["Reviewer", "Pat"]}):
            with self.assertRaises(g.ConfigError, msg=repr(over)):
                g.build_config(dict(RAW, **over))

    def test_legacy_signer_must_point_at_a_known_vendor(self):
        with self.assertRaises(g.ConfigError):
            g.build_config(dict(RAW, legacy_signers={"Atlas": "gamma"}))

    def test_role_lists_must_name_known_roles(self):
        with self.assertRaises(g.ConfigError):
            g.build_config(dict(RAW, approver_roles=["Chief Approver"]))
        self.assertEqual(g.build_config(dict(RAW, approver_roles=["Independent Reviewer"])).approver_roles,
                         {"independent reviewer"})

    def test_signature_pattern_must_compile_and_carry_its_groups(self):
        for bad in ("(", r"^\*\*(?P<name>.+)\*\*", r"\*\*(?P<name>.+)\*\*(?P<rest>.*)", 5):
            with self.assertRaises(g.ConfigError, msg=repr(bad)):
                g.build_config(dict(RAW, signature_pattern=bad))

    def test_sha_length_bounds(self):
        for bad in (6, 41, "40", True, 7.0):
            with self.assertRaises(g.ConfigError, msg=repr(bad)):
                g.build_config(dict(RAW, verdict_sha_min_length=bad))
        self.assertEqual(g.build_config(dict(RAW, verdict_sha_min_length=7)).sha_min, 7)

    def test_magic_and_secret_entries_are_validated(self):
        for magic in ([{"hex": "zz", "kind": "x"}], [{"hex": "", "kind": "x"}], [{"bytes": "00", "kind": "x"}], "PDF"):
            with self.assertRaises(g.ConfigError, msg=repr(magic)):
                g.build_config(dict(RAW, magic=magic))
        for secrets in ([{"pattern": "(", "label": "x"}], [{"pattern": "a"}]):
            with self.assertRaises(g.ConfigError, msg=repr(secrets)):
                g.build_config(dict(RAW, secrets=secrets))

    def test_body_headings_needed_when_a_tier_asks_for_them(self):
        with self.assertRaises(g.ConfigError):
            g.build_config(dict(RAW, body_headings=[]))

    def test_base_must_be_a_valid_branch(self):
        for bad in ("", "a b", "x..y", 5):
            with self.assertRaises(g.ConfigError, msg=repr(bad)):
                g.build_config(dict(RAW, base=bad))

    def test_schema_version_must_be_1(self):
        for bad in (2, "1", True):
            with self.assertRaises(g.ConfigError, msg=repr(bad)):
                g.build_config(dict(RAW, schema_version=bad))

    def test_default_config_path_is_in_the_orchestration_folder_of_the_repo(self):
        path = g.default_config_path(lambda args: "C:/work/repo\n")
        self.assertEqual(os.path.normpath(path), os.path.normpath("C:/work/repo/.orchestration/gate.json"))

        def no_git(args):
            raise g.GateError("not a git repository")
        self.assertTrue(g.default_config_path(no_git).endswith(os.path.join(".orchestration", "gate.json")))

    def test_main_reports_a_missing_config_with_exit_code_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = g.main(["--config", os.path.join(tempfile.gettempdir(), "nope-xyz", "g.json"), "paths"])
        self.assertEqual(code, 2)
        self.assertIn("no gate config", err.getvalue())


# ================================================================ signatures: legacy and new

class SignatureFormatTests(unittest.TestCase):
    def test_signature_forms(self):
        self.assertEqual(g.split_signature(CFG, f"**{REVIEW}:** Approved at `{HEAD}`"), (REVIEW, f"Approved at `{HEAD}`"))
        self.assertEqual(g.split_signature(CFG, f"**{OWNER}:** hold")[0], OWNER)
        self.assertEqual(g.split_signature(CFG, f"**{OWNER}**: hold")[0], OWNER)
        self.assertEqual(g.split_signature(CFG, "plain text"), (None, "plain text"))

    def test_new_format_is_role_then_vendor(self):
        s = g.identify(CFG, REVIEW)
        self.assertEqual((s.kind, s.vendor, s.role), ("role", "alpha", "Independent Reviewer"))
        s = g.identify(CFG, f"build engineer {SEP} BETA")
        self.assertEqual((s.kind, s.vendor), ("role", "beta"))

    def test_legacy_format_is_name_then_job(self):
        s = g.identify(CFG, LEGACY_REVIEW)
        self.assertEqual((s.kind, s.vendor, s.role), ("legacy", "alpha", None))
        self.assertEqual(g.identify(CFG, f"Bee {SEP} design").vendor, "beta")
        self.assertEqual(g.identify(CFG, "Bolt").vendor, "beta")      # legacy name alone, as the old gate read it

    def test_owner_is_the_whole_signature(self):
        self.assertEqual(g.identify(CFG, OWNER).kind, "owner")
        self.assertEqual(g.identify(CFG, "pat").kind, "owner")
        self.assertIsNone(g.identify(CFG, f"Pat {SEP} desk").kind)
        self.assertIsNone(g.identify(CFG, f"Program Owner {SEP} Alpha").kind)

    def test_new_format_needs_exactly_a_known_vendor_after_the_dot(self):
        for name in (f"Independent Reviewer {SEP} Gamma", "Independent Reviewer", f"Independent Reviewer {SEP} Alpha {SEP} x",
                     f"Independent Reviewer {SEP} ", f"Alpha {SEP} Independent Reviewer"):
            self.assertIsNone(g.identify(CFG, name).kind, name)

    def test_unknown_first_word_is_unknown(self):
        self.assertIsNone(g.identify(CFG, f"Gemini {SEP} x").kind)
        self.assertIsNone(g.identify(CFG, f"Alpha {SEP} PR review").kind)   # a vendor name is not a legacy name

    def test_both_formats_are_approvals_in_the_same_project(self):
        for reviewer in (REVIEW, LEGACY_REVIEW):
            ev = g.evaluate(pr(comments=[go(reviewer), approve(reviewer)]), CFG)
            self.assertTrue(ev["passed"], g.format_report(ev, 7))


# ================================================================ verdict must be the first words

class VerdictFirstTests(unittest.TestCase):
    """The leak class of approvals that silently did not count: verdict buried, text before it, a byte-order
    mark, a short id. Each must (a) not count and (b) make the `signals` rule FAIL with a reason."""

    def ev(self, text, name=REVIEW, c=None):
        return g.evaluate(pr(comments=[go(), comment(name, text, "2026-10-04T10:00:00Z")]), c or CFG)

    def assert_refused(self, ev, why=None):
        r = rules(ev)
        self.assertFalse(r["review"], g.format_report(ev, 7))
        self.assertFalse(r["signals"], g.format_report(ev, 7))
        self.assertFalse(ev["passed"])
        if why:
            self.assertIn(why, msg(ev, "signals"))

    def test_verdict_first_counts_and_signals_pass(self):
        ev = self.ev(f"Approved at `{HEAD}`. Tests pass.")
        self.assertTrue(ev["passed"], g.format_report(ev, 7))
        self.assertTrue(rules(ev)["signals"])

    def test_verdict_buried_in_a_later_sentence(self):
        self.assert_refused(self.ev(f"Looked at everything. Approved at `{HEAD}`."), "not the first words")

    def test_verdict_buried_in_a_later_paragraph(self):
        self.assert_refused(self.ev(f"Round 2 notes.\n\nApproved at {HEAD}"), "not the first words")

    def test_extra_text_before_the_verdict(self):
        for text in (f"Verdict: Approved at {HEAD}", f"OK. Approved at {HEAD}", f"- Approved at {HEAD}",
                     f"> Approved at {HEAD}", f"**Approved at {HEAD}**"):
            self.assert_refused(self.ev(text))

    def test_buried_not_approved_is_never_silently_ignored(self):
        p = pr(comments=[go(), approve(), comment(f"Atlas {SEP} audit", f"I re-ran it. Not approved at {HEAD}.",
                                                  "2026-10-04T11:00:00Z")])
        ev = g.evaluate(p, CFG)
        self.assertFalse(rules(ev)["signals"])
        self.assertFalse(ev["passed"])

    def test_byte_order_mark_before_the_signature(self):
        p = pr(comments=[go(), {"body": BOM + f"**{REVIEW}:** Approved at `{HEAD}`", "createdAt": "2026-10-04T10:00:00Z"}])
        ev = g.evaluate(p, CFG)
        self.assert_refused(ev, "invisible character")

    def test_zero_width_space_before_the_signature(self):
        p = pr(comments=[go(), {"body": "\u200b" + f"**{REVIEW}:** Approved at `{HEAD}`", "createdAt": "2026-10-04T10:00:00Z"}])
        self.assert_refused(g.evaluate(p, CFG), "invisible character")

    def test_byte_order_mark_go_does_not_count_and_is_reported(self):
        p = pr(comments=[{"body": BOM + f"**{REVIEW}:** go", "createdAt": "2026-10-04T09:00:00Z"}, approve()])
        r = rules(g.evaluate(p, CFG))
        self.assertFalse(r["plan"])
        self.assertFalse(r["signals"])

    def test_ordinary_leading_whitespace_is_fine(self):
        p = pr(comments=[go(), {"body": "\n  " + f"**{REVIEW}:** Approved at `{HEAD}`", "createdAt": "2026-10-04T10:00:00Z"}])
        self.assertTrue(g.evaluate(p, CFG)["passed"])

    def test_case_variants_of_the_verdict_words_count(self):
        for text in (f"approved at {HEAD}", f"APPROVED AT {HEAD}", f"Approved At `{HEAD}`", f"Approved at {HEAD.upper()}"):
            ev = self.ev(text)
            self.assertTrue(ev["passed"], (text, g.format_report(ev, 7)))

    def test_case_variants_of_not_approved_block(self):
        for text in (f"NOT APPROVED AT {HEAD}", f"not approved at `{HEAD}`"):
            p = pr(comments=[go(), approve(), comment(f"Atlas {SEP} audit", text, "2026-10-04T11:00:00Z")])
            self.assertFalse(rules(g.evaluate(p, CFG))["review"], text)

    def test_odd_spacing_inside_the_verdict_does_not_count_and_is_reported(self):
        self.assert_refused(self.ev(f"Approved  at {HEAD}"))
        self.assert_refused(self.ev(f"Approved\nat {HEAD}"))

    def test_short_commit_id_does_not_count_by_default_and_is_reported(self):
        self.assert_refused(self.ev(f"Approved at `{HEAD[:7]}`"), "7 characters")

    def test_short_commit_id_counts_when_the_project_allows_it(self):
        c = cfg(verdict_sha_min_length=7)
        ev = self.ev(f"Approved at `{HEAD[:7]}`", c=c)
        self.assertTrue(ev["passed"], g.format_report(ev, 7))
        self.assert_refused(self.ev(f"Approved at `{HEAD[:6]}`", c=c))

    def test_an_id_longer_than_40_is_not_a_prefix_match(self):
        ev = self.ev(f"Approved at {HEAD}a")
        self.assertFalse(rules(ev)["review"])

    def test_unsigned_comment_with_a_head_verdict_is_reported(self):
        p = pr(comments=[go(), approve(), comment(None, f"Reviewer says Approved at {HEAD}", "2026-10-04T11:00:00Z")])
        ev = g.evaluate(p, CFG)
        self.assertFalse(rules(ev)["signals"])
        self.assertIn("no signature", msg(ev, "signals"))

    def test_buried_verdict_for_an_older_commit_is_harmless(self):
        p = pr(comments=[go(), approve(when="2026-10-04T11:00:00Z"),
                         comment(REVIEW, f"Round 1 notes; earlier I said Approved at {OLD}", "2026-10-04T10:00:00Z")])
        self.assertTrue(g.evaluate(p, CFG)["passed"])

    def test_hiding_the_faulty_comment_clears_the_signal_rule(self):
        p = pr(comments=[go(), approve(),
                         comment(REVIEW, f"notes. Approved at {HEAD}", "2026-10-04T11:00:00Z", minimized=True)])
        self.assertTrue(g.evaluate(p, CFG)["passed"])

    def test_buried_verdict_inside_a_review_body_is_reported(self):
        p = pr(comments=[go(), approve()], reviews=[{"body": f"**{REVIEW}:** see notes. Approved at {HEAD}",
                                                    "submittedAt": "2026-10-04T10:30:00Z"}])
        self.assertFalse(rules(g.evaluate(p, CFG))["signals"])

    def test_merge_refuses_while_a_signal_is_faulty(self):
        p = pr(comments=[go(), approve(), comment(REVIEW, f"also: Approved at {HEAD}", "2026-10-04T11:00:00Z")])
        gh = FakeGH(p)
        self.assertEqual(try_merge(gh)[0], 1)
        self.assertEqual(gh.merged(), [])


# ================================================================ review rules

class ReviewTests(unittest.TestCase):
    def test_clean_tier2_passes(self):
        ev = g.evaluate(pr(), CFG)
        self.assertTrue(ev["passed"], g.format_report(ev, 7))
        self.assertEqual(ev["tier"].level, 2)
        self.assertEqual(ev["approvers"], [REVIEW])
        self.assertEqual(ev["author_vendor"], "beta")

    def test_approval_of_an_older_commit_is_ignored(self):
        ev = g.evaluate(pr(comments=[go(), approve(sha=OLD)]), CFG)
        self.assertFalse(rules(ev)["review"])
        self.assertIn("older commit", msg(ev, "review"))

    def test_reapproval_at_the_new_head_passes(self):
        p = pr(comments=[go(), approve(sha=OLD, when="2026-10-04T09:30:00Z"), approve(when="2026-10-04T11:00:00Z")])
        self.assertTrue(rules(g.evaluate(p, CFG))["review"])

    def test_same_vendor_reviewer_is_refused(self):
        r = rules(g.evaluate(pr(comments=[go(SAME_REVIEW), approve(SAME_REVIEW)]), CFG))
        self.assertFalse(r["review"])
        self.assertFalse(r["plan"])

    def test_second_prefix_of_a_vendor_counts_as_that_vendor(self):
        self.assertFalse(rules(g.evaluate(pr(headRefName="bx/mock", comments=[go(SAME_REVIEW), approve(SAME_REVIEW)]), CFG))["review"])
        self.assertTrue(g.evaluate(pr(headRefName="bx/mock"), CFG)["passed"])

    def test_alpha_branch_needs_a_beta_reviewer(self):
        self.assertFalse(rules(g.evaluate(pr(headRefName="alpha/t-1"), CFG))["review"])
        p = pr(headRefName="alpha/t-1", comments=[go(SAME_REVIEW), approve(SAME_REVIEW)])
        self.assertTrue(rules(g.evaluate(p, CFG))["review"])

    def test_unknown_branch_prefix_is_refused(self):
        ev = g.evaluate(pr(headRefName="feature/x"), CFG)
        self.assertFalse(rules(ev)["author"])
        self.assertFalse(ev["passed"])

    def test_branch_prefix_is_case_exact(self):
        self.assertFalse(rules(g.evaluate(pr(headRefName="Beta/x"), CFG))["author"])

    def test_forbidden_head_prefix_is_refused(self):
        ev = g.evaluate(pr(headRefName="integration/batch"), CFG)
        self.assertFalse(rules(ev)["branch"])

    def test_unknown_signer_and_unsigned_approval_are_ignored(self):
        self.assertFalse(rules(g.evaluate(pr(comments=[go(), approve(f"Gemini {SEP} review")]), CFG))["review"])
        self.assertFalse(rules(g.evaluate(pr(comments=[go(), approve(f"Independent Reviewer {SEP} Gamma")]), CFG))["review"])
        p = pr(comments=[go(), comment(None, f"Approved at `{HEAD}`", "2026-10-04T10:00:00Z")])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_not_approved_cancels_an_earlier_approval_by_the_same_signer(self):
        p = pr(comments=[go(), approve(), comment(REVIEW, f"Not approved at `{HEAD}`. Found a problem.", "2026-10-04T10:30:00Z")])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_same_signer_in_another_case_is_the_same_signer(self):
        p = pr(comments=[go(), approve(), comment(REVIEW.upper(), f"Not approved at {HEAD}", "2026-10-04T10:30:00Z")])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_not_approved_by_another_signer_blocks(self):
        p = pr(comments=[go(), approve(), comment(f"Atlas {SEP} IT", f"Not approved at `{HEAD}`", "2026-10-04T10:05:00Z")])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_not_approved_at_an_older_commit_does_not_block_others(self):
        p = pr(comments=[go(), approve(), comment(f"Atlas {SEP} IT", f"Not approved at `{OLD}`", "2026-10-04T08:00:00Z")])
        self.assertTrue(rules(g.evaluate(p, CFG))["review"])

    def test_approval_text_inside_a_review_body_counts(self):
        p = pr(comments=[go()], reviews=[{"body": f"**{REVIEW}:** Approved at `{HEAD}`",
                                          "submittedAt": "2026-10-04T10:00:00Z", "state": "COMMENTED"}])
        self.assertTrue(rules(g.evaluate(p, CFG))["review"])

    def test_hidden_comment_is_ignored(self):
        p = pr(comments=[go(), comment(REVIEW, f"Approved at `{HEAD}`", "2026-10-04T10:00:00Z", minimized=True)])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_approver_roles_restrict_new_format_approvals(self):
        c = cfg(approver_roles=["Independent Reviewer"])
        self.assertTrue(rules(g.evaluate(pr(), c))["review"])
        other = f"Research Analyst {SEP} Alpha"
        self.assertFalse(rules(g.evaluate(pr(comments=[go(), approve(other)]), c))["review"])
        # legacy names carry no role, so they are not restricted (documented compatibility)
        self.assertTrue(rules(g.evaluate(pr(comments=[go(), approve(LEGACY_REVIEW)]), c))["review"])

    def test_two_approvals_required(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["approvals"] = 2
        c = cfg(tiers=tiers)
        self.assertFalse(rules(g.evaluate(pr(), c))["review"])
        p = pr(comments=[go(), approve(), approve(LEGACY_REVIEW, when="2026-10-04T10:10:00Z")])
        self.assertTrue(rules(g.evaluate(p, c))["review"])


# ================================================================ pre-review gate (R16 process gates up front)

class PreReviewGateTests(unittest.TestCase):
    """passed_ignoring lets a CI job check everything the gate can verify when a PR opens, before anyone has
    reviewed it: every rule except review and owner, which are not expected to hold yet."""

    def test_passes_ignoring_review_and_owner_when_everything_else_is_ready(self):
        p = pr(comments=[go()])  # a plan go, but no approval yet
        ev = g.evaluate(p, CFG)
        self.assertFalse(ev["passed"], "no approval yet, so the full check must still fail")
        self.assertFalse(rules(ev)["review"])
        self.assertTrue(g.passed_ignoring(ev, "review", "owner"), g.format_report(ev, 7))

    def test_still_fails_ignoring_review_and_owner_when_something_else_is_wrong(self):
        p = pr(comments=[go()], body="no headings here")
        ev = g.evaluate(p, CFG)
        self.assertFalse(g.passed_ignoring(ev, "review", "owner"), g.format_report(ev, 7))

    def test_tier_3_also_ignores_owner_not_just_review(self):
        p = pr(labels=[{"name": "tier-3"}], comments=[go()])
        ev = g.evaluate(p, CFG)
        self.assertFalse(rules(ev)["owner"])
        self.assertTrue(g.passed_ignoring(ev, "review", "owner"), g.format_report(ev, 7))


class SameVendorOptionTests(unittest.TestCase):
    """A tier with cross_vendor false lets a LISTED same-vendor reviewer approve - but only with
    the compensating control in place: 2+ distinct identities and owner_approval on that tier
    (docs/vendor-count-modes.md). Config load refuses the tier without either half."""

    def c(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["cross_vendor"] = False
        tiers[1]["owner_approval"] = True
        return cfg(tiers=tiers, same_vendor_reviewers=[SAME_REVIEW, SAME_REVIEW_2])

    def test_off_by_default(self):
        self.assertFalse(g.evaluate(pr(comments=[go(SAME_REVIEW), approve(SAME_REVIEW)]), CFG)["passed"])

    def test_listed_reviewer_counts_at_the_chosen_tier(self):
        p = pr(comments=[go(SAME_REVIEW), approve(SAME_REVIEW),
                          comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")])
        ev = g.evaluate(p, self.c())
        self.assertTrue(ev["passed"], g.format_report(ev, 7))

    def test_an_unlisted_signer_of_the_same_vendor_never_counts(self):
        self.assertFalse(rules(g.evaluate(pr(comments=[go(AUTHOR), approve(AUTHOR)]), self.c()))["review"])

    def test_tier3_still_needs_the_other_vendor(self):
        p = pr(labels=[{"name": "tier-3"}], comments=[go(SAME_REVIEW), approve(SAME_REVIEW),
                                                      comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")])
        self.assertFalse(rules(g.evaluate(p, self.c()))["review"])

    def test_a_single_same_vendor_reviewer_is_refused_at_load(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["cross_vendor"] = False
        tiers[1]["owner_approval"] = True
        with self.assertRaises(g.ConfigError):
            cfg(tiers=tiers, same_vendor_reviewers=[SAME_REVIEW])

    def test_the_same_name_listed_twice_is_still_one_identity_and_is_refused(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["cross_vendor"] = False
        tiers[1]["owner_approval"] = True
        with self.assertRaises(g.ConfigError):
            cfg(tiers=tiers, same_vendor_reviewers=[SAME_REVIEW, SAME_REVIEW.upper()])

    def test_cross_vendor_false_without_owner_approval_is_refused_at_load(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["cross_vendor"] = False
        with self.assertRaises(g.ConfigError):
            cfg(tiers=tiers, same_vendor_reviewers=[SAME_REVIEW, SAME_REVIEW_2])

    def test_cross_vendor_false_with_zero_approvals_needs_neither(self):
        # A tier with no review requirement at all (approvals: 0) has nothing for the compensating
        # control to compensate for - cross_vendor is moot there, so it is not forced to list it.
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[0]["cross_vendor"] = False
        self.assertEqual(cfg(tiers=tiers).same_vendor_reviewers, set())


class PlanTests(unittest.TestCase):
    def test_tier2_needs_a_plan_go(self):
        self.assertFalse(rules(g.evaluate(pr(comments=[approve()]), CFG))["plan"])

    def test_go_from_the_same_vendor_does_not_count(self):
        self.assertFalse(rules(g.evaluate(pr(comments=[go(SAME_REVIEW), approve()]), CFG))["plan"])

    def test_go_from_the_owner_counts(self):
        self.assertTrue(rules(g.evaluate(pr(comments=[go(OWNER), approve()]), CFG))["plan"])
        self.assertTrue(rules(g.evaluate(pr(comments=[go("Pat"), approve()]), CFG))["plan"])

    def test_the_word_goal_is_not_go(self):
        p = pr(comments=[comment(REVIEW, "goal tests look fine", "2026-10-04T09:00:00Z"), approve()])
        self.assertFalse(rules(g.evaluate(p, CFG))["plan"])

    def test_go_not_first_is_not_go(self):
        for text in ("change the tier rule first, then go", "ok go"):
            p = pr(comments=[comment(REVIEW, text, "2026-10-04T09:00:00Z"), approve()])
            self.assertFalse(rules(g.evaluate(p, CFG))["plan"], text)


# ================================================================ tiers and protected paths

class TierTests(unittest.TestCase):
    def test_tier1_docs_needs_no_reviewer_and_no_plan(self):
        ev = g.evaluate(pr(labels=[{"name": "tier-1"}], files=[{"path": "docs/handoff.md"}], comments=[], body=""), CFG)
        self.assertTrue(ev["passed"], g.format_report(ev, 7))
        self.assertEqual(ev["tier"].level, 1)

    def test_tier1_touching_code_is_raised_to_2(self):
        self.assertEqual(g.evaluate(pr(labels=[{"name": "tier-1"}]), CFG)["tier"].level, 2)
        self.assertFalse(g.evaluate(pr(labels=[{"name": "tier-1"}], comments=[]), CFG)["passed"])

    def test_tier1_touching_tests_is_raised_to_2(self):
        self.assertEqual(g.evaluate(pr(labels=[{"name": "tier-1"}], files=[{"path": "tests/test_x.py"}]), CFG)["tier"].level, 2)

    def test_protected_paths_raise_to_the_protected_tier(self):
        for path in ("AGENTS.md", ".github/workflows/ci.yml", ".githooks/pre-push", "tools/gate/gate.py",
                     "app/payments.py", "reader.py", "migrations/001.py", "app/migrations/002.py", "scripts/x.sh",
                     "sub/reader.py"):
            self.assertEqual(g.evaluate(pr(files=[{"path": path}], labels=[{"name": "tier-1"}]), CFG)["tier"].level, 3, path)

    def test_a_slash_glob_does_not_match_by_name_elsewhere(self):
        self.assertEqual(g.evaluate(pr(files=[{"path": "lib/app/payments.py"}]), CFG)["tier"].level, 2)

    def test_protected_tier_is_configurable(self):
        self.assertEqual(g.evaluate(pr(files=[{"path": "AGENTS.md"}], labels=[{"name": "tier-1"}]),
                                    cfg(protected_tier=2))["tier"].level, 2)

    def test_tier3_needs_the_owner_to_approve_the_head(self):
        p = pr(labels=[{"name": "tier-3"}])
        ev = g.evaluate(p, CFG)
        self.assertFalse(rules(ev)["owner"])
        p["comments"].append(comment(OWNER, f"Approved at `{OLD}`", "2026-10-04T11:00:00Z"))
        self.assertFalse(rules(g.evaluate(p, CFG))["owner"])
        p["comments"].append(comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z"))
        ev = g.evaluate(p, CFG)
        self.assertTrue(ev["passed"], g.format_report(ev, 7))
        self.assertTrue(ev["owner_approved"])

    def test_owner_line_must_also_be_first_words(self):
        p = pr(labels=[{"name": "tier-3"}])
        p["comments"].append(comment(OWNER, f"fine by me. Approved at {HEAD}", "2026-10-04T12:00:00Z"))
        ev = g.evaluate(p, CFG)
        self.assertFalse(rules(ev)["owner"])
        self.assertFalse(rules(ev)["signals"])

    def test_owner_alone_is_not_the_independent_reviewer(self):
        p = pr(labels=[{"name": "tier-3"}], comments=[go(OWNER), comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")])
        self.assertFalse(rules(g.evaluate(p, CFG))["review"])

    def test_an_agent_signing_as_owner_role_with_a_vendor_is_not_the_owner(self):
        p = pr(labels=[{"name": "tier-3"}])
        p["comments"].append(comment(f"Program Owner {SEP} Alpha", f"Approved at {HEAD}", "2026-10-04T12:00:00Z"))
        self.assertFalse(rules(g.evaluate(p, CFG))["owner"])

    def test_non_mergeable_tier_never_passes(self):
        ev = g.evaluate(pr(labels=[{"name": "tier-4"}]), CFG)
        self.assertFalse(ev["passed"])
        self.assertFalse(rules(ev)["tier"])
        self.assertIn("human only", msg(ev, "tier"))

    def test_raise_into_a_non_mergeable_tier_fails(self):
        tiers = [{"label": "docs", "level": 1, "allowed_paths": ["docs/*"]}, {"label": "human", "level": 2, "mergeable": False}]
        c = cfg(tiers=tiers, protected_tier=2)
        ev = g.evaluate(pr(labels=[{"name": "docs"}]), c)
        self.assertFalse(rules(ev)["tier"])
        self.assertIn("raised", msg(ev, "tier"))

    def test_raise_with_no_higher_tier_fails(self):
        c = cfg(tiers=[{"label": "docs", "level": 1, "allowed_paths": ["docs/*"]}], protected_tier=1)
        self.assertFalse(rules(g.evaluate(pr(labels=[{"name": "docs"}]), c))["tier"])

    def test_tier_label_required_exactly_once(self):
        self.assertFalse(rules(g.evaluate(pr(labels=[]), CFG))["tier"])
        self.assertFalse(rules(g.evaluate(pr(labels=[{"name": "tier-1"}, {"name": "tier-2"}]), CFG))["tier"])

    def test_custom_labels_and_levels(self):
        tiers = [{"label": "docs-only", "level": 10, "allowed_paths": ["docs/*"]},
                 {"label": "code", "level": 20, "approvals": 1},
                 {"label": "trust", "level": 30, "approvals": 1, "owner_approval": True, "record": "T"}]
        c = cfg(tiers=tiers, protected_tier=30, body_headings=[])
        ev = g.evaluate(pr(labels=[{"name": "code"}], files=[{"path": "AGENTS.md"}]), c)
        self.assertEqual(ev["tier"].label, "trust")


class HoldTests(unittest.TestCase):
    def with_comments(self, *extra):
        p = pr()
        p["comments"] += list(extra)
        return rules(g.evaluate(p, CFG))

    def test_hold_comment_blocks(self):
        self.assertFalse(self.with_comments(comment(OWNER, "hold", "2026-10-04T10:30:00Z"))["hold"])

    def test_unsigned_hold_blocks(self):
        self.assertFalse(self.with_comments(comment(None, "Hold", "2026-10-04T10:30:00Z"))["hold"])

    def test_hold_behind_a_byte_order_mark_still_blocks(self):
        self.assertFalse(self.with_comments({"body": BOM + f"**{OWNER}:** hold", "createdAt": "2026-10-04T10:30:00Z"})["hold"])
        self.assertFalse(self.with_comments({"body": BOM + "hold", "createdAt": "2026-10-04T10:30:00Z"})["hold"])

    def test_owner_unhold_lifts_it(self):
        self.assertTrue(self.with_comments(comment(OWNER, "hold", "2026-10-04T10:30:00Z"),
                                           comment("Pat", "unhold", "2026-10-04T11:30:00Z"))["hold"])

    def test_an_agent_cannot_lift_a_hold(self):
        self.assertFalse(self.with_comments(comment(OWNER, "hold", "2026-10-04T10:30:00Z"),
                                            comment(AUTHOR, "unhold", "2026-10-04T11:30:00Z"))["hold"])

    def test_unhold_behind_a_byte_order_mark_does_not_lift(self):
        self.assertFalse(self.with_comments(comment(OWNER, "hold", "2026-10-04T10:30:00Z"),
                                            {"body": BOM + f"**{OWNER}:** unhold", "createdAt": "2026-10-04T11:30:00Z"})["hold"])

    def test_hold_label_blocks_and_is_configurable(self):
        self.assertFalse(rules(g.evaluate(pr(labels=[{"name": "tier-2"}, {"name": "hold"}]), CFG))["hold"])
        self.assertFalse(rules(g.evaluate(pr(labels=[{"name": "tier-2"}, {"name": "freeze"}]), cfg(hold_label="freeze")))["hold"])

    def test_the_word_holding_is_not_a_hold(self):
        self.assertTrue(self.with_comments(comment(AUTHOR, "holding the line on scope", "2026-10-04T10:30:00Z"))["hold"])


class OtherRuleTests(unittest.TestCase):
    def test_failed_check_blocks(self):
        p = pr()
        p["statusCheckRollup"][0]["conclusion"] = "FAILURE"
        r = rules(g.evaluate(p, CFG))
        self.assertFalse(r["check:tests"])
        self.assertTrue(r["check:scan"])

    def test_missing_check_blocks(self):
        r = rules(g.evaluate(pr(statusCheckRollup=[]), CFG))
        self.assertFalse(r["check:tests"])
        self.assertFalse(r["check:scan"])

    def test_rerun_with_a_failed_entry_blocks(self):
        p = pr()
        p["statusCheckRollup"].append({"__typename": "CheckRun", "name": "tests", "conclusion": "FAILURE"})
        self.assertFalse(rules(g.evaluate(p, CFG))["check:tests"])

    def test_status_context_form_is_read(self):
        p = pr(statusCheckRollup=[{"__typename": "StatusContext", "context": "ci/legacy", "state": "SUCCESS"}])
        self.assertTrue(rules(g.evaluate(p, cfg(required_checks=["ci/legacy"])))["check:ci/legacy"])

    def test_no_required_checks_is_allowed(self):
        self.assertTrue(g.evaluate(pr(statusCheckRollup=[]), cfg(required_checks=[]))["passed"])

    def test_forbidden_files_block(self):
        for path in ("docs/order.pdf", "scan.png", "models/x.gguf", ".env", "a/b/.env.local",
                     "data/orders.csv", "output/run1.json", "x/y.sqlite3"):
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": path}]), CFG))["files"], path)

    def test_env_example_is_allowed(self):
        for path in (".env.example", "app/.env.app.example"):
            self.assertTrue(rules(g.evaluate(pr(files=[{"path": path}]), CFG))["files"], path)

    def test_file_list_below_the_github_cap_is_verified(self):
        for count in (99, 100, 166, 2999):
            self.assertTrue(rules(g.evaluate(pr(files=n_files(count)), CFG))["files"], count)

    def test_file_list_at_the_github_cap_cannot_be_verified(self):
        for count in (3000, 3001):
            ev = g.evaluate(pr(files=n_files(count)), CFG)
            self.assertFalse(rules(ev)["files"], count)
            self.assertIn("cannot be fully verified; split the change", msg(ev, "files"))

    def test_forbidden_file_as_the_150th_entry_is_caught(self):
        ev = g.evaluate(pr(files=n_files(166, {149: "docs/order.pdf"})), CFG)
        self.assertFalse(rules(ev)["files"])
        self.assertIn("docs/order.pdf", msg(ev, "files"))

    def test_protected_path_as_the_150th_entry_raises_the_tier(self):
        ev = g.evaluate(pr(files=n_files(166, {149: "tools/gate/gate.py"}), labels=[{"name": "tier-1"}]), CFG)
        self.assertEqual(ev["tier"].level, 3)
        self.assertIn("raised to tier-3", msg(ev, "tier"))

    def test_hundred_comments_cannot_be_read(self):
        p = pr(comments=[go(), approve()] + [comment(AUTHOR, "note", f"2026-10-04T12:{i % 60:02d}:00Z") for i in range(98)])
        self.assertFalse(rules(g.evaluate(p, CFG))["comments"])

    def test_missing_body_heading_blocks_at_tier2(self):
        r = rules(g.evaluate(pr(body="## Plan\nx\n## Cost\ny\n"), CFG))
        self.assertFalse(r["evidence:Evidence"])
        self.assertTrue(r["evidence:Plan"])

    def test_draft_wrong_base_and_merged_block(self):
        self.assertFalse(rules(g.evaluate(pr(isDraft=True), CFG))["state"])
        self.assertFalse(rules(g.evaluate(pr(baseRefName="dev"), CFG))["state"])
        self.assertFalse(rules(g.evaluate(pr(state="MERGED"), CFG))["state"])
        self.assertTrue(rules(g.evaluate(pr(baseRefName="trunk"), cfg(base="trunk")))["state"])

    def test_report_carries_the_shared_account_note(self):
        text = g.format_report(g.evaluate(pr(), CFG), 7)
        self.assertIn("shared account", text)
        self.assertIn("RESULT: PASS", text)
        self.assertNotIn("shared account", g.format_report(g.evaluate(pr(), cfg(shared_account=False)), 7))


# ================================================================ the file list (ported bypass-first cases)

class FetchFilesTests(unittest.TestCase):
    def fetch(self, count, special=None):
        gh = FakeGH(pr(files=n_files(count, special)))
        return gh, g.fetch_pr(gh, cfg(), 7)

    def test_all_files_come_back_for_99_100_166_and_3000(self):
        for count in (99, 100, 166, 3000):
            _, got = self.fetch(count)
            self.assertEqual([f["path"] for f in got["files"]], [f["path"] for f in n_files(count)], count)

    def test_files_come_from_the_paginated_endpoint(self):
        gh, _ = self.fetch(166)
        api = [c for c in gh.calls if c[0] == "api"]
        self.assertEqual(len(api), 1)
        self.assertEqual(api[0][1], "repos/example-org/recipe-box/pulls/7/files?per_page=100")
        self.assertIn("--paginate", api[0])
        view = [c for c in gh.calls if c[:2] == ["pr", "view"]][0]
        self.assertNotIn("files", view[view.index("--json") + 1].split(","))

    def test_forbidden_file_past_the_100th_is_caught_end_to_end(self):
        _, got = self.fetch(166, {149: "scan.png"})
        self.assertFalse(rules(g.evaluate(got, CFG))["files"])

    def test_protected_file_past_the_100th_raises_the_tier_end_to_end(self):
        gh = FakeGH(pr(files=n_files(166, {149: "ROLES.md"}), labels=[{"name": "tier-1"}]))
        self.assertEqual(g.evaluate(g.fetch_pr(gh, cfg(), 7), CFG)["tier"].level, 3)

    def test_page_formats_are_all_read(self):
        one = json.dumps([{"filename": "a"}, {"filename": "b"}])
        self.assertEqual(len(g.parse_json_pages(one)), 2)
        self.assertEqual(len(g.parse_json_pages(one + chr(10) + one)), 4)
        self.assertEqual(len(g.parse_json_pages(json.dumps([[{"filename": "a"}], [{"filename": "b"}]]))), 2)
        self.assertEqual(g.parse_json_pages("[]"), [])
        for bad in ("", "  ", "{}", "5", "[1]", "[[1]]"):
            with self.assertRaises(g.GateError, msg=repr(bad)):
                g.parse_json_pages(bad)


class FileListProofTests(unittest.TestCase):
    """A successful call must be PROVEN complete against an independent count."""

    def gh(self, api_out, count, **over):
        return FakeGH(pr(files=[{"path": "app/a.py"}], changedFiles=count, **over), api_out=api_out)

    def test_complete_list_matching_the_count_passes(self):
        self.assertTrue(safe(self.gh(arr("a", "b", "c"), 3)))

    def test_empty_or_whitespace_output_is_refused(self):
        for out in ("", "   ", chr(10), " " + chr(10) + chr(9)):
            self.assertFalse(safe(self.gh(out, 3)), repr(out))
            self.assertFalse(safe(self.gh(out, 0)), repr(out))

    def test_empty_array_with_a_nonzero_count_is_refused(self):
        self.assertFalse(safe(self.gh("[]", 3)))

    def test_first_100_of_166_is_refused_even_with_a_forbidden_file_at_150(self):
        full = n_files(166, {149: "docs/order.pdf"})
        self.assertFalse(safe(FakeGH(pr(files=full), api_out=files_pages(full[:100]))))
        self.assertFalse(safe(FakeGH(pr(files=full))))

    def test_count_and_list_must_agree_in_both_directions(self):
        self.assertFalse(safe(self.gh(arr("a", "b"), 3)))
        self.assertFalse(safe(self.gh(arr("a", "b", "c", "d"), 3)))

    def test_missing_or_unusable_count_is_refused(self):
        for bad in (None, "3", True, 3.0, -1, [], {}):
            self.assertFalse(safe(self.gh(arr("a", "b", "c"), bad)), repr(bad))
        pull = pr(files=[{"path": "a"}])
        del pull["changedFiles"]
        self.assertFalse(safe(FakeGH(pull, api_out=arr("a"))))

    def test_evaluate_alone_also_refuses_without_a_matching_count(self):
        p = pr(files=[{"path": "app/a.py"}])
        del p["changedFiles"]
        self.assertFalse(rules(g.evaluate(p, CFG))["files"])
        self.assertFalse(rules(g.evaluate(pr(files=[{"path": "a"}], changedFiles=2), CFG))["files"])

    def test_zero_files_with_a_zero_count_is_a_valid_empty_list(self):
        self.assertTrue(safe(self.gh("[]", 0)))

    def test_more_than_3000_changed_files_stops_at_the_cap_not_in_an_error(self):
        full = n_files(3000)
        ev = g.evaluate(g.fetch_pr(FakeGH(pr(files=full, changedFiles=3500), api_out=files_pages(full)), cfg(), 7), CFG)
        self.assertFalse(rules(ev)["files"])
        self.assertIn("cannot be fully verified; split the change", msg(ev, "files"))

    def test_the_cap_holds_even_when_the_list_came_back_short(self):
        self.assertFalse(safe(FakeGH(pr(files=n_files(10), changedFiles=3000), api_out=files_pages(n_files(10)))))

    def test_pr_that_moves_while_it_is_being_read_is_refused(self):
        self.assertFalse(safe(FakeGH(pr(files=n_files(5)), after={"headRefOid": "c" * 40})))
        self.assertTrue(safe(FakeGH(pr(files=n_files(5)))))

    def test_merge_does_not_happen_on_an_unproven_list(self):
        gh = FakeGH(pr(files=n_files(166, {149: "docs/order.pdf"})), api_out=files_pages(n_files(100)))
        self.assertNotEqual(try_merge(gh)[0], 0)
        self.assertEqual(gh.merged(), [])


class MalformedFileListTests(unittest.TestCase):
    def gh(self, api_out, count=1):
        return FakeGH(pr(files=[{"path": "app/a.py"}], changedFiles=count), api_out=api_out)

    def test_each_malformed_output_is_refused(self):
        cases = {
            "message object": json.dumps({"message": "unexpected response"}),
            "empty entry": "[{}]",
            "empty filename": json.dumps([{"filename": ""}]),
            "numeric filename": json.dumps([{"filename": 5}]),
            "null filename": json.dumps([{"filename": None}]),
            "list filename": json.dumps([{"filename": ["a"]}]),
            "string entry": json.dumps(["a.py"]),
            "null entry": json.dumps([None]),
            "scalar": "5",
            "string page": json.dumps("a.py"),
            "bad entry beside a good one": json.dumps([{"filename": "app/ok.py"}, {}]),
            "bad entry in a later page": arr("a.py") + "[{}]",
            "message after a good page": arr("a.py") + json.dumps({"message": "rate limited"}),
            "truncated json": arr("a.py")[:-3],
            "trailing garbage": arr("a.py") + "oops",
            "mixed array of arrays": json.dumps([[{"filename": "a.py"}], "x"]),
            "nested twice": json.dumps([[[{"filename": "a.py"}]]]),
            "bad previous_filename": json.dumps([{"filename": "a.py", "previous_filename": 5}]),
            "empty previous_filename": json.dumps([{"filename": "a.py", "previous_filename": ""}]),
        }
        for label, out in cases.items():
            self.assertFalse(safe(self.gh(out, 1)), label)
            self.assertFalse(safe(self.gh(out, 2)), label)

    def test_a_duplicate_path_is_an_error_not_silently_merged(self):
        self.assertFalse(safe(self.gh(arr("a.py", "a.py"), 2)))
        self.assertFalse(safe(self.gh(arr("a.py", "a.py"), 1)))
        self.assertFalse(safe(self.gh(arr("a.py", "b.py") + arr("a.py"), 3)))
        self.assertFalse(rules(g.evaluate(pr(files=[{"path": "a.py"}, {"path": "a.py"}], changedFiles=2), CFG))["files"])

    def test_a_record_without_a_path_is_refused_by_evaluate_too(self):
        for bad in ({}, {"path": ""}, {"path": None}, {"path": 5}, {"path": "a", "previous_path": 5}):
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": "app/a.py"}, bad], changedFiles=2), CFG))["files"], repr(bad))

    def test_all_three_page_shapes_still_read(self):
        one, two = arr("a.py", "b.py"), arr("c.py")
        self.assertTrue(safe(self.gh(one + two, 3)))
        self.assertTrue(safe(self.gh(one + chr(10) + two, 3)))
        self.assertTrue(safe(self.gh(json.dumps([json.loads(one), json.loads(two)]), 3)))

    def test_null_previous_filename_is_the_same_as_none(self):
        self.assertTrue(safe(self.gh(json.dumps([{"filename": "a.py", "status": "added", "previous_filename": None}]), 1)))


class RenameTests(unittest.TestCase):
    """The old name of a renamed file is judged too."""

    def run_rename(self, old, new, label):
        got = g.fetch_pr(FakeGH(pr(files=[{"path": new, "previous": old}], labels=[{"name": label}])), cfg(), 7)
        return got, g.evaluate(got, CFG)

    def test_protected_file_renamed_away_raises_the_tier(self):
        for old, new, label in (("reader.py", "app/ordinary.py", "tier-2"),
                                (".github/workflows/check.yml", "docs/check.yml", "tier-1"),
                                ("ROLES.md", "docs/roles-copy.md", "tier-1"),
                                ("tools/gate/gate.py", "tools/other/gate.py", "tier-2")):
            self.assertEqual(self.run_rename(old, new, label)[1]["tier"].level, 3, old)

    def test_forbidden_file_renamed_away_is_blocked(self):
        for old, new in (("output/private.csv", "docs/public.csv"), ("data/orders.csv", "docs/x.csv"),
                         (".env", "docs/env-notes.txt"), ("scan.png", "docs/scan.txt")):
            self.assertFalse(rules(self.run_rename(old, new, "tier-1")[1])["files"], old)

    def test_forbidden_file_renamed_into_place_is_still_blocked(self):
        self.assertFalse(rules(self.run_rename("docs/a.txt", "output/b.csv", "tier-1")[1])["files"])

    def test_code_renamed_into_docs_is_not_tier_1(self):
        self.assertEqual(self.run_rename("app/tiers.py", "docs/tiers.md", "tier-1")[1]["tier"].level, 2)

    def test_ordinary_rename_passes(self):
        _, ev = self.run_rename("app/a.py", "app/b.py", "tier-2")
        self.assertTrue(rules(ev)["files"])
        self.assertEqual(ev["tier"].level, 2)

    def test_the_cap_counts_a_rename_once(self):
        self.assertTrue(safe(FakeGH(pr(files=[{"path": f"app/new{i}.py", "previous": f"app/old{i}.py"} for i in range(2000)]))))

    def test_rename_swapping_two_names_is_not_a_duplicate(self):
        self.assertTrue(safe(FakeGH(pr(files=[{"path": "app/a.py", "previous": "app/b.py"},
                                              {"path": "app/b.py", "previous": "app/a.py"}]))))

    def test_a_merge_of_a_protected_rename_needs_owner_approval(self):
        gh = FakeGH(pr(files=[{"path": "app/ordinary.py", "previous": "reader.py"}], labels=[{"name": "tier-2"}]))
        self.assertEqual(try_merge(gh)[0], 1)
        self.assertEqual(gh.merged(), [])


class WhichDiffTests(unittest.TestCase):
    """The list must belong to the same diff the gate evaluates; each identity field varied on its own."""

    def run_with(self, after=None, **over):
        return FakeGH(pr(files=[{"path": "app/ordinary.py"}], **over), after=after)

    def test_nothing_moving_passes(self):
        self.assertTrue(safe(self.run_with()))
        self.assertTrue(safe(self.run_with(after={})))

    def test_each_field_that_moves_on_its_own_is_refused(self):
        for label, after in {"head": {"headRefOid": "c" * 40}, "base sha": {"baseRefOid": "e" * 40},
                             "base branch": {"baseRefName": "dev"}, "head branch": {"headRefName": "beta/other"},
                             "count": {"changedFiles": 2}, "number": {"number": 8}}.items():
            self.assertFalse(safe(self.run_with(after=after)), label)

    def test_base_moves_with_constant_head_and_constant_count(self):
        self.assertFalse(safe(self.run_with(after={"baseRefOid": "e" * 40})))
        gh = self.run_with(after={"baseRefOid": "e" * 40})
        self.assertNotEqual(try_merge(gh)[0], 0)
        self.assertEqual(gh.merged(), [])

    def test_a_field_missing_from_the_second_look_is_refused(self):
        for field in g.SNAPSHOT_FIELDS:
            self.assertFalse(safe(self.run_with(after={field: DROP})), field)

    def test_a_field_missing_or_unusable_in_the_first_look_is_refused(self):
        for field, bad in (("baseRefOid", DROP), ("baseRefOid", None), ("baseRefOid", ""), ("baseRefOid", "xyz"),
                           ("baseRefOid", 5), ("baseRefOid", "D" * 40), ("headRefOid", DROP), ("headRefOid", ""),
                           ("headRefOid", "abc"), ("baseRefName", DROP), ("baseRefName", ""), ("number", DROP),
                           ("headRefName", DROP), ("changedFiles", DROP)):
            pull = pr(files=[{"path": "app/ordinary.py"}])
            if bad is DROP:
                del pull[field]
            else:
                pull[field] = bad
            self.assertFalse(safe(FakeGH(pull)), (field, bad))

    def test_the_pr_that_comes_back_must_be_the_pr_asked_for(self):
        self.assertFalse(safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}], number=8))))


class FreshStateTests(unittest.TestCase):
    """Comments, labels and checks are judged as of the second look, so a hold or a failing check that lands while
    the file list is being read still blocks the merge."""

    def merge_with_later(self, **later):
        gh = FakeGH(pr(files=[{"path": "app/ordinary.py"}]), after=later)
        return gh, try_merge(gh)

    def test_control_without_a_change_merges(self):
        gh, (code, _) = self.merge_with_later()
        self.assertEqual(code, 0)
        self.assertEqual(len(gh.merged()), 1)

    def test_a_hold_posted_between_the_reads_blocks_the_merge(self):
        hold = comment(OWNER, "hold", "2099-01-01T00:00:00Z")
        gh, (code, report) = self.merge_with_later(comments=[go(), approve(), hold])
        self.assertNotEqual(code, 0)
        self.assertEqual(gh.merged(), [])
        self.assertIn("hold", report)

    def test_a_check_that_fails_between_the_reads_blocks_the_merge(self):
        failing = [{"__typename": "CheckRun", "name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"}]
        gh, (code, _) = self.merge_with_later(statusCheckRollup=failing)
        self.assertNotEqual(code, 0)
        self.assertEqual(gh.merged(), [])

    def test_a_label_removed_between_the_reads_is_seen(self):
        pull = g.fetch_pr(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), after={"labels": []}), cfg(), 7)
        self.assertEqual(pull["labels"], [])

    def test_the_file_list_is_kept_from_the_pinned_read(self):
        pull = g.fetch_pr(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), after={"comments": []}), cfg(), 7)
        self.assertEqual([f["path"] for f in pull["files"]], ["app/ordinary.py"])


class RenameStatusTests(unittest.TestCase):
    def one(self, status, prev):
        entry = {"filename": "app/ordinary.py"}
        if status is not DROP:
            entry["status"] = status
        if prev is not DROP:
            entry["previous_filename"] = prev
        return safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), api_out=json.dumps([entry])))

    def test_status_by_previous_name_matrix(self):
        bad_prev = (None, "", 5, True, ["reader.py"], {"a": 1})
        for status in ("added", "modified", "removed", "changed", "unchanged"):
            self.assertTrue(self.one(status, DROP), status)
            self.assertTrue(self.one(status, None), status)
            self.assertTrue(self.one(status, "app/old.py"), status)
            for prev in bad_prev[1:]:
                self.assertFalse(self.one(status, prev), (status, prev))
        for status in ("renamed", "copied"):
            self.assertTrue(self.one(status, "app/old.py"), status)
            self.assertFalse(self.one(status, DROP), status)
            for prev in bad_prev:
                self.assertFalse(self.one(status, prev), (status, prev))

    def test_missing_or_unknown_status_is_refused(self):
        for status in (DROP, None, "", 5, ["renamed"], "Renamed", "moved"):
            self.assertFalse(self.one(status, "app/old.py"), status)
            self.assertFalse(self.one(status, DROP), status)

    def test_evaluate_alone_refuses_a_rename_record_without_an_old_name(self):
        for rec in ({"path": "a.py", "status": "renamed"}, {"path": "a.py", "status": "renamed", "previous_path": None},
                    {"path": "a.py", "status": "copied"}):
            self.assertFalse(rules(g.evaluate(pr(files=[rec]), CFG))["files"], rec)
        self.assertTrue(rules(g.evaluate(pr(files=[{"path": "a.py", "status": "added"}]), CFG))["files"])


NL, CR, TAB, NUL, BS = chr(10), chr(13), chr(9), chr(0), chr(92)


class StrictValueTests(unittest.TestCase):
    SHA_BAD = [HEAD + NL, HEAD + CR + NL, " " + HEAD, HEAD + " ", TAB + HEAD, "A" * 40, "a" * 39, "a" * 41,
               "g" * 40, "", None, 5, True, ["a" * 40], {"sha": HEAD}, "0x" + "a" * 38]
    COUNT_BAD = [True, False, 1.0, 1.5, "1", None, -1, [], {}, 2]
    NUMBER_BAD = ["7", 7.0, True, None, 8, [], 0]
    NAME_BAD = ["", None, 5, ["main"], "main" + NL, " main", "main ", "ma" + TAB + "in", "main" + CR, NUL + "main", True]

    def check(self, field, bad):
        for where in ("first", "second", "both"):
            pull, after = pr(files=[{"path": "app/ordinary.py"}]), {}
            if where in ("first", "both"):
                pull[field] = bad
            if where in ("second", "both"):
                after[field] = bad
            self.assertFalse(safe(FakeGH(pull, after=after)), (field, repr(bad), where))

    def test_commit_ids_are_matched_as_whole_strings(self):
        for field in ("baseRefOid", "headRefOid"):
            for bad in self.SHA_BAD:
                self.check(field, bad)

    def test_file_count_must_be_a_real_integer(self):
        for bad in self.COUNT_BAD:
            self.check("changedFiles", bad)

    def test_number_must_be_the_integer_asked_for(self):
        for bad in self.NUMBER_BAD:
            self.check("number", bad)

    def test_branch_names_must_be_clean_non_empty_text(self):
        for field in ("baseRefName", "headRefName"):
            for bad in self.NAME_BAD:
                self.check(field, bad)

    def test_equal_but_not_identical_type_never_counts_as_unchanged(self):
        for field, second in (("changedFiles", True), ("changedFiles", 1.0), ("number", 7.0), ("number", True)):
            self.assertFalse(safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), after={field: second})), (field, second))


class StrictPathTests(unittest.TestCase):
    BAD_PATHS = ["x.pdf" + NL, "x.pdf" + CR, " reader.py", "reader.py ", "a" + TAB + "b.py", "a" + NUL + "b.py",
                 "/abs.py", "./a.py", "a/./b.py", "a/../b.py", "../a.py", "a//b.py", "a" + BS + "b.py", "a/", ".", "..",
                 "reader.py" + NL + "x"]

    def entry(self, **kw):
        e = {"filename": "app/ordinary.py", "status": "added"}
        e.update(kw)
        return json.dumps([e])

    def run_entry(self, out):
        return safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), api_out=out))

    def test_bad_file_names_are_refused(self):
        for bad in self.BAD_PATHS:
            self.assertFalse(self.run_entry(self.entry(filename=bad)), repr(bad))

    def test_bad_old_names_are_refused_for_every_status(self):
        for bad in self.BAD_PATHS:
            for status in ("renamed", "modified", "added"):
                self.assertFalse(self.run_entry(self.entry(status=status, previous_filename=bad)), (status, repr(bad)))

    def test_status_must_be_exact_lowercase_text(self):
        for bad in ("added" + NL, " added", "added ", "ADDED", "Added", "renamed" + NL, "RENAMED", "added" + CR):
            self.assertFalse(self.run_entry(self.entry(status=bad, previous_filename="app/old.py")), repr(bad))

    def test_evaluate_alone_refuses_bad_names_and_statuses(self):
        for bad in self.BAD_PATHS:
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": bad}]), CFG))["files"], repr(bad))
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": "app/ordinary.py", "previous_path": bad}]), CFG))["files"], repr(bad))
        for bad in ("ADDED", "added" + NL, 5, None, "moved"):
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": "app/ordinary.py", "status": bad}]), CFG))["files"], repr(bad))

    def test_forbidden_files_are_caught_whatever_their_case(self):
        for path in ("SCAN.PNG", "docs/Order.PDF", ".ENV", "a/.Env.Local", "Data/orders.csv", "OUTPUT/run.json",
                     "x/Model.GGUF", "TMP/x.txt", ".VENV/lib/x.py"):
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": path}]), CFG))["files"], path)

    def test_the_env_example_allowance_stays_exact(self):
        self.assertTrue(rules(g.evaluate(pr(files=[{"path": ".env.example"}]), CFG))["files"])
        self.assertFalse(rules(g.evaluate(pr(files=[{"path": ".ENV.EXAMPLE"}]), CFG))["files"])

    def test_protected_files_raise_the_tier_whatever_their_case(self):
        for path in ("Reader.py", "READER.PY", ".GitHub/workflows/x.yml", "tools/Gate/gate.py", "roles.md",
                     "Scripts/run.py", "MIGRATIONS/x.py"):
            self.assertEqual(g.evaluate(pr(files=[{"path": path}], labels=[{"name": "tier-1"}]), CFG)["tier"].level, 3, path)

    def test_docs_shortcut_for_tier_1_stays_case_exact(self):
        self.assertEqual(g.evaluate(pr(files=[{"path": "DOCS/x.md"}], labels=[{"name": "tier-1"}]), CFG)["tier"].level, 2)


def code_points(*numbers):
    return [chr(n) for n in numbers]


C_CHARS = code_points(0x00, 0x1f, 0x7f, 0x80, 0x85, 0x9f, 0xad, 0x61c, 0x200b, 0x200d, 0x200e, 0x202a, 0x202e,
                      0x2060, 0x2066, 0x2069, 0xfeff, 0xfff9, 0xd800, 0xdc00, 0xdfff, 0xe000, 0xf8ff, 0x378,
                      0xfdd0, 0xffff, 0xf0000, 0xe0001)
Z_CHARS = code_points(0xa0, 0x1680, 0x2000, 0x2003, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000)
DRIVE_AND_ROOTED = ["C:/tools/gate/gate.py", "c:" + BS + "x", "C:x", "C:", "z:/a/b.py", "C:" + BS + "tools" + BS + "x.py",
                    "//server/share/x.py", "//x", "/x", "/tools/gate/gate.py", BS + BS + "?" + BS + "C:" + BS + "x",
                    BS + BS + "server" + BS + "share" + BS + "x.py", BS + "x", "~/x" + BS + "y"]


class UnicodeAndRootedPathTests(unittest.TestCase):
    def test_the_character_lists_really_are_in_those_categories(self):
        for ch in C_CHARS:
            self.assertTrue(unicodedata.category(ch).startswith("C"), hex(ord(ch)))
        for ch in Z_CHARS:
            self.assertTrue(unicodedata.category(ch).startswith("Z"), hex(ord(ch)))

    def paths_with(self, chars):
        for ch in chars:
            yield "tools/gate" + ch + "/gate.py"
            yield ch + "tools/gate/gate.py"
            yield "tools/gate/gate.py" + ch
            yield "docs/a" + ch + "b.md"

    def entry(self, **kw):
        e = {"filename": "app/ordinary.py", "status": "added"}
        e.update(kw)
        return json.dumps([e])

    def fetched_ok(self, out):
        return safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}]), api_out=out))

    def test_new_and_old_names_with_c_or_z_characters_or_roots_are_refused(self):
        for bad in list(self.paths_with(C_CHARS + Z_CHARS)) + DRIVE_AND_ROOTED:
            self.assertFalse(self.fetched_ok(self.entry(filename=bad)), repr(bad))
            self.assertFalse(self.fetched_ok(self.entry(status="renamed", previous_filename=bad)), repr(bad))
            self.assertFalse(rules(g.evaluate(pr(files=[{"path": bad}]), CFG))["files"], repr(bad))

    def test_branch_names_with_c_or_z_characters_are_refused(self):
        for field in ("baseRefName", "headRefName"):
            for ch in C_CHARS + Z_CHARS + [" "]:
                for where in ("first", "second", "both"):
                    pull, after = pr(files=[{"path": "app/ordinary.py"}]), {}
                    if where in ("first", "both"):
                        pull[field] = "beta/" + ch + "bad"
                    if where in ("second", "both"):
                        after[field] = "beta/" + ch + "bad"
                    self.assertFalse(safe(FakeGH(pull, after=after)), (field, hex(ord(ch)), where))

    def test_ordinary_non_ascii_names_and_inner_spaces_still_pass(self):
        for good in ("docs/caf" + chr(0xe9) + ".md", "docs/" + chr(0x65e5) + chr(0x672c) + "/" + chr(0x6ce8) + ".txt",
                     "my docs/a b.txt", "src/na" + chr(0xef) + "ve file.py", "docs/emoji-" + chr(0x1f600) + ".md",
                     "a-b_c.d/e+f.py", ".github-notes/x.md"):
            self.assertTrue(self.fetched_ok(self.entry(filename=good)), repr(good))
            self.assertTrue(rules(g.evaluate(pr(files=[{"path": good}]), CFG))["files"], repr(good))

    def test_non_ascii_branch_names_without_controls_still_pass(self):
        self.assertTrue(safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}], headRefName="beta/caf" + chr(0xe9)))))


BAD_GIT_BRANCHES = [
    "beta/../x", "beta/a..b", "beta/./x", "beta/.hidden/x", "beta/x.lock", "beta/x.lock/y",
    "beta//x", "beta/x/", "/beta/x", "//server/share/x", "beta/x.", "beta/a@{b",
    "beta/a~b", "beta/a^b", "beta/a:b", "beta/a?b", "beta/a*b", "beta/a[b", "beta/a" + BS + "b",
    "C:/x", "C:x", BS + BS + "server" + BS + "share" + BS + "x", "-beta/x",
    "beta/@{", ".beta/x", "beta/.x", "beta/", "/", "//", "beta/a..", "..", ".", "-", "--x", "beta/a b",
    "beta/a" + chr(127) + "b", "x.lock", "beta/a/.lock", "a/b.lock/c",
]
GOOD_GIT_BRANCHES = ["@", "beta/@", "@x", "x@", "beta/some-task", "main", "feature", "beta/v1.2.3",
                     "beta/task-42", "beta/caf" + chr(0xe9), "beta/" + chr(0x65e5) + chr(0x672c), "a@b", "beta/a]b",
                     "beta/x.locked", "beta/a.lock.b", "beta/a_b/c-d", "beta/UPPER"]


def git_accepts_branch(name):
    return subprocess.run(["git", "check-ref-format", "--branch", name], capture_output=True).returncode == 0


class GitBranchGrammarTests(unittest.TestCase):
    def test_invalid_branches_never_reach_the_merge(self):
        for bad in BAD_GIT_BRANCHES:
            for field in ("headRefName", "baseRefName"):
                for where in ("first", "second", "both"):
                    pull, after = pr(files=[{"path": "app/ordinary.py"}]), {}
                    if where in ("first", "both"):
                        pull[field] = bad
                    if where in ("second", "both"):
                        after[field] = bad
                    gh = FakeGH(pull, after=after)
                    self.assertNotEqual(try_merge(gh)[0], 0, (field, repr(bad), where))
                    self.assertEqual(gh.merged(), [], (field, repr(bad), where))

    def test_valid_branch_names_still_pass(self):
        for good in GOOD_GIT_BRANCHES:
            self.assertTrue(safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}], headRefName=good))), repr(good))
            self.assertTrue(safe(FakeGH(pr(files=[{"path": "app/ordinary.py"}], baseRefName=good))), repr(good))

    def test_a_tier_1_docs_pr_from_a_branch_named_at_merges_by_the_owner(self):
        for head in ("@", "beta/@", "@x"):
            gh = FakeGH(pr(labels=[{"name": "tier-1"}], files=[{"path": "docs/handoff.md"}], comments=[], body="",
                           headRefName=head))
            self.assertEqual(try_merge(gh, OWNER)[0], 0, head)
            self.assertEqual(len(gh.merged()), 1, head)

    def test_matrix_agrees_with_git_check_ref_format(self):
        try:
            git_accepts_branch("main")
        except OSError:
            self.skipTest("git not available")
        for name in BAD_GIT_BRANCHES:
            self.assertFalse(git_accepts_branch(name), repr(name))
            self.assertIsNotNone(g.bad_branch(name), repr(name))
        for name in GOOD_GIT_BRANCHES:
            self.assertTrue(git_accepts_branch(name), repr(name))
            self.assertIsNone(g.bad_branch(name), repr(name))

    def test_every_printable_ascii_character_agrees_with_git(self):
        try:
            git_accepts_branch("main")
        except OSError:
            self.skipTest("git not available")
        for c in range(33, 127):
            ch = chr(c)
            for name in (ch, "a" + ch + "b", "a/" + ch, ch + "/a", "a" + ch, ch + "a", "a." + ch):
                self.assertEqual(g.bad_branch(name) is None, git_accepts_branch(name), repr(name))


class RepoNameTests(unittest.TestCase):
    def test_odd_repository_names_are_refused(self):
        for bad in ("", "owner", "owner/", "/name", "a/b/c", "o wner/name", "owner/na" + NL + "me", "owner" + NL + "/n",
                    "../x", "owner/..", "owner/name?x", "owner/name#1", "owner:x/name", "own" + chr(0x200b) + "er/name",
                    "owner/name" + BS, "-owner/name"):
            gh = FakeGH(pr())
            detected = lambda args, _g=gh, _b=bad: _b + NL if args[:2] == ["repo", "view"] else _g(args)
            with self.assertRaises(g.GateError, msg=repr(bad)):
                g.fetch_pr(detected, cfg(repo=""), 7)
            if bad:
                with self.assertRaises(g.GateError, msg=repr(bad)):
                    g.fetch_pr(gh, cfg(repo=bad), 7)

    def test_normal_repository_names_pass(self):
        for good in ("example-org/recipe-box", "a/b", "o-w_n.er/name.with.dots"):
            self.assertEqual(g.repo_of(FakeGH(pr()), cfg(repo=good)), good)


# ================================================================ merge pinning and the Gate-Record trailer

class MergeTests(unittest.TestCase):
    def run_merge(self, gh, merged_as=AUTHOR, c=None, **kw):
        lines = []
        code = g.cmd_merge(gh, c or cfg(), 7, merged_as, out=lines.append, **kw)
        return code, "\n".join(lines)

    def body(self, gh):
        call = gh.merged()[0]
        return call[call.index("--body") + 1]

    def test_passing_pr_is_merged_pinned_to_head_with_a_record(self):
        gh = FakeGH(pr())
        code, out = self.run_merge(gh)
        self.assertEqual(code, 0, out)
        call = gh.merged()[0]
        self.assertEqual(call[call.index("--match-head-commit") + 1], HEAD)
        self.assertIn("--squash", call)
        body = self.body(gh)
        self.assertEqual(body, f"Gate-Record: pass tier=2 head={HEAD} reviewers={REVIEW} owner=no by={AUTHOR}")
        self.assertTrue(CFG.trailer.search(body))

    def test_record_uses_the_configured_tier_record(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["record"] = "code"
        c = cfg(tiers=tiers)
        gh = FakeGH(pr())
        self.assertEqual(self.run_merge(gh, c=c)[0], 0)
        self.assertIn("Gate-Record: pass tier=code head=", self.body(gh))
        self.assertTrue(c.trailer.search(self.body(gh)))

    def test_repo_is_detected_when_not_configured(self):
        gh = FakeGH(pr())
        self.run_merge(gh, c=cfg(repo=""))
        call = gh.merged()[0]
        self.assertEqual(call[call.index("--repo") + 1], "example-org/recipe-box")

    def test_failing_pr_is_not_merged(self):
        p = pr()
        p["statusCheckRollup"][0]["conclusion"] = "FAILURE"
        gh = FakeGH(p)
        self.assertEqual(self.run_merge(gh)[0], 1)
        self.assertEqual(gh.merged(), [])

    def test_held_pr_is_not_merged(self):
        p = pr()
        p["comments"].append(comment(OWNER, "hold", "2026-10-04T10:30:00Z"))
        gh = FakeGH(p)
        self.assertEqual(self.run_merge(gh)[0], 1)
        self.assertEqual(gh.merged(), [])

    def test_the_other_vendor_cannot_merge(self):
        for who in (REVIEW, LEGACY_REVIEW, f"Release Manager {SEP} Alpha"):
            gh = FakeGH(pr())
            with self.assertRaises(g.GateError, msg=who):
                self.run_merge(gh, merged_as=who)
            self.assertEqual(gh.merged(), [])

    def test_unknown_or_malformed_merger_is_refused(self):
        for who in ("", "  ", f"Gemini {SEP} x", "Bolt", "just me", f"Release Manager {SEP} Gamma",
                    "Release Manager", f"Release Manager {SEP} Beta\nby=x"):
            with self.assertRaises(g.GateError, msg=who):
                self.run_merge(FakeGH(pr()), merged_as=who)

    def test_new_and_legacy_signers_of_the_author_vendor_may_merge(self):
        for who in (MERGER, AUTHOR, f"Bolt {SEP} goal gaps", f"Bee {SEP} design"):
            self.assertEqual(self.run_merge(FakeGH(pr()), merged_as=who)[0], 0, who)

    def test_merger_roles_restrict_who_merges(self):
        c = cfg(merger_roles=["Release Manager"])
        self.assertEqual(self.run_merge(FakeGH(pr()), merged_as=MERGER, c=c)[0], 0)
        with self.assertRaises(g.GateError):
            self.run_merge(FakeGH(pr()), merged_as=AUTHOR, c=c)

    def test_a_reviewer_who_approved_cannot_merge(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[1]["cross_vendor"] = False
        tiers[1]["owner_approval"] = True
        c = cfg(tiers=tiers, same_vendor_reviewers=[SAME_REVIEW, SAME_REVIEW_2])
        gh = FakeGH(pr(comments=[go(SAME_REVIEW), approve(SAME_REVIEW),
                                  comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z")]))
        with self.assertRaises(g.GateError):
            self.run_merge(gh, merged_as=SAME_REVIEW.lower(), c=c)
        self.assertEqual(gh.merged(), [])

    def test_the_owner_may_merge(self):
        self.assertEqual(self.run_merge(FakeGH(pr()), merged_as=OWNER)[0], 0)

    def test_tier3_merges_only_with_owner_approval_and_records_it(self):
        p = pr(labels=[{"name": "tier-3"}])
        gh = FakeGH(p)
        self.assertEqual(self.run_merge(gh)[0], 1)
        self.assertEqual(gh.merged(), [])
        p["comments"].append(comment(OWNER, f"Approved at `{HEAD}`", "2026-10-04T12:00:00Z"))
        code, out = self.run_merge(gh)
        self.assertEqual(code, 0, out)
        self.assertIn("owner=yes", self.body(gh))
        self.assertIn("tier=3", self.body(gh))

    def test_dry_run_prints_and_does_not_merge(self):
        gh = FakeGH(pr())
        code, out = self.run_merge(gh, dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", out)
        self.assertIn("--match-head-commit", out)
        self.assertEqual(gh.merged(), [])


# ================================================================ local git fixtures

def _rm_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)   # git marks object files read-only; Windows refuses to delete them otherwise
    func(path)


def remove_tree(path):
    try:
        shutil.rmtree(path, onexc=_rm_readonly)       # Python 3.12+
    except TypeError:
        shutil.rmtree(path, onerror=_rm_readonly)


def git_repo(test):
    d = tempfile.mkdtemp()
    test.addCleanup(remove_tree, d)

    def git(*a):
        return subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Tester")
    git("config", "core.autocrlf", "false")
    return d, git


def write(d, name, data):
    path = os.path.join(d, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def git_runner(d):
    return lambda args, binary=False: g.run_git(args, cwd=d, binary=binary)


class AuditTests(unittest.TestCase):
    def first(self):
        d, git = git_repo(self)
        write(d, "a.txt", "1")
        git("add", ".")
        git("commit", "-q", "-m", "first")
        return d, git, git("rev-parse", "HEAD")

    def audit(self, d, rng, c=None):
        lines = []
        code = g.cmd_audit(git_runner(d), c or CFG, rng, out=lines.append)
        return code, "\n".join(lines)

    def commit(self, d, git, n, *msgs):
        write(d, "a.txt", str(n))
        args = ["commit", "-qam", msgs[0]]
        for m in msgs[1:]:
            args += ["-m", m]
        git(*args)
        return git("rev-parse", "HEAD")

    def test_flags_commit_without_a_gate_record(self):
        d, git, base = self.first()
        self.commit(d, git, 2, "good change (#1)", f"Gate-Record: pass tier=2 head={'c' * 40} reviewers=x owner=no by=y")
        head = self.commit(d, git, 3, "sneaky direct push")
        code, text = self.audit(d, f"{base}..{head}")
        self.assertEqual(code, 1)
        self.assertIn("sneaky direct push", text)
        self.assertNotIn("good change", text)

    def test_clean_range_passes(self):
        d, git, base = self.first()
        head = self.commit(d, git, 2, "ok (#2)", f"Gate-Record: pass tier=1 head={'d' * 40} reviewers=none owner=no by=y")
        self.assertEqual(self.audit(d, f"{base}..{head}")[0], 0)

    def test_record_for_a_non_mergeable_or_unknown_tier_is_not_accepted(self):
        for tier in ("4", "9", "x", "22"):
            d, git, base = self.first()
            head = self.commit(d, git, 2, "forged", f"Gate-Record: pass tier={tier} head={'e' * 40} owner=yes by=y")
            self.assertEqual(self.audit(d, f"{base}..{head}")[0], 1, tier)

    def test_record_with_a_short_or_bad_head_is_not_accepted(self):
        for head_value in ("e" * 39, "E" * 40, "e" * 39 + "g"):
            d, git, base = self.first()
            head = self.commit(d, git, 2, "forged", f"Gate-Record: pass tier=2 head={head_value} owner=no by=y")
            self.assertEqual(self.audit(d, f"{base}..{head}")[0], 1, head_value)

    def test_owner_tier_record_without_owner_is_flagged_and_with_owner_is_listed(self):
        d, git, base = self.first()
        mid = self.commit(d, git, 2, "risky A", f"Gate-Record: pass tier=3 head={'e' * 40} reviewers=x owner=no by=y")
        code, text = self.audit(d, f"{base}..{mid}")
        self.assertEqual(code, 1)
        self.assertIn("without owner approval", text)
        head = self.commit(d, git, 3, "risky B", f"Gate-Record: pass tier=3 head={'f' * 40} reviewers=x owner=yes by=y")
        code, text = self.audit(d, f"{mid}..{head}")
        self.assertEqual(code, 0)
        self.assertIn("Owner-approval merges in this range", text)
        self.assertIn("risky B", text)

    def test_owner_yes_smuggled_into_the_reviewer_names_does_not_count(self):
        d, git, base = self.first()
        head = self.commit(d, git, 2, "sneaky", f"Gate-Record: pass tier=3 head={'e' * 40} reviewers=owner=yes owner=no by=y")
        self.assertEqual(self.audit(d, f"{base}..{head}")[0], 1)

    def test_custom_record_values_are_read(self):
        tiers = json.loads(json.dumps(RAW["tiers"]))
        tiers[2]["record"] = "trust"
        c = cfg(tiers=tiers)
        d, git, base = self.first()
        head = self.commit(d, git, 2, "t", f"Gate-Record: pass tier=trust head={'e' * 40} reviewers=x owner=no by=y")
        self.assertIn("without owner approval", self.audit(d, f"{base}..{head}", c)[1])

    def test_new_branch_push_audits_only_the_tip(self):
        d, git, base = self.first()
        code, text = self.audit(d, f"{'0' * 40}..{base}")
        self.assertEqual(code, 1)
        self.assertEqual(len([l for l in text.split("\n") if l.startswith("  ")]), 1)

    def test_exempt_commit_is_skipped(self):
        d, git, base = self.first()
        head = self.commit(d, git, 2, "adoption commit")
        self.assertEqual(self.audit(d, f"{base}..{head}", cfg(audit_exempt=[head]))[0], 0)


class ScanTests(unittest.TestCase):
    def repo_with(self, files):
        d, git = git_repo(self)
        for name, data in files.items():
            write(d, name, data)
        git("add", "-A")
        return d, git

    def scan(self, d, c=None, **kw):
        lines = []
        code = g.cmd_scan(git_runner(d), c or CFG, out=lines.append, **kw)
        return code, "\n".join(lines)

    def test_clean_repo_passes(self):
        d, git = self.repo_with({"src/a.py": b"print('hi')\n", "README.md": b"# hi\n", ".env.example": b"KEY=\n"})
        git("commit", "-q", "-m", "x")
        self.assertEqual(self.scan(d)[0], 0)

    def test_pdf_renamed_to_txt_is_caught_by_content(self):
        d, git = self.repo_with({"notes/order.txt": b"%PDF-1.4\n%fake body\n"})
        git("commit", "-q", "-m", "x")
        code, out = self.scan(d)
        self.assertEqual(code, 1)
        self.assertIn("content is a PDF", out)

    def test_every_default_magic_kind_is_caught_by_content(self):
        files = {f"m{i}.dat": bytes.fromhex(m["hex"]) + b"rest" for i, m in enumerate(g.DEFAULT_MAGIC)}
        d, git = self.repo_with(files)
        git("commit", "-q", "-m", "x")
        out = self.scan(d)[1]
        for m in g.DEFAULT_MAGIC:
            self.assertIn(m["kind"], out)

    def test_magic_list_is_configurable(self):
        d, git = self.repo_with({"a.dat": b"PK\x03\x04zip", "b.dat": b"%PDF-1.4"})
        git("commit", "-q", "-m", "x")
        out = self.scan(d, c=cfg(magic=[{"hex": "504b0304", "kind": "ZIP archive"}]))[1]
        self.assertIn("ZIP archive", out)
        self.assertNotIn("PDF", out)

    def test_data_folder_is_forbidden_by_name(self):
        d, git = self.repo_with({"data/orders.csv": b"a,b\n"})
        git("commit", "-q", "-m", "x")
        self.assertIn("forbidden file name", self.scan(d)[1])

    def test_forbidden_name_is_caught_whatever_its_case(self):
        d, git = self.repo_with({"Data/orders.csv": b"a,b\n"})
        git("commit", "-q", "-m", "x")
        self.assertIn("forbidden file name", self.scan(d)[1])

    def test_secret_in_text_is_caught_and_never_printed(self):
        fake = "sk-" + "Z" * 24
        d, git = self.repo_with({"cfg.py": f"KEY = '{fake}'\n".encode()})
        git("commit", "-q", "-m", "x")
        code, out = self.scan(d)
        self.assertEqual(code, 1)
        self.assertIn("API key", out)
        self.assertNotIn(fake, out)

    def test_secret_in_utf16_text_is_caught(self):
        fake = "KEY = 'sk-" + "Z" * 24 + "'\n"
        for label, data in {"bom": fake.encode("utf-16"), "le": fake.encode("utf-16-le"),
                            "be": fake.encode("utf-16-be")}.items():
            d, git = self.repo_with({"cfg.txt": data})
            git("commit", "-q", "-m", "x")
            code, out = self.scan(d)
            self.assertEqual(code, 1, label)
            self.assertIn("API key", out, label)
            self.assertNotIn("Z" * 24, out, label)

    def test_binary_with_nul_bytes_is_still_not_read_as_text(self):
        g_text = g.decode_text(bytes(range(256)) * 40)
        self.assertIsNone(g_text)
        self.assertIsNone(g.decode_text(b"\x00" * 100 + b"abc"))

    def test_decode_text_reads_plain_utf8_and_utf16(self):
        self.assertEqual(g.decode_text("héllo".encode("utf-8")), "héllo")
        self.assertEqual(g.decode_text("hello".encode("utf-16-le")), "hello")
        self.assertEqual(g.decode_text("hello".encode("utf-16-be")), "hello")

    def test_secret_in_an_allowed_file_is_still_caught(self):
        d, git = self.repo_with({".env.example": ("API_KEY=sk-" + "Y" * 24 + "\n").encode()})
        git("commit", "-q", "-m", "x")
        self.assertEqual(self.scan(d)[0], 1)

    def test_word_ending_in_sk_is_not_a_secret(self):
        d, git = self.repo_with({"a.md": b"the disk-" + b"x" * 30 + b" is fine\n"})
        git("commit", "-q", "-m", "x")
        self.assertEqual(self.scan(d)[0], 0)

    def test_private_key_header_is_caught(self):
        d, git = self.repo_with({"k.txt": b"-----BEGIN OPENSSH " b"PRIVATE KEY-----\nabc\n"})
        git("commit", "-q", "-m", "x")
        self.assertEqual(self.scan(d)[0], 1)

    def test_staged_mode_sees_only_the_index(self):
        d, git = self.repo_with({"ok.py": b"x = 1\n"})
        git("commit", "-q", "-m", "x")
        write(d, "bad.pdf", b"%PDF-1.7")
        git("add", "bad.pdf")
        code, out = self.scan(d, staged=True)
        self.assertEqual(code, 1)
        self.assertIn("bad.pdf", out)

    def test_range_mode_checks_files_changed_in_range(self):
        d, git = self.repo_with({"ok.py": b"x = 1\n"})
        git("commit", "-q", "-m", "x")
        a = git("rev-parse", "HEAD")
        write(d, "n.bin", b"%PDF-1.7")
        git("add", "-A")
        git("commit", "-q", "-m", "y")
        code, out = self.scan(d, rng=f"{a}..{git('rev-parse', 'HEAD')}")
        self.assertEqual(code, 1)
        self.assertIn("n.bin", out)

    def test_bad_range_is_an_error(self):
        d, git = self.repo_with({"ok.py": b"x = 1\n"})
        git("commit", "-q", "-m", "x")
        for bad in ("HEAD", "a...b", "a..b..c"):
            with self.assertRaises(g.GateError, msg=bad):
                self.scan(d, rng=bad)

    def test_allow_list_permits_a_fictional_fixture(self):
        d, git = self.repo_with({"tests/fixtures/fictional/po1.pdf": b"%PDF-1.4 fictional"})
        git("commit", "-q", "-m", "x")
        self.assertEqual(self.scan(d, c=cfg(scan_allow=["tests/fixtures/fictional/*"]))[0], 0)

    def test_large_file_is_flagged(self):
        d, git = self.repo_with({"big.dat": b"a" * (2 * 1024 * 1024)})
        git("commit", "-q", "-m", "x")
        self.assertIn("larger than", self.scan(d, c=cfg(max_file_mb=1))[1])

    def test_non_ascii_file_names_are_scanned(self):
        d, git = self.repo_with({"docs/caf\u00e9.txt": b"%PDF-1.4"})
        git("commit", "-q", "-m", "x")
        code, out = self.scan(d)
        self.assertEqual(code, 1, out)
        self.assertIn("content is a PDF", out)

    def test_non_ascii_file_names_are_scanned_in_staged_mode(self):
        d, git = self.repo_with({"ok.py": b"x = 1\n"})
        git("commit", "-q", "-m", "x")
        write(d, "naïve.txt", b"%PDF-1.4")
        git("add", "-A")
        code, out = self.scan(d, staged=True)
        self.assertEqual(code, 1, out)


FAKE_KEY = b"-----BEGIN OPENSSH " b"PRIVATE KEY-----\nabc\n"


def add_then_remove_history(d, git):
    """A clean, then B adds a key file, then C removes it (the tip looks like A)."""
    write(d, "a.txt", "1")
    git("add", "-A")
    git("commit", "-q", "-m", "A")
    a = git("rev-parse", "HEAD")
    write(d, "k.txt", FAKE_KEY)
    git("add", "-A")
    git("commit", "-q", "-m", "B")
    b = git("rev-parse", "HEAD")
    git("rm", "-q", "k.txt")
    git("commit", "-q", "-m", "C")
    return a, b, git("rev-parse", "HEAD")


class HistoryScanTests(unittest.TestCase):
    def scan(self, d, **kw):
        lines = []
        code = g.cmd_scan(git_runner(d), CFG, out=lines.append, **kw)
        return code, "\n".join(lines)

    def test_range_catches_a_key_added_then_removed_inside_the_range(self):
        d, git = git_repo(self)
        a, b, c = add_then_remove_history(d, git)
        self.assertEqual(self.scan(d, rev=c)[0], 0)
        code, out = self.scan(d, rng=f"{a}..{c}")
        self.assertEqual(code, 1)
        self.assertIn("k.txt", out)
        self.assertIn(b[:7], out)
        self.assertNotIn("abc", out)

    def test_range_before_the_bad_commit_is_clean(self):
        d, git = git_repo(self)
        a, _, _ = add_then_remove_history(d, git)
        self.assertEqual(self.scan(d, rng=f"{a}..{a}")[0], 0)

    def test_outgoing_without_a_remote_covers_the_whole_history(self):
        d, git = git_repo(self)
        _, _, c = add_then_remove_history(d, git)
        code, out = self.scan(d, outgoing=c)
        self.assertEqual(code, 1)
        self.assertIn("k.txt", out)

    def test_outgoing_skips_commits_a_remote_already_has(self):
        d, git = git_repo(self)
        _, _, c = add_then_remove_history(d, git)
        remote = tempfile.mkdtemp()
        self.addCleanup(remove_tree, remote)
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
        git("remote", "add", "origin", remote)
        git("push", "-q", "origin", f"{c}:refs/heads/main")
        write(d, "later.txt", "ok")
        git("add", "-A")
        git("commit", "-q", "-m", "D")
        self.assertEqual(self.scan(d, outgoing=git("rev-parse", "HEAD"))[0], 0)

    def test_merge_commit_and_first_commit_are_read(self):
        d, git = git_repo(self)
        write(d, "a.txt", "1")
        git("add", "-A")
        git("commit", "-q", "-m", "A")
        git("checkout", "-q", "-b", "side")
        write(d, "n.bin", b"%PDF-1.7")
        git("add", "-A")
        git("commit", "-q", "-m", "S")
        git("checkout", "-q", "main")
        write(d, "b.txt", "2")
        git("add", "-A")
        git("commit", "-q", "-m", "M")
        git("merge", "-q", "--no-ff", "side", "-m", "merge")
        self.assertEqual(self.scan(d, outgoing=git("rev-parse", "HEAD"))[0], 1)


class PathsTests(unittest.TestCase):
    def test_counts_and_warns_about_empty_globs(self):
        d, git = git_repo(self)
        write(d, "AGENTS.md", "x")
        write(d, ".github/workflows/ci.yml", "x")
        git("add", "-A")
        git("commit", "-q", "-m", "x")
        lines = []
        g.cmd_paths(git_runner(d), cfg(protected_paths=["AGENTS.md", ".github/*", "nothing/*"]), out=lines.append)
        text = "\n".join(lines)
        self.assertIn("   1  AGENTS.md", text)
        self.assertIn("   1  .github/*", text)
        self.assertIn("   0  nothing/*", text)
        self.assertIn("match no file today", text)

    def test_non_ascii_protected_names_are_counted(self):
        d, git = git_repo(self)
        write(d, "règles.md", "x")
        git("add", "-A")
        git("commit", "-q", "-m", "x")
        lines = []
        g.cmd_paths(git_runner(d), cfg(protected_paths=["règles.md"]), out=lines.append)
        self.assertIn("   1  règles.md", "\n".join(lines))


class CliTests(unittest.TestCase):
    def test_paths_and_scan_run_from_the_command_line_with_the_default_config_location(self):
        d, git = git_repo(self)
        write(d, ".orchestration/gate.json", json.dumps(RAW))
        write(d, "AGENTS.md", "x")
        git("add", "-A")
        git("commit", "-q", "-m", "x")
        here = os.path.dirname(os.path.abspath(g.__file__))
        for args, want in ((["paths"], 0), (["scan", "--rev", "HEAD"], 0)):
            p = subprocess.run([sys.executable, os.path.join(here, "gate.py")] + args, cwd=d,
                               capture_output=True)
            self.assertEqual(p.returncode, want, p.stderr.decode(errors="replace"))
        write(d, "bad.txt", b"%PDF-1.4")
        git("add", "-A")
        p = subprocess.run([sys.executable, os.path.join(here, "gate.py"), "scan", "--staged"], cwd=d,
                           capture_output=True)
        self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
