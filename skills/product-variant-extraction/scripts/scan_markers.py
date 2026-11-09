#!/usr/bin/env python3
"""Read-only literal marker scan. Reports locations, never matching source text."""
import argparse
from collections import deque
import codecs
import json
from pathlib import Path
import sys

EXCLUDED = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".next"}
MAX_BYTES = 2 * 1024 * 1024
MAX_REPORTED_MATCHES = 500


def read_markers(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    markers = raw.get("markers") if isinstance(raw, dict) else None
    if not isinstance(markers, list) or not markers:
        raise ValueError("provide a nonempty markers array")
    ids = set()
    for item in markers:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError("each marker needs a nonempty string id")
        if item["id"] in ids:
            raise ValueError("marker ids must be unique")
        ids.add(item["id"])
        if not isinstance(item.get("needle"), str) or not item["needle"]:
            raise ValueError("marker needle must be a nonempty literal string")
        if item.get("where", "both") not in ("path", "content", "both"):
            raise ValueError("marker where must be path, content or both")
        if not isinstance(item.get("case_sensitive", True), bool):
            raise ValueError("case_sensitive must be a boolean")
    return markers


def contains(text, marker):
    needle = marker["needle"]
    if not marker.get("case_sensitive", True):
        text, needle = text.casefold(), needle.casefold()
    return needle in text


def scan(root, markers, max_files, max_directories):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("scan root must be an existing directory")
    pending = deque([root])
    matches, skipped, errors = [], [], []
    seen_files = seen_dirs = total_hits = 0
    limited = False
    content_needed = any(m.get("where", "both") != "path" for m in markers)

    def hit(marker, rel, where, line=None):
        nonlocal total_hits
        total_hits += 1
        if len(matches) < MAX_REPORTED_MATCHES:
            record = {"marker_id": marker["id"], "path": rel, "where": where}
            if line is not None:
                record["line"] = line
            matches.append(record)

    while pending:
        if seen_dirs >= max_directories:
            limited = True
            break
        directory = pending.popleft()
        seen_dirs += 1
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name.casefold())
            for path in children:
                rel = path.relative_to(root).as_posix()
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    skipped.append({"path": rel, "reason": "link_not_followed"})
                    continue
                if path.is_dir():
                    if path.name.casefold() in EXCLUDED:
                        skipped.append({"path": rel, "reason": "excluded_directory"})
                    else:
                        pending.append(path)
                    continue
                if not path.is_file():
                    continue
                if seen_files >= max_files:
                    limited = True
                    break
                seen_files += 1
                for marker in markers:
                    if marker.get("where", "both") != "content" and contains(rel, marker):
                        hit(marker, rel, "path")
                if not content_needed:
                    continue
                try:
                    path.resolve().relative_to(root)
                    before = path.stat()
                    if before.st_size > MAX_BYTES:
                        errors.append({"path": rel, "reason": "content_exceeds_2_mib"})
                        continue
                    raw = path.read_bytes()
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                        errors.append({"path": rel, "reason": "file_changed_while_reading"})
                        continue
                    encoding = ("utf-32" if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)) else
                                "utf-16" if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else "utf-8-sig")
                    text = raw.decode(encoding)
                    if "\0" in text:
                        raise ValueError("binary-like content")
                    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                    for number, line in enumerate(lines, 1):
                        for marker in markers:
                            if marker.get("where", "both") != "path" and contains(line, marker):
                                hit(marker, rel, "content", number)
                except (OSError, ValueError, UnicodeError):
                    errors.append({"path": rel, "reason": "content_not_readable_or_not_supported_text"})
            if limited:
                break
        except OSError:
            errors.append({"path": directory.relative_to(root).as_posix(), "reason": "directory_not_readable"})
    return {"schema_version": 1, "root": str(root), "matches": matches, "matches_found": total_hits,
        "unreported_match_count": total_hits - len(matches), "files_scanned": seen_files,
        "directories_scanned": seen_dirs, "budget_exhausted": limited,
        "complete_for_declared_scope": not limited and not errors,
        "excluded_directory_names": sorted(EXCLUDED), "skipped": skipped, "errors": errors,
        "automatic_replacement_performed": False, "semantic_isolation_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--markers", required=True)
    parser.add_argument("--max-files", type=int, default=10000)
    parser.add_argument("--max-directories", type=int, default=10000)
    args = parser.parse_args()
    try:
        if args.max_files < 1 or args.max_directories < 1:
            raise ValueError("scan budgets must be positive")
        result = scan(args.root, read_markers(args.markers), args.max_files, args.max_directories)
    except (OSError, ValueError) as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["complete_for_declared_scope"] else 2


if __name__ == "__main__":
    sys.exit(main())
