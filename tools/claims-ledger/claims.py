#!/usr/bin/env python3
"""claims: track behavioural claims in docs so a changed quantifier sentence always has a matching ledger row.

Standard library only. State is one JSON file (sorted keys, two-space indent), mirroring
tools/class-ledger's convention. Design and scope: docs/claims-ledger-design.md. Protocol source:
rules/leak-classes.md C2 ("any sentence with a condition, a quantifier - always, never, only, same, new -
or a qualifier, written without the input that would make it false").

Commands (the ledger file is always the first argument)
  init    FILE
  add     FILE --slug SLUG --doc PATH --line N --claim TEXT --condition TEXT --condition-pointer PATH:LINE
                --exception TEXT [--states S1,S2,...] --by SIG
  scan    FILE --doc PATH [--since REF]   every quantifier sentence in PATH with no matching row (human
                                          table); --since REF scopes to lines changed since that git ref
                                          (e.g. origin/main) instead of the whole file
  check   FILE --doc PATH [--since REF]   exit 0 if every (scoped) quantifier sentence in PATH has a row,
                                          else refuse (1), naming each one

What it enforces (exit 1 and no write when refused)
  - A claim needs a non-empty --condition and --exception; a claim that restates "it does X" with no
    condition is the exact bug this ledger exists to catch.
  - A slug is added once; `add` on an existing slug is refused.
  - A claim is matched to a doc's sentence by whitespace-normalized TEXT, not by line number - line numbers
    drift whenever something above the claim is edited; the sentence's own wording is what the claim is
    about. `line` is a pointer for a human to find it, never used for matching.

What it cannot do: tell whether a condition or exception is actually true against the code (the reviewer's
job, with condition_pointer as where to look); detect a quantifier sentence outside the fixed word list
below (PROPOSED, tune after running on a real doc change); --since requires `path` to be inside a working
git tree with `ref` reachable, and fails (exit 2) otherwise - there is no non-git fallback.

Exit codes: 0 done, 1 refused by a rule or an unclaimed sentence found, 2 usage, file or format error.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

SCHEMA_VERSION = 1
QUANTIFIER_WORDS = ("always", "never", "only", "same", "new", "every", "any", "guaranteed", "must", "cannot")
_WORD_RE = {w: re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in QUANTIFIER_WORDS}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class Refused(Exception):
    """A protocol rule refused the action (exit 1)."""


class Broken(Exception):
    """Usage, file or format error (exit 2)."""


def normalize(text):
    return " ".join(text.split())


def quantifier_sentences(text):
    """Yield (line_no, sentence) for each sentence containing a quantifier word, 1-indexed by the line it
    starts on. A first cut: splits sentences within a line, not across line breaks - true for the short,
    single-line-per-sentence style this repo's own docs already use; a doc that hard-wraps a sentence
    across lines will miss it here."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        for sentence in _SENTENCE_SPLIT.split(line):
            sentence = sentence.strip()
            if sentence and any(rx.search(sentence) for rx in _WORD_RE.values()):
                yield line_no, sentence


