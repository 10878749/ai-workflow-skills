#!/usr/bin/env python3
"""Bounded local inventory. Reads Git metadata and explicitly named artifacts only."""

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


EXCLUDED = {".git", "node_modules", ".venv", "venv", "__pycache__",
            ".pytest_cache", ".mypy_cache", ".next"}
GIT = shutil.which("git")
MAX_STATUS_ENTRIES = 200
GIT_ERRORS = {}


def git(directory, *args):
    key = (str(directory), args)
    if not GIT:
        GIT_ERRORS[key] = {"reason": "git_unavailable"}
        return None
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    # A caller's Git selectors must not silently redirect an explicit -C target.
    for env_name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(env_name, None)
    try:
        result = subprocess.run(
            [GIT, "--no-optional-locks", "-c", "core.quotepath=false",
             "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
             "-C", str(directory), *args],
            capture_output=True, env=env, timeout=30,
        )
    except subprocess.TimeoutExpired:
        GIT_ERRORS[key] = {"reason": "git_command_timed_out"}
        return None
    except OSError:
        GIT_ERRORS[key] = {"reason": "git_process_could_not_start"}
        return None
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace").casefold()
        reason = "git_query_failed"
        for marker, label in (("permission denied", "permission_denied"),
                              ("access is denied", "permission_denied"),
                              ("dubious ownership", "git_ownership_restriction"),
                              ("not a git repository", "not_a_repository")):
            if marker in stderr:
                reason = label
                break
        GIT_ERRORS[key] = {"reason": reason, "exit_code": result.returncode}
        return None
    return result.stdout.decode("utf-8", errors="replace").rstrip("\r\n")


def status_entries(raw):
    if raw is None:
        return {"available": False}
    parts = raw.split("\0")
    entries = []
    index = 0
    while index < len(parts):
        token = parts[index]
        index += 1
        if not token:
            continue
        xy, path = token[:2], token[3:]
        entry = {"status": xy, "path": path}
        if "R" in xy or "C" in xy:
            if index < len(parts):
                entry["original_path"] = parts[index]
                index += 1
        entries.append(entry)
    return {
        "available": True,
        "clean": not entries,
        "entry_count": len(entries),
        "entries": entries[:MAX_STATUS_ENTRIES],
        "omitted_count": max(0, len(entries) - MAX_STATUS_ENTRIES),
        "untracked_directories_may_be_collapsed": True,
        "submodule_contents_checked": False,
    }


def worktrees(raw):
    if raw is None:
        return None
    result = []
    for block in raw.split("\n\n"):
        item = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key in ("worktree", "HEAD", "branch"):
                item[key] = value
            elif key in ("bare", "detached", "locked", "prunable"):
                # Reasons can contain arbitrary text; the state flag is enough.
                item[key] = True
        if item:
            result.append(item)
    return result


