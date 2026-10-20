#!/usr/bin/env python3
"""gate: a generic merge gate for a repository whose plan cannot enforce branch protection.

Standard library only. Uses the GitHub CLI (gh) and git. Every project rule (tiers, vendors and their branch
prefixes, signers, protected paths, required checks, forbidden files) comes from a per-project JSON config;
the schema is in gate.schema.md. Approvals are signed comments, not GitHub reviews, so that agents of several
vendors posting from one shared account can still be told apart by their signature.

Commands
  check <PR>              Evaluate every gate rule against the PR's current head commit.
  merge <PR> --as NAME    Run check; if it passes, squash-merge with the head commit pinned.
  audit --range A..B      Flag commits on the base branch that did not come through `merge`.
  scan                    Block forbidden files and secrets, by content as well as by name.
  paths                   Show how many tracked files each protected path matches.

What the gate cannot do: stop someone who has the account's credentials from merging by hand. It makes the
rules checkable and leaves a record on every merge. The audit and the owner's "hold" are the backstops.
"""
import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import unicodedata

SEP = "·"  # the middle dot in "Independent Reviewer · VendorName"

# GitHub facts, not project policy.
VIEW_FIELDS = ("number,title,state,isDraft,baseRefName,headRefName,headRefOid,author,labels,"
               "body,baseRefOid,changedFiles,statusCheckRollup,comments,reviews")
# Everything that defines WHICH diff the file list belongs to. Read before and after the list.
SNAPSHOT_FIELDS = ("number", "baseRefName", "baseRefOid", "headRefName", "headRefOid", "changedFiles")
SHA = re.compile(r"[0-9a-f]{40}")                       # used with fullmatch: a trailing newline must not pass
FILE_STATUSES = ("added", "removed", "modified", "renamed", "copied", "changed", "unchanged")
NEEDS_OLD_NAME = ("renamed", "copied")
MAX_FILES = 3000       # GitHub lists at most 3000 files of a pull request
MAX_COMMENTS = 100     # `gh pr view --json comments` returns at most 100
DRIVE = re.compile(r"[A-Za-z]:")
REF_FORBIDDEN = set("~^:?*[" + chr(92))
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
RECORD_VALUE = re.compile(r"[A-Za-z0-9_.-]+")

GO = re.compile(r"^go\b", re.I)
HOLD = re.compile(r"^hold\b", re.I)
UNHOLD = re.compile(r"^unhold\b", re.I)
# Finds a verdict phrase ANYWHERE, leniently (any spacing, any case), to report verdicts that do not count.
VERDICT_ANYWHERE = re.compile(r"\b(not\s+)?approved\s+at\s+`?([0-9a-f]{4,40})(?![0-9a-f])", re.I)

# ---------------------------------------------------------------- config defaults (non-policy knobs only)

DEFAULT_ROLES = ["Orchestrator", "Platform Engineer", "Build Engineer", "Independent Reviewer",
                 "Release Manager", "Verification Engineer", "Research Analyst", "Operations Clerk",
                 "Strategy Advisor"]
# A signed comment starts with the signer's name in bold: **Name:** or **Name**: (the colon is optional).
DEFAULT_SIGNATURE = r"^\s*\*\*\s*(?P<name>[^*\n]+?)\s*:?\s*\*\*\s*:?\s*(?P<rest>.*)\Z"
DEFAULT_MAGIC = [
    {"hex": "25504446 2d", "kind": "PDF"},
    {"hex": "89504e47 0d0a1a0a", "kind": "PNG image"},
    {"hex": "ffd8ff", "kind": "JPEG image"},
    {"hex": "47494638 3761", "kind": "GIF image"},
    {"hex": "47494638 3961", "kind": "GIF image"},
    {"hex": "49492a00", "kind": "TIFF image"},
    {"hex": "4d4d002a", "kind": "TIFF image"},
    {"hex": "47475546", "kind": "GGUF model file"},
]
DEFAULT_SECRETS = [
    {"pattern": r"\bsk-[A-Za-z0-9_-]{20,}", "label": "API key (sk-...)"},
    {"pattern": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "label": "private key"},
    {"pattern": r"AKIA[0-9A-Z]{16}", "label": "AWS access key"},
    {"pattern": r"gh[pousr]_[A-Za-z0-9]{30,}", "label": "GitHub token"},
]
DEFAULT_FORBIDDEN = [".env", ".env.*", "*.pem", "*.key"]
DEFAULT_ALLOW = [".env.example", ".env.*.example"]

OPTIONAL = {
    "repo": "",
    "base": "main",
    "roles": DEFAULT_ROLES,
    "legacy_signers": {},
    "approver_roles": None,
    "merger_roles": None,
    "same_vendor_reviewers": [],
    "forbidden_head_prefixes": [],
    "hold_label": "hold",
    "body_headings": [],
    "signature_pattern": DEFAULT_SIGNATURE,
    "verdict_sha_min_length": 40,
    "forbidden_globs": DEFAULT_FORBIDDEN,
    "scan_allow": DEFAULT_ALLOW,
    "magic": DEFAULT_MAGIC,
    "secrets": DEFAULT_SECRETS,
    "max_file_mb": 5,
    "shared_account": True,
    "owner_logins": [],
    "distinct_accounts": False,
    "audit_exempt": [],
}
REQUIRED = ("schema_version", "tiers", "vendors", "owner_signers", "protected_paths", "protected_tier",
            "required_checks")
TIER_KEYS = {"label", "level", "name", "record", "approvals", "plan_go", "owner_approval", "cross_vendor",
             "body_headings", "allowed_paths", "mergeable"}
VENDOR_KEYS = {"names", "branch_prefixes", "logins"}


class GateError(Exception):
    pass


class ConfigError(GateError):
    pass


# ---------------------------------------------------------------- config

def _key(text):
    """How names are compared: whitespace runs collapsed, case folded."""
    return " ".join(text.split()).casefold()


def _is_int(value):
    """A real integer: not a bool, not a float that happens to equal one."""
    return type(value) is int


