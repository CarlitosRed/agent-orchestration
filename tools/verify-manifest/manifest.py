#!/usr/bin/env python3
"""manifest: shared helper for a project's .orchestration/verify/ scripts.

Standard library only. Three operations every generated verification skill needs and was
reinventing per project (leaks L48, L49 from the F4 trial on advance-po-reader):

  find-root   SCRIPT          resolve <root> from a script living under <root>/.orchestration/verify/,
                               by searching upward for an ancestor literally named ".orchestration"
                               rather than counting path segments (the off-by-one class behind L49)
  hash        PATH...         print path, size and sha256 for each file, tab-separated
  verify-survival MANIFEST    re-hash every evidence entry in a run's manifest.json; exit 1 on any
                               mismatch (missing file, size change, hash change)

A desk without Python ports find_verify_root's marker-search logic and verify_survival's
compare-by-hash logic exactly; see skills/create-verification-skill/SKILL.md.

Exit codes: 0 ok, 1 a check failed (survival mismatch), 2 usage or file error.
"""
import argparse
import hashlib
import json
import os
import sys


class Broken(Exception):
    """Usage, file or lookup error (exit 2)."""


def find_verify_root(start):
    """Return <root> given a path inside or equal to <root>/.orchestration/verify/.

    Walks upward from `start` looking for an ancestor directory named exactly
    ".orchestration" and returns its parent. This is a structural search, not a fixed
    hop count, so it cannot reproduce the off-by-one (wrong number of parent hops)
    that broke a hand-written doctor script during the F4 trial.
    """
    d = os.path.abspath(start)
    if os.path.isfile(d) or not os.path.isdir(d):
        d = os.path.dirname(d)
    while True:
        if os.path.basename(d) == ".orchestration":
            return os.path.dirname(d)
        parent = os.path.dirname(d)
        if parent == d:
            raise Broken(f"no .orchestration ancestor found above {start}")
        d = parent


def sha256_of(path, chunk_size=65536):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def build_entry(path):
    """One manifest evidence entry for `path`: path, size, sha256."""
    st = os.stat(path)
    return {"path": path, "size": st.st_size, "sha256": sha256_of(path)}


def verify_survival(entries, base_dir="."):
    """Re-check each recorded evidence entry against disk now.

    `entries`: list of {"path", "size", "sha256"} as recorded before cleanup.
    Returns a list of mismatch dicts (empty means survival held). Never raises for a
    missing or changed file; that is a reportable mismatch, not a crash.
    """
    mismatches = []
    for e in entries:
        full = e["path"] if os.path.isabs(e["path"]) else os.path.join(base_dir, e["path"])
        if not os.path.exists(full):
            mismatches.append({"path": e["path"], "reason": "missing"})
            continue
        now_size = os.stat(full).st_size
        if now_size != e["size"]:
            mismatches.append({"path": e["path"], "reason": "size", "was": e["size"], "now": now_size})
            continue
        now_hash = sha256_of(full)
        if now_hash != e["sha256"]:
            mismatches.append({"path": e["path"], "reason": "hash", "was": e["sha256"], "now": now_hash})
    return mismatches


def _cmd_find_root(args, out, err):
    try:
        root = find_verify_root(args.script)
    except Broken as e:
        print(str(e), file=err)
        return 2
    print(root, file=out)
    return 0


def _cmd_hash(args, out, err):
    for p in args.paths:
        if not os.path.isfile(p):
            print(f"not a file: {p}", file=err)
            return 2
        entry = build_entry(p)
        print(f"{entry['path']}\t{entry['size']}\t{entry['sha256']}", file=out)
    return 0


def _cmd_verify_survival(args, out, err):
    try:
        with open(args.manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read manifest {args.manifest}: {e}", file=err)
        return 2
    entries = data["evidence"] if isinstance(data, dict) and "evidence" in data else data
    mismatches = verify_survival(entries, base_dir=args.base)
    if mismatches:
        for m in mismatches:
            print(json.dumps(m, sort_keys=True), file=out)
        return 1
    print("survival: ok", file=out)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="manifest")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("find-root", help="resolve <root> from a script under <root>/.orchestration/verify/")
    sp.add_argument("script")
    sp.set_defaults(func=_cmd_find_root)

    sp = sub.add_parser("hash", help="print path, size, sha256 for each file (tab-separated)")
    sp.add_argument("paths", nargs="+")
    sp.set_defaults(func=_cmd_hash)

    sp = sub.add_parser("verify-survival", help="re-hash a manifest's evidence entries; exit 1 on any mismatch")
    sp.add_argument("manifest")
    sp.add_argument("--base", default=".")
    sp.set_defaults(func=_cmd_verify_survival)

    return p


def main(argv=None, out=sys.stdout, err=sys.stderr):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    return args.func(args, out, err)


if __name__ == "__main__":
    sys.exit(main())
