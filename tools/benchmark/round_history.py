#!/usr/bin/env python3
"""Describe signed review events in a PR's issue-comment history.

Retrospective text analysis is not a replay of the class ledger. Verdict events
and distinct SHA tokens are observable; review rounds and class reopens
need structured evidence absent from this input and are reported unknown.
Formal GitHub review bodies are outside the issue-comment collection surface.

fetch --repo OWNER/REPO --pr N --out FILE
analyze --comments FILE --reviewer SIGNATURE [--reviewer SIGNATURE ...]
        [--threshold 0.5]

Exit codes: 0 done, 2 usage, file, collection or input-format error.
See tools/benchmark/README.md for the report contract and examples.
"""
import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys

STOPWORDS = frozenset("a an and any are as at be by each every for from in is it its not of on or that the this to "
                      "where which with without".split())
SIGNATURE_RE = re.compile(r"\A\s*\*\*\s*(?P<signer>[^*\n]+?)\s*:?\s*\*\*\s*:?\s*(?P<rest>.*)\Z", re.S)
VERDICT_RE = re.compile(
    r"(?P<verdict>not approved|approved) at\s+"
    r"(?:`(?P<quoted_sha>[0-9a-f]{7,40})`|(?P<sha>[0-9a-f]{7,40})(?![a-z0-9`]))", re.I)
REOPEN_PHRASES = re.compile(r"\b(reopen(ed)?|remains open|still open|back open)\b", re.I)


class Broken(Exception):
    """An expected usage, collection, file or format error."""


def signer_key(text):
    return " ".join(text.strip().rstrip(":").split()).casefold()


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


def jaccard(a, b):
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def timestamp(value):
    if not isinstance(value, str):
        raise Broken("comment created must be a timezone-aware ISO 8601 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Broken("comment created must be a timezone-aware ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise Broken("comment created must include a timezone")
    return parsed


def validate_comments(comments):
    if not isinstance(comments, list):
        raise Broken("comments must be a list")
    for comment in comments:
        if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
            raise Broken("each comment must be an object with a string body")
        timestamp(comment.get("created"))
    return sorted(comments, key=lambda c: timestamp(c["created"]))


def extract_events(comments, reviewers):
    """Parse leading verdicts from an explicit allowlist, not approval authority.

    Refreshed verdicts remain events, without claiming a new round happened.
    Signatures do not authenticate the person or session behind a shared account.
    """
    allowed = {signer_key(r) for r in reviewers}
    if not allowed or "" in allowed:
        raise Broken("provide at least one non-empty reviewer signature")
    events = []
    for c in validate_comments(comments):
        signature = SIGNATURE_RE.match(c["body"])
        if not signature or signer_key(signature["signer"]) not in allowed:
            continue
        verdict = VERDICT_RE.match(signature["rest"])
        if verdict:
            events.append({"index": len(events) + 1,
                           "signer": " ".join(signature["signer"].strip().rstrip(":").split()),
                           "verdict": verdict["verdict"].lower(),
                           "sha": (verdict["sha"] or verdict["quoted_sha"]).lower(),
                           "created": c["created"], "body": c["body"]})
    return events


def report(events, threshold=0.5):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise Broken("threshold must be finite and between 0 and 1")
    first_approval = next((e["index"] for e in events if e["verdict"] == "approved"), None)
    overlap = []
    for i, event in enumerate(events):
        if event["verdict"] != "not approved":
            continue
        candidates = [(jaccard(event["body"], previous["body"]), previous["index"])
                      for previous in events[:i]]
        if candidates:
            score, earlier = max(candidates, key=lambda pair: pair[0])
            if score >= threshold:
                overlap.append({"event": event["index"], "overlaps_with_event": earlier,
                                "score": round(score, 2)})
    return {"verdict_events": len(events), "has_approval_event": first_approval is not None,
            "first_approval_event_index": first_approval,
            "distinct_reviewed_sha_tokens": len({e["sha"] for e in events}),
            "review_rounds": None, "rounds_to_approval": None, "class_reopens": None,
            "comment_text_overlap": overlap,
            "literal_reopen_phrase_events": [e["index"] for e in events if REOPEN_PHRASES.search(e["body"])],
            "limitations": ["Verdict events and distinct SHA tokens do not establish review rounds.",
                            "Abbreviated and full SHA tokens are not resolved to canonical commits.",
                            "An approval event does not establish current-head approval or merge readiness.",
                            "Text overlap and phrase matches do not establish class identity or closure.",
                            "Reviewer signatures are supplied by the caller, not authenticated here."]}


def cmd_fetch(args):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo) or args.pr < 1:
        raise Broken("provide OWNER/REPO and a positive PR number")
    response = subprocess.run(
        ["gh", "api", "--paginate", "--slurp",
         f"repos/{args.repo}/issues/{args.pr}/comments?per_page=100"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    if response.returncode:
        raise Broken(f"gh api failed: {response.stderr.strip()}")
    pages = json.loads(response.stdout)
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise Broken("gh api must return a list of comment pages")
    comments = []
    for page in pages:
        for item in page:
            if not isinstance(item, dict):
                raise Broken("gh api returned an invalid comment")
            comments.append({"id": item.get("id"), "created": item.get("created_at"),
                             "body": item.get("body"), "url": item.get("html_url")})
    comments = validate_comments(comments)
    snapshot = {"schema_version": 1, "repo": args.repo, "pr": args.pr,
                "coverage": "issue_comments_only", "pagination": "all_pages_retrieved",
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "comments": comments}
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"wrote {len(comments)} issue comments to {args.out}; formal review bodies excluded")


def cmd_analyze(args):
    with open(args.comments, encoding="utf-8") as stream:
        snapshot = json.load(stream)
    provenance = {"coverage": "unknown_legacy_snapshot", "pagination": "unknown"}
    if isinstance(snapshot, dict):
        if (snapshot.get("schema_version") != 1 or snapshot.get("coverage") != "issue_comments_only"
                or snapshot.get("pagination") != "all_pages_retrieved"):
            raise Broken("unsupported snapshot schema or collection metadata")
        provenance = {key: snapshot.get(key) for key in ("coverage", "pagination", "repo", "pr", "fetched_at")}
        snapshot = snapshot.get("comments")
    result = report(extract_events(snapshot, args.reviewer), args.threshold)
    result["collection"] = provenance
    result["reviewer_signatures"] = sorted({signer_key(r) for r in args.reviewer})
    print(json.dumps(result, indent=2, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--repo", required=True)
    fetch.add_argument("--pr", required=True, type=int)
    fetch.add_argument("--out", required=True)
    fetch.set_defaults(func=cmd_fetch)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--comments", required=True)
    analyze.add_argument("--reviewer", action="append", required=True, help="eligible signature, without ** markup")
    analyze.add_argument("--threshold", type=float, default=0.5)
    analyze.set_defaults(func=cmd_analyze)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (Broken, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