def _str_list(raw, field, allow_empty=True):
    value = raw[field]
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigError(f"config '{field}' must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ConfigError(f"config '{field}' must not be empty")
    return list(value)


def _bool(obj, field, where):
    if type(obj[field]) is not bool:
        raise ConfigError(f"config {where} '{field}' must be true or false")
    return obj[field]


class Tier:
    def __init__(self, raw, index):
        where = f"tiers[{index}]"
        if not isinstance(raw, dict):
            raise ConfigError(f"config {where} must be an object")
        unknown = set(raw) - TIER_KEYS
        if unknown:
            raise ConfigError(f"config {where} has unknown field(s) {sorted(unknown)}")
        for need in ("label", "level"):
            if need not in raw:
                raise ConfigError(f"config {where} needs '{need}'")
        if not isinstance(raw["label"], str) or not raw["label"].strip():
            raise ConfigError(f"config {where} 'label' must be a non-empty string")
        if not _is_int(raw["level"]):
            raise ConfigError(f"config {where} 'level' must be a whole number")
        full = {"name": raw["label"], "record": str(raw["level"]), "approvals": 0, "plan_go": False,
                "owner_approval": False, "cross_vendor": True, "body_headings": False, "allowed_paths": None,
                "mergeable": True}
        full.update(raw)
        self.label, self.level, self.name = full["label"], full["level"], full["name"]
        if not isinstance(self.name, str):
            raise ConfigError(f"config {where} 'name' must be a string")
        self.record = full["record"]
        if not isinstance(self.record, str) or not RECORD_VALUE.fullmatch(self.record):
            raise ConfigError(f"config {where} 'record' must be letters, digits, '.', '_' or '-' only")
        if not _is_int(full["approvals"]) or full["approvals"] < 0:
            raise ConfigError(f"config {where} 'approvals' must be a whole number, 0 or more")
        self.approvals = full["approvals"]
        self.plan_go = _bool(full, "plan_go", where)
        self.owner_approval = _bool(full, "owner_approval", where)
        self.cross_vendor = _bool(full, "cross_vendor", where)
        self.body_headings = _bool(full, "body_headings", where)
        self.mergeable = _bool(full, "mergeable", where)
        paths = full["allowed_paths"]
        if paths is not None and (not isinstance(paths, list)
                                  or not all(isinstance(p, str) and p.strip() for p in paths)):
            raise ConfigError(f"config {where} 'allowed_paths' must be null or a list of non-empty strings")
        self.allowed_paths = paths


class Signer:
    """kind: 'owner', 'role' (new format **Role · Vendor:**), 'legacy' (old format **Name · job:**) or None."""
    def __init__(self, name, kind=None, vendor=None, role=None):
        self.name, self.kind, self.vendor, self.role = name, kind, vendor, role
        self.key = _key(name)

    @property
    def known(self):
        return self.kind is not None


class Config:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ConfigError("the config must be a JSON object")
        unknown = [k for k in raw if k not in OPTIONAL and k not in REQUIRED and not k.startswith("_")]
        if unknown:
            raise ConfigError(f"config has unknown field(s) {sorted(unknown)}; fields starting with '_' are comments")
        missing = [k for k in REQUIRED if k not in raw]
        if missing:
            raise ConfigError(f"config is missing required field(s) {missing}")
        full = {k: (json.loads(json.dumps(v)) if isinstance(v, (list, dict)) else v) for k, v in OPTIONAL.items()}
        full.update(raw)
        self.raw = full
        if full["schema_version"] != 1 or not _is_int(full["schema_version"]):
            raise ConfigError("config 'schema_version' must be 1")

        # repository and base
        if not isinstance(full["repo"], str):
            raise ConfigError("config 'repo' must be a string (empty = detect)")
        self.repo = full["repo"]
        if not isinstance(full["base"], str) or bad_branch(full["base"]):
            raise ConfigError("config 'base' must be a valid branch name")
        self.base = full["base"]

        # tiers
        if not isinstance(full["tiers"], list) or not full["tiers"]:
            raise ConfigError("config 'tiers' must be a non-empty list")
        self.tiers = sorted((Tier(t, i) for i, t in enumerate(full["tiers"])), key=lambda t: t.level)
        for attr in ("label", "level", "record"):
            values = [getattr(t, attr) for t in self.tiers]
            if len(set(values)) != len(values):
                raise ConfigError(f"config tiers must have unique '{attr}' values")
        self.tier_by_label = {t.label: t for t in self.tiers}
        if not _is_int(full["protected_tier"]) or full["protected_tier"] not in [t.level for t in self.tiers]:
            raise ConfigError("config 'protected_tier' must be the level of one of the tiers")
        self.protected_tier = full["protected_tier"]

        # vendors
        vendors = full["vendors"]
        if not isinstance(vendors, dict) or not vendors:
            raise ConfigError("config 'vendors' must be a non-empty object of vendor id -> {names, branch_prefixes}")
        self.vendor_by_name, self.prefixes = {}, []
        self.vendor_by_login, self.vendor_logins = {}, {}
        for vid, spec in vendors.items():
            if not vid.strip():
                raise ConfigError("config vendor ids must be non-empty")
            if not isinstance(spec, dict) or set(spec) - VENDOR_KEYS or "names" not in spec:
                raise ConfigError(f"config vendors['{vid}'] must be an object with 'names' and 'branch_prefixes'")
            names = spec["names"]
            prefixes = spec.get("branch_prefixes", [])
            for field, value in (("names", names), ("branch_prefixes", prefixes)):
                if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
                    raise ConfigError(f"config vendors['{vid}'].{field} must be a list of non-empty strings")
            if not names:
                raise ConfigError(f"config vendors['{vid}'].names must not be empty")
            for n in names:
                if SEP in n or _key(n) in self.vendor_by_name:
                    raise ConfigError(f"config vendor name '{n}' is repeated or contains the middle dot")
                self.vendor_by_name[_key(n)] = vid
            for p in prefixes:
                self.prefixes.append((p, vid))
            logins = spec.get("logins", [])
            if not isinstance(logins, list) or not all(isinstance(v, str) and v and not any(c.isspace() for c in v)
                                                       for v in logins):
                raise ConfigError(f"config vendors['{vid}'].logins must be a list of GitHub logins (no spaces)")
            self.vendor_logins[vid] = {v.lower() for v in logins}
            for login in logins:
                if login.lower() in self.vendor_by_login:
                    raise ConfigError(f"config login '{login}' is listed for more than one vendor")
                self.vendor_by_login[login.lower()] = vid
        for p, v in self.prefixes:
            for q, w in self.prefixes:
                if (p, v) != (q, w) and q.startswith(p):
                    raise ConfigError(f"config branch prefixes '{p}' and '{q}' overlap; a branch could match both")
        self.forbidden_head_prefixes = _str_list(full, "forbidden_head_prefixes")

        # signers: roles (new format), legacy names (old format), owner names. Disjoint, so detection is unambiguous.
        self.roles = _str_list(full, "roles")
        self.role_by_key = {_key(r): r for r in self.roles}
        legacy = full["legacy_signers"]
        if not isinstance(legacy, dict):
            raise ConfigError("config 'legacy_signers' must be an object of old first name -> vendor id")
        self.legacy = {}
        for name, vid in legacy.items():
            if not name.strip() or SEP in name or vid not in vendors:
                raise ConfigError(f"config legacy_signers['{name}'] must be a plain name mapped to a vendor id")
            self.legacy[_key(name)] = vid
        self.owner_signers = _str_list(full, "owner_signers", allow_empty=False)
        self.owner_keys = {_key(o) for o in self.owner_signers}
        groups = {"roles": set(self.role_by_key), "legacy_signers": set(self.legacy), "owner_signers": self.owner_keys}
        names = list(groups)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                both = groups[a] & groups[b]
                if both:
                    raise ConfigError(f"config '{a}' and '{b}' share {sorted(both)}; a signature must mean one thing")
        if any(SEP in r for r in self.roles):
            raise ConfigError("config role names must not contain the middle dot")
        for field in ("approver_roles", "merger_roles"):
            value = full[field]
            if value is not None:
                lst = _str_list(full, field)
                if any(_key(r) not in self.role_by_key for r in lst):
                    raise ConfigError(f"config '{field}' may only name roles listed in 'roles'")
                value = {_key(r) for r in lst}
            setattr(self, field, value)
        self.same_vendor_reviewers = {_key(n) for n in _str_list(full, "same_vendor_reviewers")}
        # Compensating control for a tier that allows same-vendor review (docs/vendor-count-modes.md,
        # adapters/README.md "How many vendors"): a single listed identity (or the same name twice,
        # which collapses to one key above) is self-approval wearing an allowlist, not independent
        # review, and that tier must pull the owner in instead of silently trusting one same-vendor name.
        same_vendor_tiers = [t for t in self.tiers if not t.cross_vendor and t.approvals > 0]
        if same_vendor_tiers:
            if len(self.same_vendor_reviewers) < 2:
                raise ConfigError(
                    "config 'same_vendor_reviewers' needs at least 2 distinct identities: tier(s) "
                    f"{[t.label for t in same_vendor_tiers]} set cross_vendor: false with approvals > 0, "
                    "and a single name (or one name listed twice) is self-approval, not review")
            no_owner = [t.label for t in same_vendor_tiers if not t.owner_approval]
            if no_owner:
                raise ConfigError(
                    f"config tier(s) {no_owner} set cross_vendor: false with approvals > 0 but "
                    "owner_approval: false; a tier allowing same-vendor review must also require the "
                    "owner's approval on that tier (the decided compensating control, docs/vendor-count-modes.md)")

        # signals
        if not isinstance(full["signature_pattern"], str):
            raise ConfigError("config 'signature_pattern' must be a string")
        try:
            self.signature = re.compile(full["signature_pattern"], re.S)
        except re.error as exc:
            raise ConfigError(f"config 'signature_pattern' is not a valid regular expression: {exc}")
        if not {"name", "rest"} <= set(self.signature.groupindex):
            raise ConfigError("config 'signature_pattern' needs the named groups 'name' and 'rest'")
        if not self.signature.pattern.startswith("^"):
            raise ConfigError("config 'signature_pattern' must start with ^ (the signature opens the comment)")
        n = full["verdict_sha_min_length"]
        if not _is_int(n) or not 7 <= n <= 40:
            raise ConfigError("config 'verdict_sha_min_length' must be a whole number from 7 to 40")
        self.sha_min = n
        # The verdict is matched with re.match on the text right after the signature: it must be the first words.
        self.verdict = re.compile(r"(approved|not approved) at\s+`?([0-9a-f]{%d,40})(?![0-9a-f])`?" % n, re.I)
        if not isinstance(full["hold_label"], str) or not full["hold_label"].strip():
            raise ConfigError("config 'hold_label' must be a non-empty string")
        self.hold_label = full["hold_label"]

        # paths, checks, body
        self.protected_paths = _str_list(full, "protected_paths")
        self.required_checks = _str_list(full, "required_checks")
        self.body_headings = _str_list(full, "body_headings")
        if any(t.body_headings for t in self.tiers) and not self.body_headings:
            raise ConfigError("a tier asks for body headings but config 'body_headings' is empty")

        # scan
        self.forbidden_globs = _str_list(full, "forbidden_globs")
        self.scan_allow = _str_list(full, "scan_allow")
        self.magic = []
        if not isinstance(full["magic"], list):
            raise ConfigError("config 'magic' must be a list of {hex, kind}")
        for m in full["magic"]:
            if not isinstance(m, dict) or set(m) != {"hex", "kind"} or not isinstance(m["kind"], str):
                raise ConfigError("config 'magic' entries must be {\"hex\": ..., \"kind\": ...}")
            try:
                data = bytes.fromhex(m["hex"])
            except (TypeError, ValueError):
                raise ConfigError(f"config magic '{m['kind']}' has a hex value that is not hex")
            if not data:
                raise ConfigError(f"config magic '{m['kind']}' is empty")
            self.magic.append((data, m["kind"]))
        self.secrets = []
        if not isinstance(full["secrets"], list):
            raise ConfigError("config 'secrets' must be a list of {pattern, label}")
        for s in full["secrets"]:
            if not isinstance(s, dict) or set(s) != {"pattern", "label"}:
                raise ConfigError("config 'secrets' entries must be {\"pattern\": ..., \"label\": ...}")
            try:
                self.secrets.append((re.compile(s["pattern"]), s["label"]))
            except (re.error, TypeError) as exc:
                raise ConfigError(f"config secret '{s.get('label')}' is not a valid regular expression: {exc}")
        mb = full["max_file_mb"]
        if type(mb) not in (int, float) or mb <= 0:
            raise ConfigError("config 'max_file_mb' must be a positive number")
        self.max_file_mb = mb
        self.shared_account = _bool(full, "shared_account", "")
        owner_logins = _str_list(full, "owner_logins")
        if any(any(c.isspace() for c in v) for v in owner_logins):
            raise ConfigError("config 'owner_logins' must be GitHub logins (no spaces)")
        self.owner_logins = {v.lower() for v in owner_logins}
        clash = sorted(self.owner_logins & set(self.vendor_by_login))
        if clash:
            raise ConfigError(f"config logins {clash} are listed both as owner and as a vendor; they must be separate accounts")
        self.distinct_accounts = _bool(full, "distinct_accounts", "")
        self.audit_exempt = _str_list(full, "audit_exempt")

        # the Gate-Record trailer: only tiers the gate can merge have a valid record value
        records = "|".join(re.escape(t.record) for t in self.tiers if t.mergeable)
        self.trailer = re.compile(r"^Gate-Record: pass tier=(%s) head=([0-9a-f]{40})\b(.*)$" % (records or "(?!)"),
                                  re.M)
        self.tier_by_record = {t.record: t for t in self.tiers}

    def tier_above(self, tier):
        higher = [t for t in self.tiers if t.level > tier.level]
        return higher[0] if higher else None

    def tier_at(self, level):
        return next(t for t in self.tiers if t.level == level)


def build_config(raw):
    return Config(raw)


def default_config_path(git=None):
    """<repository top level>/.orchestration/gate.json, or the same under the current folder outside git."""
    git = git or run_git
    try:
        top = git(["rev-parse", "--show-toplevel"]).strip()
    except (GateError, OSError):
        top = ""
    return os.path.join(top or os.getcwd(), ".orchestration", "gate.json")


def load_config(path):
    """Read and validate the config. A missing or invalid file is an error: there are no hidden policy defaults."""
    if not os.path.isfile(path):
        raise ConfigError(f"no gate config at {path}; pass --config or create it (see gate.schema.md)")
    with open(path, encoding="utf-8-sig") as fh:   # tolerate a byte-order mark written by Windows editors
        try:
            raw = json.load(fh)
        except ValueError as exc:
            raise ConfigError(f"the gate config {path} is not valid JSON: {exc}")
    return Config(raw)


# ---------------------------------------------------------------- strict values from GitHub

def match_any(path, globs, fold=False):
    """A glob with no slash also matches the file's own name in any folder. fold=True ignores upper/lower case:
    used for rules that DENY or raise a tier, because Windows and macOS treat `Reader.py` and `reader.py` as one."""
    if fold:
        path, globs = path.lower(), [g.lower() for g in globs]
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(path, g) or ("/" not in g and fnmatch.fnmatchcase(name, g)) for g in globs)