def load(path):
    if not os.path.exists(path):
        raise Broken(f"no such ledger file: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise Broken(f"cannot read {path}: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        raise Broken(f"{path} has schema_version {data.get('schema_version')!r}, expected {SCHEMA_VERSION}")
    return data


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def _today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def cmd_init(path, a):
    if os.path.exists(path):
        raise Refused(f"{path} already exists")
    save(path, {"schema_version": SCHEMA_VERSION, "claims": []})
    return f"initialized {path}"


def cmd_add(path, a):
    data = load(path)
    if any(c["slug"] == a.slug for c in data["claims"]):
        raise Refused(f"slug '{a.slug}' already exists")
    if not a.condition.strip():
        raise Refused("a claim needs a non-empty --condition; a claim without one is the bug this ledger "
                       "exists to catch")
    if not a.exception.strip():
        raise Refused("a claim needs a non-empty --exception (write 'none' if there truly is none, not blank)")
    row = {
        "slug": a.slug,
        "doc": a.doc,
        "line": a.line,
        "claim_text": normalize(a.claim),
        "condition": a.condition,
        "condition_pointer": a.condition_pointer,
        "exception": a.exception,
        "states": [s for s in (a.states or "").split(",") if s],
        "by": a.by,
        "date": _today(),
    }
    data["claims"].append(row)
    save(path, data)
    return f"added {a.slug}"


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(doc, since):
    """Line numbers in `doc`'s CURRENT on-disk content that are new or changed since git ref `since`,
    parsed from `git diff --unified=0`'s hunk headers. Requires `doc` to be inside a git working tree with
    `since` reachable; there is no non-git fallback (raises Broken instead)."""
    doc_dir = os.path.dirname(os.path.abspath(doc)) or "."
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", since, "--", os.path.basename(doc)],
            capture_output=True, text=True, cwd=doc_dir, check=False,
        )
    except OSError as exc:
        raise Broken(f"cannot run git: {exc}") from exc
    if result.returncode != 0:
        raise Broken(f"git diff failed (ref {since!r}, doc {doc!r}): {result.stderr.strip()}")
    lines = set()
    for line in result.stdout.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            if count == 0:
                continue  # a pure deletion at this point; nothing added to scan
            lines.update(range(start, start + count))
    return lines


def _unclaimed(data, doc, only_lines=None):
    if not os.path.exists(doc):
        raise Broken(f"no such doc file: {doc}")
    claimed = {normalize(c["claim_text"]) for c in data["claims"] if c["doc"] == doc}
    with open(doc, encoding="utf-8") as fh:
        text = fh.read()
    found = quantifier_sentences(text)
    if only_lines is not None:
        found = [(ln, s) for ln, s in found if ln in only_lines]
    return [(ln, s) for ln, s in found if normalize(s) not in claimed]


def cmd_scan(path, a):
    data = load(path)
    only = changed_lines(a.doc, a.since) if a.since else None
    unclaimed = _unclaimed(data, a.doc, only)
    scope = f" (changed since {a.since})" if a.since else ""
    if not unclaimed:
        return f"{a.doc}{scope}: every quantifier sentence has a claims-ledger row"
    lines = [f"{a.doc}{scope}: {len(unclaimed)} unclaimed quantifier sentence(s)"]
    lines += [f"  line {ln}: {s}" for ln, s in unclaimed]
    return "\n".join(lines)


def cmd_check(path, a):
    data = load(path)
    only = changed_lines(a.doc, a.since) if a.since else None
    unclaimed = _unclaimed(data, a.doc, only)
    scope = f" changed since {a.since}" if a.since else ""
    if unclaimed:
        lines = [f"{len(unclaimed)} unclaimed quantifier sentence(s) in {a.doc}{scope}"]
        lines += [f"  line {ln}: {s}" for ln, s in unclaimed]
        raise Refused("\n".join(lines))
    return f"{a.doc}{scope}: clean"


def parser():
    p = argparse.ArgumentParser(prog="claims.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def add_cmd(name, fn):
        sp = sub.add_parser(name)
        sp.add_argument("ledger")
        sp.set_defaults(fn=fn)
        return sp

    add_cmd("init", cmd_init)

    sp = add_cmd("add", cmd_add)
    sp.add_argument("--slug", required=True)
    sp.add_argument("--doc", required=True)
    sp.add_argument("--line", required=True, type=int)
    sp.add_argument("--claim", required=True)
    sp.add_argument("--condition", required=True)
    sp.add_argument("--condition-pointer", required=True)
    sp.add_argument("--exception", required=True)
    sp.add_argument("--states", default="")
    sp.add_argument("--by", required=True)

    sp = add_cmd("scan", cmd_scan)
    sp.add_argument("--doc", required=True)
    sp.add_argument("--since", help="a git ref (e.g. origin/main); scope to lines changed since it")

    sp = add_cmd("check", cmd_check)
    sp.add_argument("--doc", required=True)
    sp.add_argument("--since", help="a git ref (e.g. origin/main); scope to lines changed since it")

    return p


def main(argv=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        a = parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        print(a.fn(a.ledger, a), file=out)
        return 0
    except Refused as exc:
        print(f"REFUSED: {exc}", file=err)
        return 1
    except Broken as exc:
        print(f"ERROR: {exc}", file=err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