def repository(directory):
    top = git(directory, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    top_path = Path(top).resolve()
    if top_path != directory.resolve():
        return {"path": str(directory), "containing_repository": str(top_path),
                "inventory_expanded_to_parent": False}
    head = git(directory, "rev-parse", "--verify", "HEAD^{commit}")
    branch = git(directory, "symbolic-ref", "--quiet", "--short", "HEAD")
    upstream_ref = git(directory, "rev-parse", "--symbolic-full-name", "@{upstream}")
    upstream = None
    if upstream_ref:
        upstream = {
            "ref": upstream_ref,
            "head": git(directory, "rev-parse", "--verify", "@{upstream}^{commit}"),
            "evidence": "local_tracking_ref_not_live_remote",
        }
    return {
        "path": str(top_path), "head": head, "branch": branch,
        "detached": head is not None and branch is None,
        "unborn": head is None and branch is not None,
        "working_tree": status_entries(git(
            directory, "status", "--porcelain=v1", "-z",
            "--untracked-files=normal", "--ignore-submodules=all")),
        "upstream": upstream,
        "worktrees": worktrees(git(directory, "worktree", "list", "--porcelain")),
    }


def is_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def inspect_root(raw_path, max_depth, budget):
    root = Path(raw_path).expanduser().resolve()
    result = {"path": str(root), "repositories": [], "observations": [],
              "scanned_directories": 0, "skipped_link_directories": 0,
              "depth_limited_directories": 0, "budget_exhausted": False,
              "excluded_directory_names": sorted(EXCLUDED)}
    if not root.is_dir():
        result["error"] = "requested_directory_missing_or_not_a_directory"
        return result
    root_repo = repository(root)
    if root_repo is None:
        result["repository_probe"] = GIT_ERRORS.get(
            (str(root), ("rev-parse", "--show-toplevel")),
            {"reason": "repository_identity_not_verified"})
    if root_repo:
        if "containing_repository" in root_repo:
            result["containing_repository"] = root_repo["containing_repository"]
            result["inventory_expanded_to_parent"] = False
        else:
            result["repositories"].append(root_repo)
    if (root / ".git").exists() and not root_repo:
        result["observations"].append({"path": str(root),
            "state": "git_entry_present_but_unreadable",
            "diagnostic": result.get("repository_probe")})
    pending = deque([(root, 0)])
    while pending:
        if result["scanned_directories"] >= budget:
            result["budget_exhausted"] = True
            break
        current, depth = pending.popleft()
        result["scanned_directories"] += 1
        if current != root and (current / ".git").exists():
            info = repository(current)
            if info:
                result["repositories"].append(info)
            else:
                result["observations"].append({"path": str(current),
                    "state": "git_entry_present_but_unreadable",
                    "diagnostic": GIT_ERRORS.get(
                        (str(current), ("rev-parse", "--show-toplevel")))})
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.casefold())
            for child in children:
                if child.name.casefold() in EXCLUDED:
                    continue
                if is_link(child):
                    result["skipped_link_directories"] += 1
                    continue
                if not child.is_dir():
                    continue
                if depth >= max_depth:
                    result["depth_limited_directories"] += 1
                    continue
                pending.append((child, depth + 1))
        except OSError:
            result["observations"].append({"path": str(current),
                                           "state": "directory_not_readable"})
    result["discovery_is_exhaustive"] = False
    return result


def artifact(raw_path):
    path = Path(raw_path).expanduser().resolve()
    result = {"path": str(path)}
    try:
        if not path.is_file():
            result["error"] = "requested_artifact_missing_or_not_a_file"
            return result
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
        result.update({
            "size_bytes": after.st_size, "sha256": digest.hexdigest(),
            "modified_at_utc": datetime.fromtimestamp(
                after.st_mtime, timezone.utc).isoformat(),
            "changed_while_hashing": (before.st_size, before.st_mtime_ns) !=
                                     (after.st_size, after.st_mtime_ns),
            "source_revision_proven": False,
        })
    except OSError:
        result["error"] = "requested_artifact_not_readable"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="Explicit project directories")
    parser.add_argument("--max-depth", type=int, default=2, choices=range(0, 6))
    parser.add_argument("--directory-budget", type=int, default=300)
    parser.add_argument("--artifact", action="append", default=[],
                        help="Explicit file to hash; repeat for multiple files")
    args = parser.parse_args()
    if args.directory_budget < 1:
        parser.error("--directory-budget must be positive")
    result = {
        "schema_version": 1,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {"max_depth": args.max_depth,
                  "directory_budget_per_root": args.directory_budget,
                  "network_accessed": False, "project_code_started": False,
                  "git_available": bool(GIT)},
        "roots": [inspect_root(p, args.max_depth, args.directory_budget) for p in args.roots],
        "artifacts": [artifact(p) for p in args.artifact],
    }
    if not GIT:
        result["warning"] = "git_unavailable_repository_identity_not_verified"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    incomplete = any("error" in x for x in result["roots"] + result["artifacts"])
    for root in result["roots"]:
        if root.get("repository_probe", {}).get("reason") not in (None, "not_a_repository"):
            incomplete = True
        if root.get("observations"):
            incomplete = True
        if any(not repo.get("working_tree", {}).get("available", True)
               for repo in root.get("repositories", [])):
            incomplete = True
    return 2 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