def odd_character(ch, allow_space):
    """Any Unicode control, format, surrogate, private-use or unassigned character (C*), and any separator (Z*)
    except, where allowed, the plain ASCII space."""
    cat = unicodedata.category(ch)
    return cat.startswith("C") or (cat.startswith("Z") and not (allow_space and ch == " "))


def bad_path(path):
    """Why a repository path from GitHub cannot be trusted, or None."""
    if not isinstance(path, str) or not path:
        return "is not text"
    if any(odd_character(c, allow_space=True) for c in path) or chr(92) in path or path != path.strip(" "):
        return "has a control, hidden or unusual space character, or a backslash, or a space at an end"
    if path.startswith("/") or DRIVE.match(path) or any(part in ("", ".", "..") for part in path.split("/")):
        return "is not a plain repository path (rooted, drive-lettered, or with an empty, '.' or '..' part)"
    return None


def bad_branch(name):
    """Why a branch name cannot be trusted, or None. Exact, non-normalizing form of git check-ref-format."""
    if not isinstance(name, str) or not name:
        return "is not text"
    if any(odd_character(c, allow_space=False) for c in name):
        return "has a space, control or hidden character"
    if any(c in REF_FORBIDDEN for c in name):
        return "has a character Git does not allow in a branch name (~ ^ : ? * [ or a backslash)"
    if name.startswith("-") or name.endswith(".") or ".." in name or "@{" in name:
        return "is not a valid Git branch name"
    for part in name.split("/"):
        if not part or part.startswith(".") or part.endswith(".lock"):
            return "is not a valid Git branch name (empty part, or a part starting with '.' or ending in '.lock')"
    return None


