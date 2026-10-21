#!/usr/bin/env python3
"""Build and post a relayed review comment, refusing to send one whose finding text is empty (leak L16).

build: signature, verdict first (R22), then the reviewer's text quoted unchanged. Refuses an empty review file,
       a verdict sha that is not 40 hex characters, and a body with a byte-order mark.
post:  build, post with `gh pr comment --body-file`, then read that comment back by its URL and fail unless it holds
       the built body (a post that dropped text is caught while the PR is still open, not minutes later).
--as-account LOGIN: post as that GitHub account (a vendor's own login) instead of the session's. The token is read
       with `gh auth token --user LOGIN` (from --token-config-dir, or RELAY_TOKEN_CONFIG_DIR, when the login lives in
       another gh config folder) and goes into the environment of the gh calls of this one run only. Before posting it
       checks the token belongs to LOGIN and that LOGIN is not the pull request's author; after posting it checks the
       comment's author is LOGIN.
Review files from Windows PowerShell 5.1 `Tee-Object` are UTF-16; this reads UTF-8 or UTF-16 with or without a mark.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_GATE_DIR = str(Path(__file__).resolve().parent.parent / "gate")
if _GATE_DIR not in sys.path:
    sys.path.insert(0, _GATE_DIR)
import gate  # tools/gate/gate.py: the single source of truth for which --role names gate.py will ever recognize

SHA = re.compile(r"^[0-9a-f]{40}$")
VERDICTS = {"approved": "Approved at", "not-approved": "Not approved at"}


class RelayError(Exception):
    pass


def read_text(path):
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    elif b"\x00" in data:
        text = data.decode("utf-16-le" if data[1::2].count(0) >= data[0::2].count(0) else "utf-16-be", errors="replace")
    else:
        text = data.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")


def quote(text):
    return "\n".join(("> " + line).rstrip() if line.strip() else ">" for line in text.strip("\n").split("\n"))


def known_roles():
    """The signer roles the current project's own gate config recognizes, or None if no config is found (nothing
    to check --role against). A role posted outside this set is text gate.py will flag as 'not a known signer'
    and ignore — the review would never count, with no error at post time to say so."""
    path = gate.default_config_path()
    if not os.path.isfile(path):
        return None
    try:
        return set(gate.load_config(path).role_by_key)
    except gate.GateError:
        return None


def check_role(role, roles=None):
    """Refuse a --role gate.py would not recognize as a signer. roles=None looks up the project's own gate
    config; pass an explicit set (of gate._key-normalized names) to check against something else, e.g. in tests."""
    if roles is None:
        roles = known_roles()
    if roles is not None and gate._key(role) not in roles:
        raise RelayError(f"role {role!r} is not a signer role in this project's gate config "
                          "(.orchestration/gate.json): gate.py would post it but never count it as a review")


def build(role, vendor, verdict, sha, review_text, relayer, note_text=""):
    if verdict not in VERDICTS:
        raise RelayError(f"verdict must be one of {sorted(VERDICTS)}")
    if not SHA.match(sha):
        raise RelayError("sha must be the full 40-character lowercase hex head commit")
    if not review_text.strip():
        raise RelayError("review text is empty: refusing to post a relay with no finding text")
    parts = [
        f"**{role} · {vendor}:** {VERDICTS[verdict]} {sha}",
        f"Relayed by {relayer}. The reviewer's text follows unchanged; the verdict line is the relayer's mapping of its "
        "findings, not the reviewer's own words.",
        quote(review_text),
    ]
    if note_text.strip():
        parts.append(note_text.strip())
    body = "\n\n".join(parts) + "\n"
    if body.startswith("﻿"):
        raise RelayError("body starts with a byte-order mark")
    return body


def run_gh(args, stdin=None, env=None):
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, encoding="utf-8", env=env)
    if done.returncode != 0:
        raise RelayError(f"gh {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout


def gh_as(account, config_dir=None, runner=run_gh):
    """A gh callable that runs as `account`. The token is looked up with `gh auth token --user` and kept in the
    environment of these calls only; a token that does not belong to `account` is refused."""
    lookup = {**os.environ, "GH_CONFIG_DIR": config_dir} if config_dir else None
    if lookup is not None:
        lookup.pop("GH_TOKEN", None)
    token = runner(["auth", "token", "--user", account], env=lookup).strip()
    if not token:
        raise RelayError(f"no token found for {account}: sign it in with `gh auth login` first")
    env = {**os.environ, "GH_TOKEN": token}

    def gh(args, stdin=None):
        return runner(args, stdin=stdin, env=env)

    login = gh(["api", "user", "--jq", ".login"]).strip()
    if login.lower() != account.lower():
        raise RelayError(f"the token for {account} belongs to {login or 'nobody'}; refusing to post")
    return gh


def post(pr, body, gh=run_gh, repo=None, expect_author=None):
    scope = ["--repo", repo] if repo else []
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8", newline="\n") as handle:
        handle.write(body)
        path = handle.name
    try:
        printed = gh(["pr", "comment", str(pr), *scope, "--body-file", path]).strip().splitlines()
        url = printed[-1].strip() if printed else ""
        out = gh(["pr", "view", str(pr), *scope, "--json", "comments"])
    finally:
        Path(path).unlink(missing_ok=True)
    mine = [c for c in json.loads(out).get("comments", []) if url and c.get("url") == url]
    if not mine:
        raise RelayError(f"posted, but the new comment ({url or 'no url printed'}) is not visible on the PR")
    if expect_author:
        author = (mine[0].get("author") or {}).get("login", "")
        if author.lower() != expect_author.lower():
            raise RelayError(f"comment {url} was posted by {author or 'an unknown account'}, not {expect_author}")
    if mine[0].get("body", "").strip() != body.strip():
        raise RelayError(f"comment {url} does not match what was built: fix it by editing that comment")
    return url


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "post"):
        sp = sub.add_parser(name)
        sp.add_argument("--role", default="Independent Reviewer")
        sp.add_argument("--vendor", required=True)
        sp.add_argument("--verdict", required=True, choices=sorted(VERDICTS))
        sp.add_argument("--sha", required=True)
        sp.add_argument("--review-file", required=True)
        sp.add_argument("--relayer", required=True, help="who relays, for example 'the Framework Orchestrator (Claude)'")
        sp.add_argument("--note-file", help="optional text added after the quote, such as the relayer's own note")
        if name == "build":
            sp.add_argument("--out", help="write the body here instead of stdout")
        else:
            sp.add_argument("pr", type=int)
            sp.add_argument("--repo")
            sp.add_argument("--as-account", help="post as this GitHub login (the vendor's own account)")
            sp.add_argument("--token-config-dir", default=os.environ.get("RELAY_TOKEN_CONFIG_DIR"),
                            help="gh config folder that holds the --as-account login (default: $RELAY_TOKEN_CONFIG_DIR)")
    args = ap.parse_args(argv)
    try:
        check_role(args.role)
        note = read_text(args.note_file) if args.note_file else ""
        body = build(args.role, args.vendor, args.verdict, args.sha, read_text(args.review_file), args.relayer, note)
        if args.cmd == "build":
            if args.out:
                Path(args.out).write_text(body, encoding="utf-8", newline="\n")
            else:
                sys.stdout.write(body)
        else:
            gh = run_gh
            if args.as_account:
                gh = gh_as(args.as_account, args.token_config_dir)
                scope = ["--repo", args.repo] if args.repo else []
                author = gh(["pr", "view", str(args.pr), *scope, "--json", "author", "--jq", ".author.login"]).strip()
                if author.lower() == args.as_account.lower():
                    raise RelayError(f"{args.as_account} is the author of PR {args.pr}; a review from the author's "
                                     "own account is not independent")
            print(f"posted and read back: {post(args.pr, body, gh=gh, repo=args.repo, expect_author=args.as_account)}")
    except (RelayError, OSError) as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
