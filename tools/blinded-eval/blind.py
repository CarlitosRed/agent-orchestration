#!/usr/bin/env python3
"""blind: assign two variants (e.g. an old and a new skill file) to randomized, unlabeled slots so a judge
can score agent behavior without knowing which is which, then reveal the real mapping once judging is done.

Standard library only. From idea I-012 (ideas/README.md): "test how a skill or prompt change affects agent
behavior, blinded." This tool is the one safely-automatable piece of that: the randomization and sealing.
It does not run an agent, score anything, or design the eval's test cases - that stays the judge's job.

Commands
  assign  --a PATH --b PATH --out DIR [--seed N]   copy A and B into DIR/variant-1 and DIR/variant-2 in a
                                                    randomized order; writes a sealed mapping file
  reveal  --out DIR                                print which variant was which

What it enforces (exit 1 and no write when refused)
  - assign refuses an --out directory that already exists - a fresh eval every time, never a silent merge
    of two assignments.

What it cannot do: run anything, judge anything, or truly stop a judge from opening the mapping file early -
it only removes the LABELS from the copies the judge actually works with. The mapping file's name starts
with a dot so it does not sort next to the variant folders in a casual listing; that is a workflow nudge,
not security. --seed makes the coin flip reproducible for a test; omit it for a real eval, where the point
is that nobody (including whoever ran assign) can predict it without looking.

Exit codes: 0 done, 1 refused by a rule, 2 usage or file error.
"""
import argparse
import json
import os
import random
import shutil
import sys


class Refused(Exception):
    """A protocol rule refused the action (exit 1)."""


class Broken(Exception):
    """Usage, file or format error (exit 2)."""


def _copy_any(src, dst_dir):
    """Copy src (file or directory) into a freshly-created dst_dir. A file source is renamed to a neutral
    `content<ext>` - its original filename can itself carry the A/B identity (this tool's own tests used
    "old.md" vs "new.md") and would leak the blinding if preserved. A directory source keeps its own
    internal file names (already shared and neutral across variants by convention, e.g. both are
    SKILL.md) and is copied flat, with no nested folder carrying the original directory's name."""
    os.makedirs(dst_dir)
    if os.path.isdir(src):
        for name in os.listdir(src):
            s, d = os.path.join(src, name), os.path.join(dst_dir, name)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
    elif os.path.isfile(src):
        ext = os.path.splitext(src)[1]
        shutil.copy2(src, os.path.join(dst_dir, f"content{ext}"))
    else:
        raise Broken(f"no such file or directory: {src}")


def cmd_assign(a, out=None, err=None):
    if os.path.exists(a.out):
        raise Refused(f"{a.out} already exists; use a fresh --out directory for each eval")
    if not os.path.exists(a.a):
        raise Broken(f"no such file or directory: {a.a}")
    if not os.path.exists(a.b):
        raise Broken(f"no such file or directory: {a.b}")
    rng = random.Random(a.seed)
    a_is_variant_1 = rng.random() < 0.5
    os.makedirs(a.out)
    if a_is_variant_1:
        slots = {"variant-1": ("a", a.a), "variant-2": ("b", a.b)}
    else:
        slots = {"variant-1": ("b", a.b), "variant-2": ("a", a.a)}
    mapping = {}
    for slot, (label, source) in slots.items():
        _copy_any(source, os.path.join(a.out, slot))
        mapping[slot] = {"label": label, "source": os.path.abspath(source)}
    with open(os.path.join(a.out, ".mapping.json"), "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=2, sort_keys=True)
    return (f"assigned into {a.out}/variant-1 and {a.out}/variant-2 "
            "(sealed mapping at .mapping.json - judge first, reveal after)")


def cmd_reveal(a, out=None, err=None):
    mapping_path = os.path.join(a.out, ".mapping.json")
    if not os.path.exists(mapping_path):
        raise Broken(f"no mapping found in {a.out}; was assign run here?")
    with open(mapping_path, encoding="utf-8") as fh:
        mapping = json.load(fh)
    return "\n".join(f"{slot}: {info['label']} ({info['source']})" for slot, info in sorted(mapping.items()))


def parser():
    p = argparse.ArgumentParser(prog="blind.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("assign")
    sp.add_argument("--a", required=True)
    sp.add_argument("--b", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--seed", type=int, default=None, help="reproducible for a test; omit for a real eval")
    sp.set_defaults(fn=cmd_assign)

    sp = sub.add_parser("reveal")
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_reveal)

    return p


def main(argv=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        a = parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        print(a.fn(a), file=out)
        return 0
    except Refused as exc:
        print(f"REFUSED: {exc}", file=err)
        return 1
    except Broken as exc:
        print(f"ERROR: {exc}", file=err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
