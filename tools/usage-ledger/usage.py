#!/usr/bin/env python3
"""usage: track helper launches against a project's declared usage ceilings (R14).

Standard library only. State is one JSON file (sorted keys, two-space indent), appended to per dispatch -
mirrors tools/class-ledger and tools/claims-ledger's conventions.

R14: "Helpers are launched only below the project's usage ceilings (five-hour and weekly, declared in the
adapter); a resumed helper counts as a launch." The simplest, most literal reading is cost 1 per launch
(including a resume); a project that wants token-level tracking can log a real count instead - Codex's own
`--json` output already reports real per-call tokens (vendors/codex.md), this tool just sums whatever
number it is given, under whatever unit the project's own roles.md names alongside its ceiling.

Commands (the ledger file is always the first argument)
  init    FILE
  log     FILE --vendor V --role ROLE --task TEXT [--cost N] [--when ISO8601]
  status  FILE --window 5h|7d [--vendor V]           total cost in the window (all vendors, or one)
  check   FILE --window 5h|7d --ceiling N [--vendor V]   exit 0 if under the ceiling, else refuse (1)

What it enforces (exit 1 and no write when refused)
  - check refuses (does not launch anything itself - it only answers "is it safe to") when the window's
    total cost is at or over the ceiling. R14's "queue the task" instruction is the caller's job: a refusal
    here means queue, not retry harder.
  - log refuses a non-positive --cost and an unparsable --when.

What it cannot do: launch or stop a helper, know a vendor's real usage without being told (there is no
universal cross-vendor usage API; the caller logs what it knows, if anything is logged at all this is only
as accurate as what gets logged), or distinguish a resumed helper from a fresh one - the caller decides
whether a resume counts as its own log entry (R14 says it should).

Exit codes: 0 done, 1 refused by a rule or over the ceiling, 2 usage, file or format error.
"""
import argparse
import datetime
import json
import os
import re
import sys

SCHEMA_VERSION = 1
WINDOW_RE = re.compile(r"^(\d+)(h|d)$")


class Refused(Exception):
    """A protocol rule refused the action (exit 1)."""


class Broken(Exception):
    """Usage, file or format error (exit 2)."""


def parse_window(text):
    m = WINDOW_RE.fullmatch(text)
    if not m:
        raise Broken(f"--window must be like '5h' or '7d' (digits then h or d), got {text!r}")
    n, unit = int(m.group(1)), m.group(2)
    return datetime.timedelta(hours=n) if unit == "h" else datetime.timedelta(days=n)


def parse_when(text):
    try:
        dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Broken(f"--when must be ISO 8601, got {text!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


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


def cmd_init(path, a):
    if os.path.exists(path):
        raise Refused(f"{path} already exists")
    save(path, {"schema_version": SCHEMA_VERSION, "entries": []})
    return f"initialized {path}"


def cmd_log(path, a):
    data = load(path)
    cost = a.cost if a.cost is not None else 1
    if cost <= 0:
        raise Broken("--cost must be a positive number")
    when = parse_when(a.when) if a.when else _now()
    entry = {
        "vendor": a.vendor,
        "role": a.role,
        "task": a.task,
        "cost": cost,
        "when": when.isoformat(),
    }
    data["entries"].append(entry)
    save(path, data)
    return f"logged cost {cost} for {entry['vendor']}/{entry['role']} ({entry['task']})"


def _window_total(data, window, vendor=None):
    cutoff = _now() - window
    total = 0
    for e in data["entries"]:
        when = parse_when(e["when"])
        if when >= cutoff and (vendor is None or e["vendor"] == vendor):
            total += e["cost"]
    return total


def cmd_status(path, a):
    data = load(path)
    window = parse_window(a.window)
    total = _window_total(data, window, a.vendor)
    scope = f" for {a.vendor}" if a.vendor else " across all vendors"
    return f"last {a.window}{scope}: {total}"


def cmd_check(path, a):
    data = load(path)
    window = parse_window(a.window)
    total = _window_total(data, window, a.vendor)
    scope = f" for {a.vendor}" if a.vendor else " across all vendors"
    if total >= a.ceiling:
        raise Refused(f"last {a.window}{scope}: {total} is at or over the ceiling of {a.ceiling}; queue "
                      "the task instead of launching (R14)")
    return f"ok: last {a.window}{scope}: {total} under the ceiling of {a.ceiling}"


def parser():
    p = argparse.ArgumentParser(prog="usage.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def add_cmd(name, fn):
        sp = sub.add_parser(name)
        sp.add_argument("ledger")
        sp.set_defaults(fn=fn)
        return sp

    add_cmd("init", cmd_init)

    sp = add_cmd("log", cmd_log)
    sp.add_argument("--vendor", required=True)
    sp.add_argument("--role", required=True)
    sp.add_argument("--task", required=True)
    sp.add_argument("--cost", type=float, default=None, help="defaults to 1 (one launch, R14's own unit)")
    sp.add_argument("--when", help="ISO 8601; defaults to now")

    sp = add_cmd("status", cmd_status)
    sp.add_argument("--window", required=True)
    sp.add_argument("--vendor")

    sp = add_cmd("check", cmd_check)
    sp.add_argument("--window", required=True)
    sp.add_argument("--ceiling", type=float, required=True)
    sp.add_argument("--vendor")

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
