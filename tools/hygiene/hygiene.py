#!/usr/bin/env python3
"""Repo hygiene checks: vendor names, log row length, derivable numbers, hashed name sweep.

Usage: hygiene.py check [--root DIR] [--config PATH]
Exit 0: every check passed; 1: a violation; 2: bad config or not a git repo.
Reads tracked files only (git ls-files). The name sweep compares SHA-256 hashes of lowercase words, so
the denylist itself publishes nothing, and a violation prints file:line but never the word.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

CONFIG_KEYS = {"vendor_words", "vendor_free_paths", "log_files", "no_derivable_numbers", "sweep"}
LOG_KEYS = {"path", "max_chars", "since"}
DERIVABLE_KEYS = {"paths", "patterns"}
SWEEP_KEYS = {"hash_file", "exempt_files"}
ROW = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
WORD = re.compile(r"[A-Za-z]+")


class ConfigError(Exception):
    """The config or the repo cannot be used."""


def only(value, allowed, label):
    if not isinstance(value, dict) or {k for k in value if not k.startswith("_")} - allowed:
        raise ConfigError(f"{label}: expected an object with fields from {sorted(allowed)}")


def load_config(path):
    try:
        with open(path, encoding="utf-8-sig") as stream:
            cfg = json.load(stream)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    only(cfg, CONFIG_KEYS, "config")
    for name in ("vendor_words", "vendor_free_paths"):
        if not isinstance(cfg.get(name, []), list) or not all(isinstance(v, str) for v in cfg.get(name, [])):
            raise ConfigError(f"{name}: expected a list of strings")
    for entry in cfg.get("log_files", []):
        only(entry, LOG_KEYS, "log_files entry")
        if not isinstance(entry.get("path"), str) or type(entry.get("max_chars")) is not int:
            raise ConfigError("log_files entry needs a string path and an integer max_chars")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.get("since", "0000-00-00")):
            raise ConfigError("log_files since must be YYYY-MM-DD")
    if "no_derivable_numbers" in cfg:
        only(cfg["no_derivable_numbers"], DERIVABLE_KEYS, "no_derivable_numbers")
    if "sweep" in cfg:
        only(cfg["sweep"], SWEEP_KEYS, "sweep")
    return cfg


def tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(f"{root} is not a readable git repository") from exc
    return [p for p in out.decode("utf-8").split("\0") if p]


def read_lines(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as stream:
            return stream.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def check_vendor_words(root, files, cfg):
    words = cfg.get("vendor_words", [])
    if not words:
        return []
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
    problems = []
    for rel in files:
        if not any(fnmatch.fnmatchcase(rel, g) for g in cfg.get("vendor_free_paths", [])):
            continue
        for number, line in enumerate(read_lines(root, rel) or [], 1):
            hit = pattern.search(line)
            if hit:
                problems.append(f"{rel}:{number}: vendor name '{hit.group(1)}' outside vendors/")
    return problems


def check_log_rows(root, files, cfg):
    problems = []
    for entry in cfg.get("log_files", []):
        if entry["path"] not in files:
            problems.append(f"{entry['path']}: log file is not tracked")
            continue
        for number, line in enumerate(read_lines(root, entry["path"]) or [], 1):
            row = ROW.match(line)
            if row and row.group(1) >= entry.get("since", "0000-00-00") and len(line) > entry["max_chars"]:
                problems.append(f"{entry['path']}:{number}: row is {len(line)} characters, limit {entry['max_chars']}; "
                                "keep the row short and point to the evidence")
    return problems


def check_derivable_numbers(root, files, cfg):
    spec = cfg.get("no_derivable_numbers")
    if not spec:
        return []
    patterns = [re.compile(p) for p in spec.get("patterns", [])]
    problems = []
    for rel in spec.get("paths", []):
        if rel not in files:
            problems.append(f"{rel}: file is not tracked")
            continue
        for number, line in enumerate(read_lines(root, rel) or [], 1):
            for pattern in patterns:
                hit = pattern.search(line)
                if hit:
                    problems.append(f"{rel}:{number}: derivable number '{hit.group(0)}'; delete it or point at the source")
    return problems


def check_name_sweep(root, files, cfg):
    spec = cfg.get("sweep")
    if not spec:
        return []
    hashes = set()
    lines = read_lines(root, spec["hash_file"])
    if lines is None:
        return [f"{spec['hash_file']}: cannot read the hash file"]
    for line in lines:
        token = line.split("#", 1)[0].strip().lower()
        if token:
            hashes.add(token)
    exempt = set(spec.get("exempt_files", []))
    problems = []
    for rel in files:
        if rel in exempt or rel == spec["hash_file"]:
            continue
        for number, line in enumerate(read_lines(root, rel) or [], 1):
            if any(hashlib.sha256(w.lower().encode("utf-8")).hexdigest() in hashes for w in WORD.findall(line)):
                problems.append(f"{rel}:{number}: contains a word from the name denylist")
    return problems


CHECKS = [("vendor-words", check_vendor_words), ("log-rows", check_log_rows),
          ("derivable-numbers", check_derivable_numbers), ("name-sweep", check_name_sweep)]


def run(root, config_path, out=print):
    cfg = load_config(config_path)
    files = sorted(tracked_files(root))
    failed = False
    for name, check in CHECKS:
        problems = check(root, files, cfg)
        if problems:
            failed = True
            for problem in problems:
                out(f"FAIL {name}: {problem}")
        else:
            out(f"PASS {name}")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    try:
        return run(args.root, args.config or os.path.join(args.root, ".orchestration", "hygiene.json"))
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
