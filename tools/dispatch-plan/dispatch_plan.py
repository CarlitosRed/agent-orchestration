#!/usr/bin/env python3
"""Check a proposed dispatch plan before launching workers; no launch or filesystem lock.

Usage: dispatch_plan.py check PLAN.json
Exit 0: declared plan is consistent; 1: coordination conflict; 2: file/format error.
Resources, workspace IDs and branch IDs are logical labels, not filesystem paths.
"""
import argparse
import json
import re
import sys

SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
SCOPE = re.compile(r"[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*\Z")
PLAN_FIELDS = {"schema_version", "base_sha", "goal", "integration_check", "max_parallel", "jobs"}
JOB_FIELDS = {"id", "role", "provider", "model", "access", "workspace_id", "branch_id",
              "write_scopes", "depends_on", "output", "proof"}


class Broken(Exception):
    """Invalid input representation."""


class Conflict(Exception):
    """The declared dispatch cannot safely run in its proposed dependency order."""


def fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise Broken(f"{label}: expected fields {', '.join(sorted(expected))}")


def text(value, label):
    if (not isinstance(value, str) or not value.strip()
            or any(ord(c) < 32 or ord(c) == 127 or c in "\x85\u2028\u2029" for c in value)):
        raise Broken(f"{label}: expected non-empty single-line text")
    return value


def slug(value, label):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise Broken(f"{label}: expected lowercase logical ID (letters, digits, underscore, hyphen)")


def id_list(value, label, pattern):
    if not isinstance(value, list) or any(not isinstance(v, str) or not pattern.fullmatch(v) for v in value):
        raise Broken(f"{label}: invalid logical ID list")
    if len(value) != len(set(value)):
        raise Broken(f"{label}: duplicate entries")


def overlaps(left, right):
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def validate(plan):
    fields(plan, PLAN_FIELDS, "plan")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise Broken("schema_version must be integer 1")
    if not isinstance(plan["base_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", plan["base_sha"]):
        raise Broken("base_sha must be a full lowercase 40-character SHA")
    for name in ("goal", "integration_check"):
        text(plan[name], name)
    if type(plan["max_parallel"]) is not int or plan["max_parallel"] < 1:
        raise Broken("max_parallel must be a positive integer")
    if not isinstance(plan["jobs"], list) or not plan["jobs"]:
        raise Broken("jobs must be a non-empty list")
    jobs = {}
    for job in plan["jobs"]:
        fields(job, JOB_FIELDS, "job")
        slug(job["id"], "job.id")
        if job["id"] in jobs:
            raise Conflict(f"duplicate worker ID: {job['id']}")
        jobs[job["id"]] = job
        for name in ("role", "provider", "model", "output", "proof"):
            text(job[name], f"{job['id']}.{name}")
        slug(job["workspace_id"], f"{job['id']}.workspace_id")
        if job["access"] not in ("read-only", "write"):
            raise Broken(f"{job['id']}: access must be read-only or write")
        id_list(job["write_scopes"], f"{job['id']}.write_scopes", SCOPE)
        id_list(job["depends_on"], f"{job['id']}.depends_on", SLUG)
        if job["access"] == "write":
            slug(job["branch_id"], f"{job['id']}.branch_id")
            if not job["write_scopes"]:
                raise Broken(f"{job['id']}: writer must declare its write scopes")
        elif job["write_scopes"] or job["branch_id"] is not None:
            raise Broken(f"{job['id']}: read-only job must have no write scopes or branch ID")
    for job in jobs.values():
        missing = set(job["depends_on"]) - jobs.keys()
        if missing:
            raise Conflict(f"{job['id']}: unknown dependencies: {', '.join(sorted(missing))}")
    ancestors, batches, done = {}, [], set()
    while len(done) < len(jobs):
        ready = sorted(k for k, j in jobs.items() if k not in done and set(j["depends_on"]) <= done)
        if not ready:
            raise Conflict("dependency cycle: " + ", ".join(sorted(jobs.keys() - done)))
        batch = ready[:plan["max_parallel"]]
        for key in batch:
            ancestors[key] = set(jobs[key]["depends_on"])
            for dep in jobs[key]["depends_on"]:
                ancestors[key].update(ancestors[dep])
        done.update(batch)
        batches.append(batch)
    values = list(jobs.values())
    for i, left in enumerate(values):
        for right in values[i + 1:]:
            # Incidental batching or a temporary concurrency limit is not an ownership dependency.
            if left["id"] in ancestors[right["id"]] or right["id"] in ancestors[left["id"]]:
                continue
            writer = left["access"] == "write" or right["access"] == "write"
            if writer and left["workspace_id"] == right["workspace_id"]:
                raise Conflict(f"{left['id']} / {right['id']}: unordered writer shares workspace")
            if left["access"] != "write" or right["access"] != "write":
                continue
            if left["branch_id"] == right["branch_id"]:
                raise Conflict(f"{left['id']} / {right['id']}: unordered writers share branch ID")
            for a in left["write_scopes"]:
                for b in right["write_scopes"]:
                    if overlaps(a, b):
                        raise Conflict(f"{left['id']} / {right['id']}: unordered write scopes overlap: {a} / {b}")
    return {"valid": True, "base_sha": plan["base_sha"], "job_count": len(jobs),
            "proposed_batches": batches, "declared_provider_labels": sorted({j["provider"] for j in values}),
            "declared_model_pairs": sorted({(j["provider"], j["model"]) for j in values}),
            "limits": ["Declared logical resources only; no path/alias resolution or live workspace inspection.",
                       "Proposed batches assume prior work succeeds; completion is not observed.",
                       "No agent launch, authorization, locking, model availability or review-policy check.",
                       "Output/proof/integration fields are required text, not executed evidence."]}


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Broken(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_plan(path):
    with open(path, encoding="utf-8") as stream:
        content = stream.read()
    try:
        return json.loads(content, object_pairs_hook=no_duplicate_keys)
    except (ValueError, RecursionError) as exc:
        raise Broken("JSON is malformed or exceeds decoder limits") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check"])
    parser.add_argument("plan")
    args = parser.parse_args(argv)
    try:
        result = validate(load_plan(args.plan))
    except Conflict as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    except (Broken, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