def check_identity(got, number, where):
    """Validate, strictly and before any comparison, the fields that say which diff a pull request is."""
    if not isinstance(got, dict):
        raise GateError(f"GitHub's {where} answer about the pull request is not an object; cannot verify the files")
    for field in SNAPSHOT_FIELDS:
        if field not in got:
            raise GateError(f"GitHub's {where} answer leaves out {field}; cannot tell which diff the file list belongs to")
    if not _is_int(got["number"]) or got["number"] != number:
        raise GateError(f"GitHub's {where} answer is for pull request {got['number']!r}, not {number}")
    for field in ("headRefOid", "baseRefOid"):
        if not isinstance(got[field], str) or not SHA.fullmatch(got[field]):
            raise GateError(f"GitHub's {where} {field} is not a 40-character lowercase commit id; "
                            "cannot tell which diff the file list belongs to")
    for field in ("headRefName", "baseRefName"):
        if bad_branch(got[field]):
            raise GateError(f"GitHub's {where} {field} is not a clean branch name; "
                            "cannot tell which diff the file list belongs to")
    if not _is_int(got["changedFiles"]) or got["changedFiles"] < 0:
        raise GateError(f"GitHub's {where} changedFiles is not a whole number; cannot verify the files")


# ---------------------------------------------------------------- runners

