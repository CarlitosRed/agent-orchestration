#!/usr/bin/env python3
"""Build and post a relayed review comment, refusing to send one whose finding text is empty (leak L16).

build: signature, verdict first (R22), then the reviewer's text quoted unchanged. Refuses an empty review file,
       a verdict sha that is not 40 hex characters, and a body with a byte-order mark.
post:  build, post with `gh pr comment --body-file`, then read the newest comment back and fail unless it holds
       the built body (a post that dropped text is caught while the PR is still open, not minutes later).
Review files from Windows PowerShell 5.1 `Tee-Object` are UTF-16; this reads UTF-8 or UTF-16 with or without a mark.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
VERDICTS = {"approved": "Approved at", "not-approved": "Not approved at"}


class RelayError(Exception):
    pass


def read_text(path):
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    elif b"\x00" in data[:4096]:
        text = data.decode("utf-16-le" if data[1:2] == b"\x00" else "utf-16-be", errors="replace")
    else:
        text = data.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")


def quote(text):
    return "\n".join(("> " + line).rstrip() if line.strip() else ">" for line in text.strip("\n").split("\n"))


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


def run_gh(args, stdin=None):
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise RelayError(f"gh {' '.join(args[:2])} failed: {done.stderr.strip()}")
    return done.stdout


def post(pr, body, gh=run_gh, repo=None):
    scope = ["--repo", repo] if repo else []
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8", newline="\n") as handle:
        handle.write(body)
        path = handle.name
    try:
        gh(["pr", "comment", str(pr), *scope, "--body-file", path])
        out = gh(["pr", "view", str(pr), *scope, "--json", "comments"])
    finally:
        Path(path).unlink(missing_ok=True)
    comments = json.loads(out).get("comments", [])
    if not comments:
        raise RelayError("posted, but no comments are visible on the PR")
    if comments[-1].get("body", "").strip() != body.strip():
        raise RelayError("the newest comment does not match what was built: fix it by editing that comment")
    return len(comments)


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
    args = ap.parse_args(argv)
    try:
        note = read_text(args.note_file) if args.note_file else ""
        body = build(args.role, args.vendor, args.verdict, args.sha, read_text(args.review_file), args.relayer, note)
        if args.cmd == "build":
            if args.out:
                Path(args.out).write_text(body, encoding="utf-8", newline="\n")
            else:
                sys.stdout.write(body)
        else:
            count = post(args.pr, body, repo=args.repo)
            print(f"posted and read back; PR now has {count} comments")
    except (RelayError, OSError) as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
