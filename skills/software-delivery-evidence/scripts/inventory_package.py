#!/usr/bin/env python3
"""Read-only package metadata and physical source-line inventory; no origin inference."""
import argparse
from collections import deque
import codecs
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys

EXCLUDED_DIRS = {".git", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}
PRIVATE_SUFFIXES = {".pem", ".key", ".pfx", ".p12"}
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".f", ".for", ".f90", ".f95",
    ".f03", ".f08", ".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java", ".go", ".rs",
    ".m", ".mm", ".sh", ".ps1", ".sql", ".html", ".css", ".scss", ".vue", ".svelte", ".r", ".rb"}
MAX_SOURCE_BYTES = 16 * 1024 * 1024


def link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def selector(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("module selectors must be nonempty relative paths")
    value = value.replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError("module selectors must stay inside the package")
    return str(path).rstrip("/")


def load_modules(path):
    if path is None:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list):
        raise ValueError("module mapping needs a modules array")
    seen = set()
    for item in modules:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError("every module needs a nonempty string id")
        if item["id"] in seen:
            raise ValueError("module ids must be unique")
        seen.add(item["id"])
        if not isinstance(item.get("paths"), list) or not item["paths"]:
            raise ValueError("every module needs a nonempty paths array")
        if not isinstance(item.get("exclude_paths", []), list):
            raise ValueError("exclude_paths must be an array")
        item["paths"] = [selector(p) for p in item["paths"]]
        item["exclude_paths"] = [selector(p) for p in item.get("exclude_paths", [])]
    return modules


def matches(path, prefix):
    return prefix == "." or path == prefix or path.startswith(prefix + "/")


def inspect_file(path, root, encoding):
    rel = path.relative_to(root).as_posix()
    before = path.stat()
    digest = hashlib.sha256()
    source = path.suffix.lower() in SOURCE_SUFFIXES
    chunks = [] if source and before.st_size <= MAX_SOURCE_BYTES else None
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
    after = path.stat()
    changed = (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino)
    record = {"path": rel, "bytes": after.st_size, "sha256": digest.hexdigest(),
              "source_by_extension": source, "physical_lines": None, "changed_while_reading": changed}
    if source:
        if changed:
            record["line_count_reason"] = "file_changed"
        elif chunks is None:
            record["line_count_reason"] = "source_exceeds_16_mib"
        else:
            raw = b"".join(chunks)
            chosen = ("utf-32" if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)) else
                      "utf-16" if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else
                      "utf-8-sig" if raw.startswith(codecs.BOM_UTF8) else encoding)
            try:
                text = raw.decode(chosen)
                if "\0" in text:
                    raise ValueError("NUL in decoded source")
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                record["physical_lines"] = text.count("\n") + int(bool(text) and not text.endswith("\n"))
                record["source_encoding"] = chosen
            except (UnicodeError, ValueError):
                record["line_count_reason"] = "undecodable_or_binary_like_source"
    return record


def summarize(records):
    unique = {}
    for item in records:
        previous = unique.get(item["sha256"])
        if previous is None or (previous["physical_lines"] is None and item["physical_lines"] is not None):
            unique[item["sha256"]] = item
    return {"files_by_path": len(records), "bytes_by_path": sum(x["bytes"] for x in records),
        "known_physical_lines_by_path": sum(x["physical_lines"] or 0 for x in records),
        "source_files_with_unknown_lines": [x["path"] for x in records if x["source_by_extension"] and x["physical_lines"] is None],
        "unique_content_count": len(unique), "bytes_by_unique_content": sum(x["bytes"] for x in unique.values()),
        "known_physical_lines_by_unique_content": sum(x["physical_lines"] or 0 for x in unique.values())}


def inventory(root, modules, encoding, max_files, max_directories):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("package root must be an existing directory")
    records, skipped, errors = [], [], []
    pending = deque([root])
    visited = 0
    budget_exhausted = False
    while pending:
        if visited >= max_directories:
            budget_exhausted = True
            break
        directory = pending.popleft()
        visited += 1
        try:
            for path in sorted(directory.iterdir(), key=lambda p: p.name.casefold()):
                rel = path.relative_to(root).as_posix()
                if link(path):
                    skipped.append({"path": rel, "reason": "link_not_followed"})
                    continue
                if path.is_dir():
                    if path.name.casefold() in EXCLUDED_DIRS:
                        skipped.append({"path": rel, "reason": "excluded_directory"})
                    else:
                        pending.append(path)
                    continue
                if not path.is_file():
                    skipped.append({"path": rel, "reason": "not_a_regular_file"})
                    continue
                name = path.name.lower()
                if name == ".env" or name.startswith(".env.") or path.suffix.lower() in PRIVATE_SUFFIXES:
                    skipped.append({"path": rel, "reason": "private_config_not_read"})
                    continue
                if len(records) >= max_files:
                    budget_exhausted = True
                    break
                try:
                    path.resolve().relative_to(root)
                    records.append(inspect_file(path, root, encoding))
                except (OSError, ValueError):
                    errors.append({"path": rel, "reason": "file_not_readable_or_outside_scope"})
            if budget_exhausted:
                break
        except OSError:
            errors.append({"path": directory.relative_to(root).as_posix(), "reason": "directory_not_readable"})
    by_hash = {}
    module_results = []
    assignments = {item["path"]: [] for item in records}
    for item in records:
        by_hash.setdefault(item["sha256"], []).append(item["path"])
    for module in modules:
        selected = [item for item in records if any(matches(item["path"], p) for p in module["paths"])
                    and not any(matches(item["path"], p) for p in module["exclude_paths"])]
        for item in selected:
            assignments[item["path"]].append(module["id"])
        module_results.append({"id": module["id"], "origin_claim": module.get("origin_claim", "未提供"),
            "origin_evidence_refs": module.get("evidence_refs", []), "origin_verification": "not_performed",
            "paths": [item["path"] for item in selected], "totals": summarize(selected)})
    totals = summarize(records)
    complete = not budget_exhausted and not errors and not any(x["changed_while_reading"] for x in records)
    return {"schema_version": 1, "root": str(root),
        "line_count_method": "physical_lines_including_comments_and_blank_lines",
        "scope": {"excluded_directory_names": sorted(EXCLUDED_DIRS), "max_files": max_files,
                  "max_directories": max_directories, "directories_scanned": visited, "budget_exhausted": budget_exhausted},
        "complete_for_declared_scope": complete,
        "source_line_counts_complete": not totals["source_files_with_unknown_lines"],
        "files": records, "totals": totals, "modules": module_results,
        "module_overlaps": [{"path": p, "modules": ids} for p,ids in assignments.items() if len(ids) > 1],
        "unassigned_paths": [p for p,ids in assignments.items() if not ids] if modules else [],
        "duplicate_content_groups": [paths for paths in by_hash.values() if len(paths) > 1],
        "skipped": skipped, "errors": errors, "origin_or_license_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--modules")
    parser.add_argument("--source-encoding", default="utf-8")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--max-directories", type=int, default=20000)
    args = parser.parse_args()
    try:
        if args.max_files < 1 or args.max_directories < 1:
            raise ValueError("inventory budgets must be positive")
        codecs.lookup(args.source_encoding)
        result = inventory(args.root, load_modules(args.modules), args.source_encoding, args.max_files, args.max_directories)
    except (OSError, ValueError, LookupError) as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["complete_for_declared_scope"] and result["source_line_counts_complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