def run_gh(args):
    p = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise GateError(f"gh {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def run_git(args, cwd=None, binary=False):
    p = subprocess.run(["git"] + args, capture_output=True, cwd=cwd)
    if p.returncode != 0:
        raise GateError(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout if binary else p.stdout.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- reading signed comments

def split_signature(cfg, body):
    """Return (name, rest). name is None when the comment is not signed. Nothing is stripped before the
    signature except ordinary whitespace: a byte-order mark or other invisible character makes it unsigned."""
    m = cfg.signature.match(body or "")
    if not m:
        return None, (body or "").strip()
    return m.group("name").strip(), m.group("rest").strip()


def strip_invisible(text):
    """Drop leading whitespace and invisible characters (byte-order mark, zero-width marks, other C* and Z*)."""
    i = 0
    while i < len(text) and (text[i].isspace() or unicodedata.category(text[i])[0] in "CZ"):
        i += 1
    return text[i:]


def identify(cfg, name):
    """Who signed. The first part (before the middle dot) decides the format, so detection is unambiguous:
    roles, legacy names and owner names are disjoint (checked when the config loads).
      owner   - the whole signature is one of owner_signers, e.g. **Program Owner:**
      role    - new format **<Role> · <Vendor>:**, exactly two parts, a known role and a known vendor name
      legacy  - old format **<Name> · <job>:** (or **<Name>:**), the first part is in legacy_signers
    Anything else is an unknown signer: never an approval, never a go."""
    key = _key(name)
    if key in cfg.owner_keys:
        return Signer(name, "owner")
    parts = [p.strip() for p in " ".join(name.split()).split(SEP)]
    first = _key(parts[0])
    if first in cfg.role_by_key:
        if len(parts) == 2 and _key(parts[1]) in cfg.vendor_by_name:
            return Signer(name, "role", cfg.vendor_by_name[_key(parts[1])], cfg.role_by_key[first])
        return Signer(name)
    if first in cfg.legacy:
        return Signer(name, "legacy", cfg.legacy[first])
    return Signer(name)


def author_vendor_of(cfg, branch):
    for prefix, vendor in cfg.prefixes:
        if (branch or "").startswith(prefix):
            return vendor
    return None


def timeline(pr):
    """Comments and review bodies, oldest first. Hidden (minimized) comments are ignored."""
    items = []
    for cm in pr.get("comments") or []:
        if cm.get("isMinimized"):
            continue
        items.append({"body": cm.get("body") or "", "when": cm.get("createdAt") or "",
                      "author": (cm.get("author") or {}).get("login") or ""})
    for rv in pr.get("reviews") or []:
        if rv.get("body"):
            items.append({"body": rv["body"], "when": rv.get("submittedAt") or "",
                          "author": (rv.get("author") or {}).get("login") or ""})
    items.sort(key=lambda i: i["when"])
    return items


def signal_problems(cfg, body, head):
    """Why this comment's signal does not count although it looks like one, or []. This is the enforcer for
    'the verdict is the first words after the signature' and 'no byte-order mark'."""
    problems = []
    name, rest = split_signature(cfg, body)
    if name is None:
        clean = strip_invisible(body)
        lead = body[:len(body) - len(clean)]
        if any(not c.isspace() for c in lead) and cfg.signature.match(clean):
            problems.append("starts with an invisible character (for example a byte-order mark) before the "
                            "signature, so it is unsigned and counts for nothing")
            return problems
        text, start_ok = body, False
    else:
        text, start_ok = rest, bool(cfg.verdict.match(rest))
    for m in VERDICT_ANYWHERE.finditer(text):
        if start_ok and m.start() == 0:
            continue
        sha = m.group(2).lower()
        if not (head and head.startswith(sha)):
            continue
        if name is None:
            problems.append("carries a verdict for the head commit but has no signature")
        elif m.start() == 0 and len(sha) < cfg.sha_min:
            problems.append(f"gives a commit id of {len(sha)} characters; the verdict needs at least {cfg.sha_min}")
        else:
            problems.append("has a verdict for the head commit that is not the first words after the signature")
        break
    return problems


def account_problem(cfg, signer, login):
    """Why this GitHub account may not speak as this signer, or None. A signer with no configured logins is
    trusted on its signature text alone (the shared-account case)."""
    if signer.kind == "owner":
        allowed, who = cfg.owner_logins, "the owner"
    elif signer.vendor is not None:
        allowed, who = cfg.vendor_logins.get(signer.vendor, set()), f"vendor {signer.vendor}"
    else:
        return None
    if not allowed or (login or "").lower() in allowed:
        return None
    return f"is signed as {signer.name} but was posted by {login or 'an unknown account'}, which is not one of {who}'s configured logins"


def read_signals(pr, cfg, head=""):
    """Parse the conversation into the latest verdict per signer, plan 'go' signers, hold state and the
    comments whose signal does not count although it looks like one."""
    latest, go_by, held, held_by, problems = {}, {}, False, None, []
    verdict_login, go_login = {}, {}
    for it in timeline(pr):
        body = it["body"]
        name, rest = split_signature(cfg, body)
        # A hold is a brake: it counts even behind an invisible character or without a signature.
        h_name, h_rest = split_signature(cfg, strip_invisible(body))
        if HOLD.match(h_rest):
            held, held_by = True, h_name or "an unsigned comment"
        elif UNHOLD.match(rest) and name and identify(cfg, name).kind == "owner" \
                and account_problem(cfg, identify(cfg, name), it["author"]) is None:
            held, held_by = False, None
        for why in signal_problems(cfg, body, head):
            problems.append(f"comment by {name or h_name or 'an unsigned author'} at {it['when'] or '?'} {why}")
        if not name:
            continue
        signer = identify(cfg, name)
        m = cfg.verdict.match(rest)
        if m or GO.match(rest):
            bad = account_problem(cfg, signer, it["author"])
            if bad:
                problems.append(f"comment by {name} at {it['when'] or '?'} {bad}, so its signal counts for nothing")
                continue
        login = (it["author"] or "").lower()
        if m:
            latest[signer.key] = (signer, "approve" if m.group(1).lower() == "approved" else "reject",
                                  m.group(2).lower())
            verdict_login[signer.key] = login
        if GO.match(rest):
            go_by[signer.key] = signer
            go_login[signer.key] = login
    return {"latest": latest, "go_by": go_by, "held": held, "held_by": held_by, "problems": problems,
            "verdict_login": verdict_login, "go_login": go_login}


# ---------------------------------------------------------------- fetching the pull request

def repo_of(gh, cfg):
    repo = cfg.repo or gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()
    if not repo:
        raise GateError("could not detect the repository; run inside the repo folder or set 'repo' in the config")
    if not isinstance(repo, str) or not REPO_NAME.fullmatch(repo) or repo.startswith("-") \
            or any(part in (".", "..") for part in repo.split("/")):
        raise GateError(f"the repository name {repo!r} is not a plain owner/name; refusing to continue")
    cfg.repo = repo
    return repo


def parse_json_pages(raw):
    """Read the output of `gh api --paginate`: one JSON array per page, written one after another, a single
    array, or an array of arrays (`--slurp`). Anything else is refused: never read 'nothing useful' as 'no files'."""
    raw = raw or ""
    if not raw.strip():
        raise GateError("the changed-file list came back empty; cannot verify the files")
    dec, pos, items = json.JSONDecoder(), 0, []
    while True:
        while pos < len(raw) and raw[pos].isspace():
            pos += 1
        if pos >= len(raw):
            return items
        try:
            page, pos = dec.raw_decode(raw, pos)
        except ValueError as exc:
            raise GateError(f"the changed-file list is not valid JSON ({exc}); cannot verify the files")
        if not isinstance(page, list):
            raise GateError("the changed-file list is not a JSON array (got an error or another object); "
                            "cannot verify the files")
        if page and all(isinstance(e, list) for e in page):
            page = [entry for sub in page for entry in sub]
        for entry in page:
            if not isinstance(entry, dict):
                raise GateError("the changed-file list has an entry that is not an object; cannot verify the files")
            items.append(entry)


def fetch_files(gh, repo, number):
    """The complete changed-file list, page by page; every entry strictly validated."""
    raw = gh(["api", f"repos/{repo}/pulls/{number}/files?per_page=100", "--paginate"])
    files, seen = [], set()
    for entry in parse_json_pages(raw):
        name = entry.get("filename")
        if bad_path(name):
            raise GateError(f"the changed-file list has a file name that {bad_path(name)}: {name!r}; cannot verify the files")
        if name in seen:
            raise GateError(f"the changed-file list names '{name}' twice; cannot verify the files")
        seen.add(name)
        status = entry.get("status")
        if not isinstance(status, str) or status not in FILE_STATUSES:
            raise GateError(f"the changed-file list gives no usable status for '{name}'; cannot verify the files")
        rec = {"path": name, "status": status}
        prev = entry.get("previous_filename")
        if prev is not None:
            if bad_path(prev):
                raise GateError(f"the changed-file list has an old name for '{name}' that {bad_path(prev)}; "
                                "cannot verify the files")
            rec["previous_path"] = prev
        elif status in NEEDS_OLD_NAME:
            raise GateError(f"'{name}' is {status} but the list gives no old name; cannot verify the files")
        files.append(rec)
    return files


def fetch_pr(gh, cfg, number):
    """The pull request plus its complete file list, pinned: the fields that say which diff it is are read
    before and after the list, and any difference (or any of them being unreadable) refuses the read. The second
    read is the full one and is what gets judged, so a hold, label or check that lands while the list is being
    read counts. The remote read and the merge still cannot be made atomic; the merge pins the head commit."""
    repo = repo_of(gh, cfg)
    pr = json.loads(gh(["pr", "view", str(number), "--repo", repo, "--json", VIEW_FIELDS]))
    check_identity(pr, number, "first")
    files = fetch_files(gh, repo, number)
    after = json.loads(gh(["pr", "view", str(number), "--repo", repo, "--json", VIEW_FIELDS]))
    check_identity(after, number, "second")
    if any(type(after[k]) is not type(pr[k]) or after[k] != pr[k] for k in SNAPSHOT_FIELDS):
        raise GateError("the pull request changed while its file list was being read (its base, head or file count "
                        "moved); run the check again")
    after["files"] = files
    return after


# ---------------------------------------------------------------- check

def evaluate(pr, cfg):
    results, notes = [], []

    def add(rule, ok, msg):
        results.append({"rule": rule, "ok": bool(ok), "msg": msg})

    head = pr.get("headRefOid") or ""
    branch = pr.get("headRefName") or ""
    records = pr.get("files") or []
    files, problems, new_names = [], [], []
    for rec in records:
        path = rec.get("path") if isinstance(rec, dict) else None
        prev = rec.get("previous_path") if isinstance(rec, dict) else None
        status = rec.get("status") if isinstance(rec, dict) else None
        if bad_path(path):
            problems.append(f"a file name {bad_path(path)}: {path!r}")
        elif prev is not None and bad_path(prev):
            problems.append(f"'{path}' has an old name that {bad_path(prev)}")
        elif isinstance(rec, dict) and "status" in rec and status not in FILE_STATUSES:
            problems.append(f"'{path}' has an unknown status")
        elif status in NEEDS_OLD_NAME and not prev:
            problems.append(f"'{path}' is {status} but has no old name")
        else:
            new_names.append(path)
            files.extend([path] + ([prev] if prev else []))
    files = list(dict.fromkeys(files))
    if len(set(new_names)) != len(new_names):
        problems.append("a path is listed twice")
    expected = pr.get("changedFiles")
    count_ok = _is_int(expected) and expected >= 0
    labels = [lb.get("name") for lb in (pr.get("labels") or [])]
    sig = read_signals(pr, cfg, head)
    a_vendor = author_vendor_of(cfg, branch)
    owner_list = ", ".join(cfg.owner_signers)

    add("state", pr.get("state") == "OPEN" and not pr.get("isDraft") and pr.get("baseRefName") == cfg.base,
        f"PR is {pr.get('state')}{' (draft)' if pr.get('isDraft') else ''} into {pr.get('baseRefName')}; "
        f"needs to be open, not draft, into {cfg.base}")

    hold_label = cfg.hold_label in labels
    add("hold", not (sig["held"] or hold_label),
        "no hold" if not (sig["held"] or hold_label) else
        (f"the '{cfg.hold_label}' label is on; remove it to continue" if hold_label else
         f"on hold ({sig['held_by']}); a comment from the owner ({owner_list}) starting with 'unhold' lifts it"))

    add("signals", not sig["problems"],
        "every signal is well formed" if not sig["problems"] else
        "; ".join(sig["problems"][:3]) + (" ..." if len(sig["problems"]) > 3 else "")
        + ". Post the signal again with the verdict as the first words after the signature, no byte-order "
          "mark, and hide (minimize) the faulty comment")

    if cfg.forbidden_head_prefixes:
        bad_head = [p for p in cfg.forbidden_head_prefixes if branch.startswith(p)]
        add("branch", not bad_head, "head branch may be a PR head" if not bad_head else
            f"branch '{branch}' starts with '{bad_head[0]}', which may not be a pull request head")

    # tier
    tier_labels = [t for t in labels if t in cfg.tier_by_label]
    tier = None
    if len(tier_labels) != 1:
        add("tier", False, f"needs exactly one tier label ({', '.join(cfg.tier_by_label)}), found {tier_labels or 'none'}")
    else:
        tier = cfg.tier_by_label[tier_labels[0]]
        msgs = [tier.label]
        if tier.mergeable:
            protected = [f for f in files if match_any(f, cfg.protected_paths, fold=True)]
            if protected and tier.level < cfg.protected_tier:
                tier = cfg.tier_at(cfg.protected_tier)
                msgs = [f"{tier_labels[0]} raised to {tier.label} because it touches protected paths: "
                        f"{', '.join(protected[:3])}{' ...' if len(protected) > 3 else ''}"]
            while tier is not None and tier.mergeable and tier.allowed_paths is not None \
                    and any(not match_any(f, tier.allowed_paths) for f in files):
                was, tier = tier, cfg.tier_above(tier)
                msgs.append(f"{was.label} raised to {tier.label if tier else 'nothing higher'} because it changes "
                            f"files outside {', '.join(was.allowed_paths)}")
        if tier is None:
            add("tier", False, "; ".join(msgs) + "; no tier covers this change")
        elif not tier.mergeable:
            if tier.label == tier_labels[0]:
                msgs = []
            add("tier", False, "; ".join(msgs + [f"{tier.label} is human only: agents and this gate never merge it"]))
            tier = None
        else:
            add("tier", True, "; ".join(msgs))

    # files
    if max(len(records), expected if count_ok else 0) >= MAX_FILES:
        add("files", False, f"{MAX_FILES} or more changed files: the file list cannot be fully verified; split the change")
    elif not count_ok:
        add("files", False, "GitHub's changed-file count is missing, so the file list cannot be verified as complete")
    elif problems:
        add("files", False, f"the file list is malformed ({problems[0]}); it cannot be verified")
    elif len(new_names) != expected:
        add("files", False, f"the file list has {len(new_names)} files but GitHub counts {expected}; "
            "it may be incomplete, so it cannot be verified")
    else:
        bad = [f for f in files if match_any(f, cfg.forbidden_globs, fold=True) and not match_any(f, cfg.scan_allow)]
        add("files", not bad, "no forbidden files" if not bad else f"forbidden files changed: {', '.join(bad[:5])}")

    if len(pr.get("comments") or []) >= MAX_COMMENTS:
        add("comments", False, f"{MAX_COMMENTS} or more comments: the conversation cannot be fully read; open a fresh PR")

    rollup = pr.get("statusCheckRollup") or []
    for name in cfg.required_checks:
        entries = [c for c in rollup if (c.get("name") or c.get("context")) == name]
        okay = bool(entries) and all(
            (c.get("conclusion") == "SUCCESS" if c.get("__typename", "CheckRun") == "CheckRun"
             else c.get("state") == "SUCCESS") for c in entries)
        add(f"check:{name}", okay, "passed on the head commit" if okay else
            ("not found on the head commit" if not entries else "not successful on the head commit"))

    if tier is None:
        return _finish(results, notes, head, tier, [], False, a_vendor, branch, pr, cfg)

    if tier.body_headings:
        body = pr.get("body") or ""
        for heading in cfg.body_headings:
            has = re.search(rf"(?im)^#{{1,6}}\s*{re.escape(heading)}\b", body) is not None
            add(f"evidence:{heading}", has, "present in the PR body" if has else "missing heading in the PR body")

    if a_vendor is None and (tier.plan_go or tier.approvals > 0):
        add("author", False, f"branch '{branch}' does not start with a vendor's branch prefix "
            f"({', '.join(p for p, _ in cfg.prefixes)}); the gate cannot tell which vendor wrote it")

    author_login = ((pr.get("author") or {}).get("login") or "").lower()

    def own_account(signer, logins):
        """With distinct_accounts, a signal must come from a known GitHub account other than the PR author's."""
        if not cfg.distinct_accounts:
            return False
        login = logins.get(signer.key, "")
        return not login or login == author_login

    def independent(signer, logins):
        if signer.vendor is None or a_vendor is None:
            return False
        if own_account(signer, logins):
            return False
        if signer.kind == "role" and cfg.approver_roles is not None and _key(signer.role) not in cfg.approver_roles:
            return False
        if signer.vendor != a_vendor:
            return True
        return not tier.cross_vendor and signer.key in cfg.same_vendor_reviewers

    if tier.plan_go:
        goers = sorted(s.name for s in sig["go_by"].values() if independent(s, sig["go_login"]) or s.kind == "owner")
        add("plan", bool(goers), f"plan 'go' from {', '.join(goers)}" if goers else
            f"no plan 'go' from the other vendor's reviewer (or the owner: {owner_list}); "
            "the comment must start with the word go")

    approvers, blockers, ignored = [], [], []
    for _, (signer, kind, sha) in sorted(sig["latest"].items()):
        matches = bool(head) and head.startswith(sha)
        if kind == "reject":
            if matches:
                blockers.append(signer.name)
            continue
        if signer.kind == "owner":
            continue
        if not matches:
            ignored.append(f"{signer.name} approved an older commit")
        elif not signer.known:
            ignored.append(f"{signer.name} is not a known signer")
        elif not independent(signer, sig["verdict_login"]):
            ignored.append(f"{signer.name} is not an independent reviewer for this branch at {tier.label}"
                           + ("; it was posted from the PR author's account or an unknown one" if own_account(signer, sig["verdict_login"]) else ""))
        else:
            approvers.append(signer.name)
    if tier.approvals or approvers or blockers:
        add("review", len(approvers) >= tier.approvals and not blockers,
            f"{len(approvers)} of {tier.approvals} independent approval(s) at the head commit"
            + (f" by {', '.join(approvers)}" if approvers else "")
            + (f"; not approved by {', '.join(blockers)}" if blockers else "")
            + (f"; ignored: {'; '.join(ignored)}" if ignored else ""))

    owner_ok = any(s.kind == "owner" and k == "approve" and head.startswith(sha)
                   for s, k, sha in sig["latest"].values())
    if tier.owner_approval:
        add("owner", owner_ok, "the owner approved at the head commit" if owner_ok else
            f"{tier.label} needs the owner's comment: **{cfg.owner_signers[0]}:** Approved at <full commit id>, "
            "matching the current head")

    return _finish(results, notes, head, tier, approvers, owner_ok, a_vendor, branch, pr, cfg)


def _finish(results, notes, head, tier, approvers, owner_ok, a_vendor, branch, pr, cfg):
    if cfg.shared_account:
        notes.append("Approvals are comments from one shared account, so the gate cannot prove which person or "
                     "agent wrote them. It records them; the audit and the owner's hold are the backstop.")
    return {
        "head": head, "tier": tier, "tier_label": tier.label if tier else None, "branch": branch,
        "author_vendor": a_vendor, "title": pr.get("title", ""), "results": results,
        "passed": all(r["ok"] for r in results), "approvers": approvers,
        "owner_approved": owner_ok, "notes": notes,
    }


def passed_ignoring(ev, *ignore):
    """Whether every rule not named in ignore passed. For a pre-review CI gate (R16 "process gates up
    front"): check everything the gate can verify at PR-open time, without needing review or owner
    approval to exist yet. Typical call: passed_ignoring(ev, "review", "owner")."""
    ignored = set(ignore)
    relevant = [r for r in ev["results"] if r["rule"] not in ignored]
    return all(r["ok"] for r in relevant)


def format_report(ev, number):
    lines = [f"PR #{number}  head {ev['head'][:8]}  branch {ev['branch']}  tier {ev['tier_label']}  "
             f"author vendor {ev['author_vendor']}"]
    for r in ev["results"]:
        lines.append(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['rule']}: {r['msg']}")
    lines.append("RESULT: " + ("PASS" if ev["passed"] else "FAIL"))
    for n in ev["notes"]:
        lines.append("NOTE: " + n)
    return "\n".join(lines)


def cmd_check(gh, cfg, number, out=print, ignore=()):
    ev = evaluate(fetch_pr(gh, cfg, number), cfg)
    out(format_report(ev, number))
    if ignore:
        ok = passed_ignoring(ev, *ignore)
        out(f"PRE-REVIEW RESULT (ignoring {', '.join(ignore)}): " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    return 0 if ev["passed"] else 1


# ---------------------------------------------------------------- merge

def validate_merger(cfg, merged_as):
    if not merged_as or not merged_as.strip():
        raise GateError(f"--as is required, for example --as \"Release Manager {SEP} <vendor>\"")
    if "\n" in merged_as or "\r" in merged_as:
        raise GateError("--as must be one line")
    signer = identify(cfg, merged_as.strip())
    if not signer.known:
        raise GateError(f"'{merged_as}' is not a known signer: write it as '<Role> {SEP} <Vendor>' with a role "
                        f"from the config, or as an owner name ({', '.join(cfg.owner_signers)})")
    if signer.kind == "legacy" and SEP not in merged_as:
        raise GateError(f"'{merged_as}' needs the job after the dot, like: {merged_as.strip()} {SEP} <job>")
    if signer.kind == "role" and cfg.merger_roles is not None and _key(signer.role) not in cfg.merger_roles:
        raise GateError(f"the role '{signer.role}' may not merge; the config allows only its merger_roles")
    return signer


def cmd_merge(gh, cfg, number, merged_as, dry_run=False, out=print):
    signer = validate_merger(cfg, merged_as)
    ev = evaluate(fetch_pr(gh, cfg, number), cfg)
    out(format_report(ev, number))
    if not ev["passed"]:
        return 1
    if signer.kind != "owner":
        if signer.vendor != ev["author_vendor"]:
            raise GateError(f"the author's vendor merges: this PR is on a {ev['author_vendor']} branch "
                            f"({ev['branch']}), so '{merged_as}' cannot merge it")
        if signer.key in {_key(a) for a in ev["approvers"]}:
            raise GateError("a reviewer who approved this PR cannot also merge it")
    head = ev["head"]
    record = (f"Gate-Record: pass tier={ev['tier'].record} head={head} "
              f"reviewers={'; '.join(ev['approvers']) or 'none'} "
              f"owner={'yes' if ev['owner_approved'] else 'no'} by={merged_as.strip()}")
    cmd = ["pr", "merge", str(number), "--repo", repo_of(gh, cfg), "--squash",
           "--match-head-commit", head, "--subject", f"{ev['title']} (#{number})", "--body", record]
    if dry_run:
        out("DRY RUN: gh " + " ".join(shlex.quote(c) for c in cmd))
        return 0
    gh(cmd)
    out(f"Merged PR #{number} at {head[:8]}. {record}")
    return 0


# ---------------------------------------------------------------- audit

OWNER_YES = re.compile(r" owner=yes by=")


def cmd_audit(git, cfg, rng, out=print):
    zeros = re.match(r"^0+\.\.(.+)$", rng or "")
    args = ["log", "--first-parent", "--format=%H%x1f%an%x1f%s%x1f%b%x1e"]
    args += ["-n", "1", zeros.group(1)] if zeros else [rng]
    flagged, owner_merges = [], []
    for rec in git(args).split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, author, subject, body = (rec.split("\x1f") + ["", "", "", ""])[:4]
        if sha in cfg.audit_exempt:
            continue
        m = cfg.trailer.search(body)
        if not m:
            flagged.append((sha, author, subject, "no gate record"))
            continue
        tier = cfg.tier_by_record[m.group(1)]
        if tier.owner_approval:
            if not OWNER_YES.search(m.group(3)):
                flagged.append((sha, author, subject, f"{tier.label} record without owner approval"))
            else:
                owner_merges.append((sha, subject))
    if flagged:
        out("GATE BYPASSED: these commits on the base branch need a look:")
        for sha, author, subject, why in flagged:
            out(f"  {sha[:8]}  {author}  {subject}  ({why})")
    else:
        out("Audit clean: every commit in the range has a gate record.")
    if owner_merges:
        out("Owner-approval merges in this range (owner: confirm you approved each one):")
        for sha, subject in owner_merges:
            out(f"  {sha[:8]}  {subject}")
    return 1 if flagged else 0


# ---------------------------------------------------------------- scan

def decode_text(data):
    """The text of a file, or None when it is binary. UTF-16 (a byte-order mark, or NUL bytes on one parity only,
    which is what ASCII-heavy UTF-16 looks like) is text: Windows tools write it by default."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    sample = data[:8192]
    if b"\x00" not in sample:
        return data.decode("utf-8", errors="replace")
    odd, even, half = sample[1::2].count(0), sample[0::2].count(0), len(sample) // 2
    if half and max(odd, even) >= half * 0.3 and min(odd, even) <= half * 0.02:
        return data.decode("utf-16-le" if odd > even else "utf-16-be", errors="replace")
    return None


def scan_blob(path, data, cfg):
    problems = []
    if not match_any(path, cfg.scan_allow):
        if match_any(path, cfg.forbidden_globs, fold=True):
            problems.append("forbidden file name")
        for magic, kind in cfg.magic:
            if data.startswith(magic):
                problems.append(f"content is a {kind}")
                break
        if len(data) > cfg.max_file_mb * 1024 * 1024:
            problems.append(f"larger than {cfg.max_file_mb} MB")
    text = decode_text(data)
    if text is not None:  # secrets are looked for even in allowed text files
        for rx, label in cfg.secrets:
            if rx.search(text):
                problems.append(f"looks like: {label}")
    return problems


def scan_history(git, cfg, commits):
    """Scan every file version that any of these commits adds or changes, so a file added in one commit and
    removed in the next is still seen."""
    bad, seen = [], set()
    for commit in commits:
        raw = git(["diff-tree", "-r", "-m", "--root", "-z", "--no-commit-id", "--diff-filter=ACMR", commit])
        tokens = [t for t in raw.split("\0") if t]
        for meta, path in zip(tokens[0::2], tokens[1::2]):
            blob = meta.split()[3]  # ":old-mode new-mode old-sha new-sha status"
            if (blob, path) in seen:
                continue
            seen.add((blob, path))
            for problem in scan_blob(path, git(["cat-file", "blob", blob], binary=True), cfg):
                bad.append((f"{path} (commit {commit[:7]})", problem))
    return bad


def cmd_scan(git, cfg, staged=False, rev="HEAD", rng=None, outgoing=None, out=print):
    bad = []
    if rng or outgoing:
        if rng:
            if rng.count("..") != 1 or "..." in rng:
                raise GateError("--range must be A..B")
            a, b = rng.split("..")
            args = ["rev-list", "--reverse", f"{a}..{b}"]
        else:  # commits no remote branch has yet: what a push of this revision would upload
            args = ["rev-list", "--reverse", outgoing, "--not", "--remotes"]
        bad = scan_history(git, cfg, git(args).split())
    else:
        # -z: without it git quotes non-ASCII names ("caf\303\251.txt") and `git show` cannot find them.
        if staged:
            names = git(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]).split("\0")
            spec = lambda p: ":" + p
        else:
            names = git(["ls-tree", "-r", "-z", "--name-only", rev]).split("\0")
            spec = lambda p: f"{rev}:{p}"
        for path in [n for n in names if n]:
            for problem in scan_blob(path, git(["show", spec(path)], binary=True), cfg):
                bad.append((path, problem))
    if bad:
        out("SCAN FAILED:")
        for path, problem in bad:
            out(f"  {path}: {problem}")
    else:
        out("Scan clean.")
    return 1 if bad else 0


# ---------------------------------------------------------------- paths

def cmd_paths(git, cfg, out=print):
    tracked = [n for n in git(["ls-files", "-z"]).split("\0") if n]
    out(f"{len(tracked)} tracked files. Protected paths (a change to any of them is at least "
        f"{cfg.tier_at(cfg.protected_tier).label}):")
    empty = 0
    for g in cfg.protected_paths:
        n = sum(1 for p in tracked if match_any(p, [g], fold=True))
        out(f"  {n:4d}  {g}")
        empty += n == 0
    if empty:
        out(f"{empty} protected path(s) match no file today. Fine for paths that will exist later; "
            "otherwise correct the name in the gate config.")
    return 0


# ---------------------------------------------------------------- cli

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="gate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None,
                    help="the project's gate config (default: <repo top>/.orchestration/gate.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("pr", type=int)
    c.add_argument("--ignore", default="", help="comma-separated rule names to exclude from pass/fail "
                   "(e.g. review,owner for a pre-review CI gate run before anyone has reviewed)")
    m = sub.add_parser("merge")
    m.add_argument("pr", type=int)
    m.add_argument("--as", dest="merged_as", required=True,
                   help=f'who merges, for example "Release Manager {SEP} <Vendor>"')
    m.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("audit")
    a.add_argument("--range", required=True, help="A..B of commits to audit")
    s = sub.add_parser("scan")
    s.add_argument("--staged", action="store_true")
    s.add_argument("--rev", default="HEAD")
    s.add_argument("--range", help="A..B: scan every commit in the range")
    s.add_argument("--outgoing", help="REV: scan every commit of REV that no remote branch has yet")
    sub.add_parser("paths")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config or default_config_path())
        if args.cmd == "check":
            ignore = [r for r in args.ignore.split(",") if r]
            return cmd_check(run_gh, cfg, args.pr, ignore=ignore)
        if args.cmd == "merge":
            return cmd_merge(run_gh, cfg, args.pr, args.merged_as, args.dry_run)
        if args.cmd == "audit":
            return cmd_audit(run_git, cfg, args.range)
        if args.cmd == "paths":
            return cmd_paths(run_git, cfg)
        return cmd_scan(run_git, cfg, args.staged, args.rev, args.range, args.outgoing)
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
