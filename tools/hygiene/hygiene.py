#!/usr/bin/env python3
"""Repo hygiene checks: vendor names, log row length, derivable numbers, hashed name sweep, required text, doc references.

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

CONFIG_KEYS = {"vendor_words", "vendor_free_paths", "log_files", "no_derivable_numbers", "sweep", "required_text", "doc_refs"}
REQUIRED_KEYS = {"text", "paths"}
LOG_KEYS = {"path", "max_chars", "since"}
DERIVABLE_KEYS = {"paths", "patterns"}
SWEEP_KEYS = {"hash_file", "exempt_files"}
DOC_REF_KEYS = {"paths", "ignore"}
ROW = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
WORD = re.compile(r"[A-Za-z]+")
QUOTED = re.compile(r"`([^`\s]+)`")
NOT_A_PATH = re.compile(r"[<>*${}()|\\[\]=]")
LINE_SUFFIX = re.compile(r"(:\d+(-\d+)?(,\d+)*|#.*)$")


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
        spec = cfg["no_derivable_numbers"]
        only(spec, DERIVABLE_KEYS, "no_derivable_numbers")
        for name in ("paths", "patterns"):
            values = spec.get(name)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
                raise ConfigError(f"no_derivable_numbers.{name}: a present check needs a non-empty list of strings "
                                  "(leave the whole key out to disable it)")
        for pattern in spec["patterns"]:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ConfigError(f"no_derivable_numbers.patterns: '{pattern}' is not a regular expression: {exc}") from exc
    for entry in cfg.get("required_text", []):
        only(entry, REQUIRED_KEYS, "required_text entry")
        paths = entry.get("paths")
        if not isinstance(entry.get("text"), str) or not entry["text"].strip() or "\n" in entry["text"]:
            raise ConfigError("required_text entry needs a non-empty one-line string text")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
            raise ConfigError("required_text entry needs a non-empty list of file paths")
    if "doc_refs" in cfg:
        spec = cfg["doc_refs"]
        only(spec, DOC_REF_KEYS, "doc_refs")
        for name in ("paths", "ignore"):
            values = spec.get(name, [] if name == "ignore" else None)
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values)                     or (name == "paths" and not values):
                raise ConfigError(f"doc_refs.{name}: expected a list of strings"
                                  + (" (non-empty; leave the whole key out to disable the check)" if name == "paths" else ""))
    if "sweep" in cfg:
        spec = cfg["sweep"]
        only(spec, SWEEP_KEYS, "sweep")
        if not isinstance(spec.get("hash_file"), str) or not spec["hash_file"]:
            raise ConfigError("sweep.hash_file: a present sweep needs the path of its hash file "
                              "(leave the whole key out to disable it)")
        exempt = spec.get("exempt_files", [])
        if not isinstance(exempt, list) or not all(isinstance(v, str) for v in exempt):
            raise ConfigError("sweep.exempt_files: expected a list of strings")
    return cfg


def tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(f"{root} is not a readable git repository") from exc
    return [p for p in out.decode("utf-8").split("\0") if p]


class Unreadable(Exception):
    """A tracked file is neither UTF-8 or UTF-16 text nor clearly binary."""


def read_lines(root, rel):
    """Lines of a tracked text file, or None for a binary one (NUL bytes). UTF-8, with or without a byte-order
    mark, and UTF-16 with a byte-order mark (what Windows PowerShell writes) are text. Anything else that is
    not clearly binary is an error, never silently skipped."""
    try:
        with open(os.path.join(root, rel), "rb") as stream:
            raw = stream.read()
    except OSError as exc:
        raise Unreadable(f"cannot be read: {exc}") from exc
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16").splitlines()
        except UnicodeDecodeError as exc:
            raise Unreadable("starts like UTF-16 but does not decode as UTF-16; convert it to UTF-8") from exc
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise Unreadable("is not UTF-8 or UTF-16 text and has no NUL bytes, so it is not clearly binary; "
                         "convert it to UTF-8") from exc


def lines_of(root, rel, problems):
    """The numbered lines of a tracked file; an unreadable file is reported as a problem, a binary one skipped."""
    try:
        return list(enumerate(read_lines(root, rel) or [], 1))
    except Unreadable as exc:
        problems.append(f"{rel}: {exc}")
        return []


def check_vendor_words(root, files, cfg):
    words = cfg.get("vendor_words", [])
    if not words:
        return []
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
    problems = []
    for rel in files:
        if not any(fnmatch.fnmatchcase(rel, g) for g in cfg.get("vendor_free_paths", [])):
            continue
        for number, line in lines_of(root, rel, problems):
            hit = pattern.search(line)
            if hit:
                problems.append(f"{rel}:{number}: vendor name '{hit.group(1)}' outside vendors/")
    return problems


def check_required_text(root, files, cfg):
    """Every listed file must hold the exact one-line text, so a rule that has to travel with every agent prompt
    cannot be dropped from one template without CI saying which."""
    problems = []
    for entry in cfg.get("required_text", []):
        for rel in entry["paths"]:
            if rel not in files:
                problems.append(f"{rel}: not tracked, so it cannot carry the required text")
                continue
            lines = [line for _, line in lines_of(root, rel, problems)]
            if not any(entry["text"] in line for line in lines):
                problems.append(f"{rel}: missing the required text '{entry['text'][:50]}...'")
    return problems


def check_log_rows(root, files, cfg):
    problems = []
    for entry in cfg.get("log_files", []):
        if entry["path"] not in files:
            problems.append(f"{entry['path']}: log file is not tracked")
            continue
        for number, line in lines_of(root, entry["path"], problems):
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
        for number, line in lines_of(root, rel, problems):
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
    try:
        lines = read_lines(root, spec["hash_file"])
    except Unreadable as exc:
        return [f"{spec['hash_file']}: {exc}"]
    if lines is None:
        return [f"{spec['hash_file']}: cannot read the hash file"]
    for number, line in enumerate(lines, 1):
        token = line.split("#", 1)[0].strip().lower()
        if not token:
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", token):
            raise ConfigError(f"{spec['hash_file']}:{number}: not a 64-character hexadecimal SHA-256, so it "
                              "could never match; fix or remove it")
        hashes.add(token)
    exempt = set(spec.get("exempt_files", []))
    problems = []
    for rel in files:
        if rel in exempt or rel == spec["hash_file"]:
            continue
        for number, line in lines_of(root, rel, problems):
            if any(hashlib.sha256(w.lower().encode("utf-8")).hexdigest() in hashes for w in WORD.findall(line)):
                problems.append(f"{rel}:{number}: contains a word from the name denylist")
    return problems


def check_doc_refs(root, files, cfg):
    """A backticked path that starts at a top-level folder or file of this repo must name a tracked file or
    folder. Only opted-in files are read; `ignore` lists paths that are deliberate (a file in a project, a
    file not written yet). Placeholders, URLs and anything with shell or glob characters are not paths."""
    spec = cfg.get("doc_refs")
    if not spec:
        return []
    known = set(files)
    folders = set()
    for rel in files:
        parts = rel.split("/")
        folders.update("/".join(parts[:i]) for i in range(1, len(parts)))
    tops = {rel.split("/")[0] for rel in files}
    problems = []
    for rel in files:
        if not any(fnmatch.fnmatchcase(rel, g) for g in spec["paths"]):
            continue
        for number, line in lines_of(root, rel, problems):
            for quoted in QUOTED.findall(line):
                ref = LINE_SUFFIX.sub("", quoted.rstrip(".,;:)"))
                if NOT_A_PATH.search(ref) or "/" not in ref or ref.startswith(("http", "~", "/")):
                    continue
                if ref.split("/")[0] not in tops or any(fnmatch.fnmatchcase(ref, g) for g in spec.get("ignore", [])):
                    continue
                if ref.rstrip("/") not in known and ref.rstrip("/") not in folders:
                    problems.append(f"{rel}:{number}: `{ref}` is not a file or folder in this repo; fix the "
                                    "path, or add it to doc_refs.ignore if it is deliberate")
    return problems


CHECKS = [("vendor-words", check_vendor_words), ("log-rows", check_log_rows),
          ("derivable-numbers", check_derivable_numbers), ("name-sweep", check_name_sweep),
          ("required-text", check_required_text), ("doc-refs", check_doc_refs)]


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
