#!/usr/bin/env python3
"""ledger: track a pull request's review findings as defect CLASSES across rounds.

Standard library only. State is one JSON file per PR (sorted keys, two-space indent) so it diffs cleanly and a
project can commit it as an audit trail. Protocol: docs/convergence-loop.md.

Commands (the ledger file is always the first argument)
  init         FILE --pr ID [--budget 3] [--head SHA]
  new-round    FILE --head SHA [--escalation-sweep PTR] [--owner-decision PTR]
  add-finding  FILE --class SLUG --by SIG --severity P1|P2|P3 --file PATH:LINE --counterexample TEXT --repro CMD
               [--generator TEXT] [--new-reason TEXT] [--distinct-from SLUG ...]
  sort         FILE SLUG --bucket act|consider|noted|dismissed --by SIG [--reason TEXT]
  close-class  FILE SLUG --by SIG --evidence PTR --sweep-cmd CMD [--sweep-output FILE]
  verify-class FILE SLUG --by SIG --generator-used TEXT --evidence PTR
  merge-classes FILE SRC --into DST --by SIG --reason TEXT
  status       FILE                 short human table
  report       FILE [--json]        metrics (JSON) plus the table

What it enforces (exit 1 and no write when refused)
  - A finding on a CLOSED class reopens it (a failed builder sweep) and counts in reopen_count. It is never a new class.
  - A reopened class can only be closed again by a signature that has not closed it before (the different-agent
    whole-class sweep).
  - A new class needs a one-line generator. From round 2 on it also needs --new-reason, and a generator that looks
    like an existing class's generator, or a counterexample at a location already recorded, is refused unless the
    reviewer names that class in --distinct-from (the decision is recorded for the Orchestrator to check).
  - Closing needs an evidence pointer and the sweep command; a sweep output file is hashed into the record.
  - verify-class refuses a generator identical to the one the class was closed with (re-sweep with a DIFFERENT one).
  - new-round refuses while an open class is unsorted or in "consider"; past the budget it needs a pointer to the
    different-agent sweep (one final round), and after that a pointer to the owner's scope decision.
What it cannot do: run sweeps, judge whether a finding really belongs to the class the reviewer names, or prove who
typed a signature. See docs/f3-report.md.

Exit codes: 0 done, 1 refused by a rule, 2 usage, file or format error.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile

SCHEMA_VERSION = 1
SEVERITIES = ("P1", "P2", "P3")
BUCKETS = ("unsorted", "act", "consider", "noted", "dismissed")
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SIMILARITY_THRESHOLD = 0.5   # Jaccard on generator words; PROPOSED, tune on real ledgers
STOPWORDS = frozenset("a an and any are as at be by each every for from in is it its not of on or that the this to "
                      "where which with without".split())
OPEN_STATES = ("open", "reopened")


class Refused(Exception):
    """A protocol rule refused the action (exit 1)."""


class Broken(Exception):
    """Usage, file or format error (exit 2)."""


# ---------------------------------------------------------------- storage

def load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise Broken(f"no ledger at {path}; run init first")
    except (OSError, ValueError) as exc:
        raise Broken(f"cannot read ledger {path}: {exc}")
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise Broken(f"{path} is not a schema_version {SCHEMA_VERSION} ledger")
    return data


def save(path, data):
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".ledger-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------- helpers

def vendor_of(sig):
    """'Independent Reviewer · Alpha' -> 'alpha'. A signature without the middle dot is its own vendor."""
    parts = sig.split("·")
    return " ".join(parts[-1].split()).lower()


def norm(text):
    return " ".join(text.lower().split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


def jaccard(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def need(value, name):
    if value is None or not str(value).strip():
        raise Broken(f"{name} is required and cannot be empty")
    return str(value).strip()


def get_class(data, slug):
    cls = data["classes"].get(slug)
    if cls is None:
        raise Refused(f"unknown class '{slug}'")
    if cls["state"] == "merged":
        raise Refused(f"class '{slug}' was merged into '{cls['merged_into']}'; use that class")
    return cls


def event(cls, data, kind, by, **extra):
    row = {"round": data["round"], "kind": kind, "by": by}
    row.update(extra)
    cls["history"].append(row)


# ---------------------------------------------------------------- commands

def cmd_init(path, a):
    if os.path.exists(path):
        raise Refused(f"{path} already exists; a ledger is never re-initialised")
    if a.budget < 1:
        raise Broken("--budget must be at least 1")
    data = {
        "schema_version": SCHEMA_VERSION,
        "pr": need(a.pr, "--pr"),
        "budget": a.budget,
        "round": 1,
        "rounds": [{"n": 1, "head": a.head or ""}],
        "classes": {},
        "findings": [],
    }
    save(path, data)
    return f"ledger for PR {data['pr']} created, round 1, budget {a.budget}"


def cmd_new_round(path, a):
    data = load(path)
    unsorted = [s for s, c in sorted(data["classes"].items())
                if c["state"] in OPEN_STATES and c["bucket"] in ("unsorted", "consider")]
    if unsorted:
        raise Refused("sort before the next round (act, noted or dismissed): " + ", ".join(unsorted))
    n = data["round"] + 1
    budget = data["budget"]
    row = {"n": n, "head": need(a.head, "--head")}
    if n == budget + 1:
        if not a.escalation_sweep:
            raise Refused(f"round {n} is past the budget of {budget}: give --escalation-sweep <pointer to the "
                          "whole-class sweep by a different agent>; this will be the final round")
        row["escalation_sweep"] = a.escalation_sweep
    elif n > budget + 1:
        if not a.owner_decision:
            raise Refused(f"round {n}: the final round was {budget + 1}; only the owner's scope decision "
                          "(--owner-decision <pointer>) opens another")
        row["owner_decision"] = a.owner_decision
    data["round"] = n
    data["rounds"].append(row)
    save(path, data)
    return f"round {n} started at {row['head']}"


def cmd_add_finding(path, a):
    data = load(path)
    slug = need(a.cls, "--class")
    if not SLUG.fullmatch(slug):
        raise Broken("--class must be a lowercase slug: letters, digits, dashes, at most 64")
    by = need(a.by, "--by")
    if a.severity not in SEVERITIES:
        raise Broken("--severity must be P1, P2 or P3")
    finding = {
        "id": f"F{len(data['findings']) + 1}",
        "round": data["round"],
        "class": slug,
        "by": by,
        "vendor": vendor_of(by),
        "severity": a.severity,
        "file": need(a.file, "--file"),
        "counterexample": need(a.counterexample, "--counterexample"),
        "repro": need(a.repro, "--repro"),
    }
    cls = data["classes"].get(slug)
    if cls is not None and cls["state"] == "merged":
        raise Refused(f"class '{slug}' was merged into '{cls['merged_into']}'; file the finding there")
    if cls is None:
        msg = _new_class(data, slug, finding, a)
    else:
        msg = _instance(data, cls, finding)
    data["findings"].append(finding)
    save(path, data)
    return msg


def _new_class(data, slug, finding, a):
    generator = need(a.generator, "--generator (a new class needs its one-line generator)")
    distinct = set(a.distinct_from or [])
    for name in distinct:
        if name not in data["classes"]:
            raise Broken(f"--distinct-from names unknown class '{name}'")
    if data["round"] > 1:
        need(a.new_reason, "--new-reason (from round 2 on, say why this is not an instance of a known class)")
    lookalikes = []
    for other_slug, other in sorted(data["classes"].items()):
        if other["state"] == "merged" or other_slug in distinct:
            continue
        score = jaccard(generator, other["generator"])
        same_place = any(f["file"] == finding["file"] for f in data["findings"] if f["class"] == other_slug)
        if score >= SIMILARITY_THRESHOLD or same_place:
            why = f"generator overlap {score:.2f}" if score >= SIMILARITY_THRESHOLD else "same file:line"
            lookalikes.append(f"{other_slug} ({why}, state {other['state']})")
    if lookalikes:
        raise Refused("looks like a known class: " + "; ".join(lookalikes) + ". File it under that class, or "
                      "pass --distinct-from <class> with --new-reason so the Orchestrator can check the call")
    finding["kind"] = "new-class"
    data["classes"][slug] = {
        "slug": slug,
        "generator": generator,
        "state": "open",
        "bucket": "unsorted",
        "opened_round": data["round"],
        "opened_by": finding["by"],
        "raised_by_vendors": [finding["vendor"]],
        "severity": finding["severity"],
        "reopen_count": 0,
        "closers": [],
        "closures": [],
        "verifications": [],
        "new_reason": (a.new_reason or "").strip(),
        "distinct_from": sorted(distinct),
        "history": [],
    }
    event(data["classes"][slug], data, "opened", finding["by"], finding=finding["id"])
    return f"{finding['id']}: new class '{slug}' opened in round {data['round']}"


def _instance(data, cls, finding):
    if finding["vendor"] not in cls["raised_by_vendors"]:
        cls["raised_by_vendors"].append(finding["vendor"])
    if SEVERITIES.index(finding["severity"]) < SEVERITIES.index(cls["severity"]):
        cls["severity"] = finding["severity"]
    # Same round only: the same instance raised again in a LATER round, after a close, is a reopen.
    twin = next((f for f in data["findings"] if f["class"] == cls["slug"] and f["kind"] != "duplicate"
                 and f["round"] == data["round"] and f["file"] == finding["file"] and norm(f["counterexample"]) == norm(finding["counterexample"])),
                None)
    if twin is not None:
        # Same instance raised again (typically the other vendor in a parallel round 1): adds a vendor, not a count.
        finding["kind"] = "duplicate"
        finding["duplicate_of"] = twin["id"]
        event(cls, data, "duplicate", finding["by"], finding=finding["id"], of=twin["id"])
        return f"{finding['id']}: same instance as {twin['id']} in class '{cls['slug']}' (vendor recorded, not counted)"
    if cls["state"] == "closed":
        cls["state"] = "reopened"
        cls["reopen_count"] += 1
        finding["kind"] = "reopen"
        event(cls, data, "reopened", finding["by"], finding=finding["id"],
              note="instance after closure: the builder's sweep missed it")
        return (f"{finding['id']}: REOPEN of closed class '{cls['slug']}' (reopen #{cls['reopen_count']}); "
                f"failed sweep by {', '.join(cls['closers'])}; the next close must come from a different agent")
    finding["kind"] = "instance"
    if cls["state"] == "dismissed":
        event(cls, data, "finding-on-dismissed", finding["by"], finding=finding["id"])
        return f"{finding['id']}: instance of DISMISSED class '{cls['slug']}' recorded; re-sort it if it matters"
    event(cls, data, "instance", finding["by"], finding=finding["id"])
    return f"{finding['id']}: instance of {cls['state']} class '{cls['slug']}'"


def cmd_sort(path, a):
    data = load(path)
    cls = get_class(data, a.slug)
    if a.bucket not in BUCKETS[1:]:
        raise Broken("--bucket must be act, consider, noted or dismissed")
    if a.bucket == "dismissed" and not (a.reason or "").strip():
        raise Broken("dismissing a class needs --reason")
    if cls["state"] == "closed":
        raise Refused(f"class '{a.slug}' is closed; nothing to sort")
    cls["bucket"] = a.bucket
    if a.bucket == "dismissed":
        cls["state"] = "dismissed"
    elif cls["state"] == "dismissed":
        cls["state"] = "open"
    event(cls, data, "sorted", need(a.by, "--by"), bucket=a.bucket, reason=(a.reason or "").strip())
    save(path, data)
    return f"class '{a.slug}' -> {a.bucket}"


def cmd_close(path, a):
    data = load(path)
    cls = get_class(data, a.slug)
    by = need(a.by, "--by")
    if cls["state"] not in OPEN_STATES:
        raise Refused(f"class '{a.slug}' is {cls['state']}; only an open or reopened class can be closed")
    if cls["state"] == "reopened" and norm(by) in {norm(c) for c in cls["closers"]}:
        raise Refused(f"class '{a.slug}' was reopened after {by} closed it; a DIFFERENT agent must do the "
                      "whole-class sweep and close it")
    closure = {
        "round": data["round"],
        "by": by,
        "evidence": need(a.evidence, "--evidence"),
        "sweep_cmd": need(a.sweep_cmd, "--sweep-cmd"),
        "generator": cls["generator"],
    }
    if a.sweep_output:
        try:
            with open(a.sweep_output, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise Broken(f"cannot read --sweep-output: {exc}")
        closure["sweep_output"] = {"path": a.sweep_output.replace("\\", "/"),
                                   "sha256": hashlib.sha256(raw).hexdigest(),
                                   "lines": raw.count(b"\n")}
    cls["closures"].append(closure)
    if by not in cls["closers"]:
        cls["closers"].append(by)
    cls["state"] = "closed"
    event(cls, data, "closed", by, evidence=closure["evidence"])
    save(path, data)
    return f"class '{a.slug}' closed by {by} in round {data['round']}"


def cmd_verify(path, a):
    data = load(path)
    cls = get_class(data, a.slug)
    if cls["state"] != "closed":
        raise Refused(f"class '{a.slug}' is {cls['state']}; only a closed class is verified")
    used = need(a.generator_used, "--generator-used")
    if norm(used) == norm(cls["generator"]):
        raise Refused("that is the generator the class was closed with; re-sweep with a DIFFERENT vocabulary "
                      "or generator")
    row = {"round": data["round"], "by": need(a.by, "--by"), "generator_used": used,
           "evidence": need(a.evidence, "--evidence")}
    cls["verifications"].append(row)
    event(cls, data, "verified", row["by"], generator_used=used)
    save(path, data)
    return f"class '{a.slug}' verified clean by {row['by']} with a different generator"


def cmd_merge(path, a):
    data = load(path)
    src, dst = get_class(data, a.slug), get_class(data, a.into)
    if src is dst:
        raise Broken("cannot merge a class into itself")
    reason = need(a.reason, "--reason")
    by = need(a.by, "--by")
    for v in src["raised_by_vendors"]:
        if v not in dst["raised_by_vendors"]:
            dst["raised_by_vendors"].append(v)
    if SEVERITIES.index(src["severity"]) < SEVERITIES.index(dst["severity"]):
        dst["severity"] = src["severity"]
    for f in data["findings"]:
        if f["class"] == a.slug:
            f["class"] = a.into
            f["merged_from"] = a.slug
    src["state"] = "merged"
    src["merged_into"] = a.into
    event(src, data, "merged-into", by, into=a.into, reason=reason)
    event(dst, data, "absorbed", by, source=a.slug, reason=reason)
    save(path, data)
    return f"class '{a.slug}' merged into '{a.into}'"


# ---------------------------------------------------------------- metrics

def count_instances(data, slug):
    return sum(1 for f in data["findings"] if f["class"] == slug and f["kind"] != "duplicate")


def metrics(data):
    live = {s: c for s, c in data["classes"].items() if c["state"] != "merged"}
    per_round = {}
    for r in data["rounds"]:
        per_round[str(r["n"])] = {"findings": 0, "new_classes": 0, "instances": 0, "reopens": 0, "duplicates": 0}
    for f in data["findings"]:
        row = per_round[str(f["round"])]
        row["findings"] += 1
        row[{"new-class": "new_classes", "instance": "instances", "reopen": "reopens",
             "duplicate": "duplicates"}[f["kind"]]] += 1
    blocking = sorted(s for s, c in live.items()
                      if c["state"] in OPEN_STATES and c["severity"] in ("P1", "P2")
                      and c["bucket"] in ("unsorted", "act", "consider"))
    last = per_round[str(data["round"])]
    escalations = sorted(s for s, c in live.items() if c["state"] == "reopened")
    late_new = sorted(s for s, c in live.items() if c["opened_round"] > 1)
    return {
        "pr": data["pr"],
        "round": data["round"],
        "budget": data["budget"],
        "over_budget": data["round"] > data["budget"],
        "classes_opened": len(live),
        "classes_closed": sum(1 for c in live.values() if c["state"] == "closed"),
        "classes_open": sum(1 for c in live.values() if c["state"] in OPEN_STATES),
        "classes_dismissed": sum(1 for c in live.values() if c["state"] == "dismissed"),
        "classes_merged": len(data["classes"]) - len(live),
        "reopen_count": sum(c["reopen_count"] for c in live.values()),
        "reopened_classes": sorted(s for s, c in live.items() if c["reopen_count"]),
        "instances_per_class": {s: count_instances(data, s) for s in sorted(live)},
        "per_round": per_round,
        "both_vendor_classes": sorted(s for s, c in live.items() if len(c["raised_by_vendors"]) > 1),
        "buckets": {b: sum(1 for c in live.values() if c["bucket"] == b) for b in BUCKETS},
        "needs_different_agent": escalations,
        "new_classes_after_round_1": [{"class": s, "round": live[s]["opened_round"],
                                       "reason": live[s]["new_reason"],
                                       "distinct_from": live[s]["distinct_from"]} for s in late_new],
        "blocking_classes": blocking,
        "exit_ready": not blocking and last["new_classes"] == 0 and last["reopens"] == 0,
    }


def table(data):
    rows = [("class", "state", "sev", "bucket", "inst", "reopen", "vendors", "opened")]
    for s, c in sorted(data["classes"].items()):
        n = count_instances(data, s)
        state = c["state"] + (f"->{c['merged_into']}" if c["state"] == "merged" else "")
        rows.append((s, state, c["severity"], c["bucket"], str(n), str(c["reopen_count"]),
                     "+".join(c["raised_by_vendors"]), f"r{c['opened_round']}"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(v.ljust(widths[i]) for i, v in enumerate(r)).rstrip() for r in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def summary(m):
    pr = ", ".join(f"r{k}: {v['new_classes']} new / {v['instances']} inst / {v['reopens']} reopen"
                   for k, v in m["per_round"].items())
    out = [f"PR {m['pr']}  round {m['round']} of budget {m['budget']}"
           + ("  OVER BUDGET" if m["over_budget"] else ""),
           f"classes: {m['classes_opened']} opened, {m['classes_closed']} closed, {m['classes_open']} open, "
           f"{m['classes_dismissed']} dismissed; reopens: {m['reopen_count']}",
           f"per round: {pr}"]
    if m["needs_different_agent"]:
        out.append("NEEDS A DIFFERENT AGENT'S WHOLE-CLASS SWEEP: " + ", ".join(m["needs_different_agent"]))
    if m["new_classes_after_round_1"]:
        out.append("new classes after round 1 (Orchestrator: confirm each is not a renamed known class): "
                   + ", ".join(r["class"] for r in m["new_classes_after_round_1"]))
    out.append("exit ready: " + ("yes" if m["exit_ready"] else
                                 "no (blocking: " + (", ".join(m["blocking_classes"]) or "none")
                                 + "; last round must add no new class and no reopen)"))
    return "\n".join(out)


def cmd_status(path, a):
    data = load(path)
    return table(data) + "\n\n" + summary(metrics(data))


def cmd_report(path, a):
    data = load(path)
    m = metrics(data)
    text = json.dumps(m, indent=2, sort_keys=True)
    if a.json:
        return text
    return text + "\n\n" + table(data) + "\n\n" + summary(m)


# ---------------------------------------------------------------- CLI

def parser():
    p = argparse.ArgumentParser(prog="ledger.py", description="Class ledger for PR review rounds.")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, fn, with_slug=False):
        sp = sub.add_parser(name)
        sp.add_argument("ledger")
        if with_slug:
            sp.add_argument("slug")
        sp.set_defaults(fn=fn)
        return sp

    sp = add("init", cmd_init)
    sp.add_argument("--pr", required=True)
    sp.add_argument("--budget", type=int, default=3)
    sp.add_argument("--head")
    sp = add("new-round", cmd_new_round)
    sp.add_argument("--head", required=True)
    sp.add_argument("--escalation-sweep")
    sp.add_argument("--owner-decision")
    sp = add("add-finding", cmd_add_finding)
    sp.add_argument("--class", dest="cls", required=True)
    sp.add_argument("--by", required=True)
    sp.add_argument("--severity", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--counterexample", required=True)
    sp.add_argument("--repro", required=True)
    sp.add_argument("--generator")
    sp.add_argument("--new-reason")
    sp.add_argument("--distinct-from", action="append")
    sp = add("sort", cmd_sort, True)
    sp.add_argument("--bucket", required=True)
    sp.add_argument("--by", required=True)
    sp.add_argument("--reason")
    sp = add("close-class", cmd_close, True)
    sp.add_argument("--by", required=True)
    sp.add_argument("--evidence", required=True)
    sp.add_argument("--sweep-cmd", required=True)
    sp.add_argument("--sweep-output")
    sp = add("verify-class", cmd_verify, True)
    sp.add_argument("--by", required=True)
    sp.add_argument("--generator-used", required=True)
    sp.add_argument("--evidence", required=True)
    sp = add("merge-classes", cmd_merge, True)
    sp.add_argument("--into", required=True)
    sp.add_argument("--by", required=True)
    sp.add_argument("--reason", required=True)
    add("status", cmd_status)
    sp = add("report", cmd_report)
    sp.add_argument("--json", action="store_true")
    return p


def _print(text, stream):
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc), file=stream)


def main(argv=None, out=None, err=None):
    if out is None and err is None:
        for stream in (sys.stdout, sys.stderr):   # signatures carry a middle dot; never mangle it when piped
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except (OSError, ValueError):
                    pass
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        a = parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        _print(a.fn(a.ledger, a), out)
        return 0
    except Refused as exc:
        _print(f"REFUSED: {exc}", err)
        return 1
    except Broken as exc:
        _print(f"ERROR: {exc}", err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
