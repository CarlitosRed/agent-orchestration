#!/usr/bin/env python3
"""round-history: measure, from a PR's real signed review comments, how many rounds were spent and how many
of those rounds raised a class that overlaps an earlier round's class - the instance-chasing pattern the
convergence loop (docs/convergence-loop.md, F3) was built to stop. F3's own report named this measurement
PROPOSED and never built it (docs/f3-report.md: "Rounds actually drop - PROPOSED; measure on 2 or 3
instance-chasing PRs"). This tool is that measurement.

Standard library only. Retrospective analysis of comments that already happened - it cannot re-run a review
with the class ledger enforcing anything; it only reads the record left behind by a loop that did NOT have
the ledger yet, and reports which of those rounds a ledger-enforced loop would likely have caught as a
reopen instead of a fresh-looking finding. Label this estimate honestly in any report
(templates/benchmark-checklist.md, "end-to-end relevance"): it is a retrospective read of real history, not
a measured replay through the actual enforcing tool.

Commands
  fetch    --repo OWNER/REPO --pr N --out FILE          pull a PR's issue comments via `gh api`, write JSON
  analyze  --comments FILE [--threshold 0.5]             parse rounds, flag likely-recurring classes, print report

Exit codes: 0 done, 2 usage or file error. (No "refused" state - this tool only reads and reports.)
"""
import argparse
import json
import re
import subprocess
import sys

# Same Jaccard threshold and stopword list class-ledger uses for its own lookalike check
# (tools/class-ledger/ledger.py) - reused rather than re-tuned, so a flag here means the same thing a
# ledger-enforced round would have meant.
SIMILARITY_THRESHOLD = 0.5
STOPWORDS = frozenset("a an and any are as at be by each every for from in is it its not of on or that the this to "
                      "where which with without".split())
VERDICT_RE = re.compile(
    r"\*\*(?P<signer>[^*\n]+)\*\*:?\s*\n?\s*(?P<verdict>Approved|Not approved) at (?P<sha>[0-9a-fA-F]{7,40})"
)
REOPEN_PHRASES = re.compile(r"\b(reopen(ed)?|remains open|still open|back open)\b", re.IGNORECASE)


class Broken(Exception):
    """Usage, file or format error (exit 2)."""


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


def jaccard(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def extract_rounds(comments):
    """comments: list of {author, created, body}, oldest first (as `gh api` returns PR issue comments).
    A round is any comment whose body carries a signed verdict (R22: signature, then "Approved"/"Not
    approved at <sha>" as the first words after it) - builder progress comments and the owner's "go" carry
    no such verdict and are not rounds. Returns rounds in order: {index, signer, verdict, sha, created, body}."""
    rounds = []
    for c in comments:
        m = VERDICT_RE.search(c["body"])
        if not m:
            continue
        rounds.append({
            "index": len(rounds) + 1,
            "signer": m.group("signer").strip(),
            "verdict": m.group("verdict"),
            "sha": m.group("sha"),
            "created": c.get("created"),
            "body": c["body"],
        })
    return rounds


def flag_recurring(rounds, threshold=SIMILARITY_THRESHOLD):
    """For each 'Not approved' round, compare its body against every EARLIER round's body (any verdict) and
    flag pairs at or above threshold - the same signal class-ledger's own close-class lookalike check uses.
    Returns flagged pairs, round numbers 1-based, each pair reported once (against its highest-scoring
    earlier round, not every earlier round it happens to clear the bar against)."""
    flags = []
    for i, r in enumerate(rounds):
        if r["verdict"] != "Not approved":
            continue
        best = None
        for j in range(i):
            score = jaccard(r["body"], rounds[j]["body"])
            if score >= threshold and (best is None or score > best["score"]):
                best = {"round": r["index"], "overlaps_with_round": rounds[j]["index"], "score": round(score, 2)}
        if best:
            flags.append(best)
    return flags


def flag_explicit_reopen_language(rounds):
    return [r["index"] for r in rounds if REOPEN_PHRASES.search(r["body"])]


def report(rounds, threshold=SIMILARITY_THRESHOLD):
    approved = [r for r in rounds if r["verdict"] == "Approved"]
    recurring = flag_recurring(rounds, threshold)
    not_approved_rounds = [r["index"] for r in rounds if r["verdict"] == "Not approved"]
    likely_avoidable = sorted({f["round"] for f in recurring} |
                               set(flag_explicit_reopen_language(rounds)) & set(not_approved_rounds))
    return {
        "total_rounds": len(rounds),
        "rounds_to_approval": approved[0]["index"] if approved else None,
        "approved": bool(approved),
        "recurring_class_flags": recurring,
        "explicit_reopen_language_in_rounds": flag_explicit_reopen_language(rounds),
        "rounds_a_ledger_likely_catches_as_reopen": likely_avoidable,
    }


def cmd_fetch(args):
    out = subprocess.run(
        ["gh", "api", f"repos/{args.repo}/issues/{args.pr}/comments",
         "--jq", "[.[] | {author: .user.login, created: .created_at, body: .body}]"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise Broken(f"gh api failed: {out.stderr.strip()}")
    try:
        comments = json.loads(out.stdout)
    except json.JSONDecodeError as e:
        raise Broken(f"gh api returned non-JSON output: {e}")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(comments, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {len(comments)} comments to {args.out}")


def cmd_analyze(args):
    with open(args.comments, encoding="utf-8") as f:
        comments = json.load(f)
    rounds = extract_rounds(comments)
    result = report(rounds, args.threshold)
    print(json.dumps(result, indent=2, sort_keys=True))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("fetch")
    pf.add_argument("--repo", required=True)
    pf.add_argument("--pr", required=True, type=int)
    pf.add_argument("--out", required=True)
    pf.set_defaults(func=cmd_fetch)

    pa = sub.add_parser("analyze")
    pa.add_argument("--comments", required=True)
    pa.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD)
    pa.set_defaults(func=cmd_analyze)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except Broken as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
