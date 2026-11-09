"""Offline, hash-checked skill installation. Preview by default; never overwrite differing skills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_destination():
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser() / "skills"
    old = Path.home() / ".codex" / "skills"
    return old if old.is_dir() else Path.home() / ".agents" / "skills"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", action="append", help="Skill ID; repeat to choose several")
    parser.add_argument("--all", action="store_true", help="Select every packaged skill")
    parser.add_argument("--dest", type=Path, default=default_destination())
    parser.add_argument("--apply", action="store_true", help="Actually install; default only previews")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
    catalog = {row["id"]: row for row in manifest["skills"]}
    names = list(catalog) if args.all else list(dict.fromkeys(args.skill or []))
    if not names:
        print("Available skills:\n" + "\n".join(catalog))
        print("Choose --skill ID or --all. Add --apply to install.")
        return
    if any(not re.fullmatch(r"[a-z0-9-]+", name) or name not in catalog for name in names):
        parser.error("Unknown or invalid skill ID")
    destination = args.dest.expanduser().resolve()
    prepared = []
    for name in names:
        source = ROOT / "skills" / name
        target = destination / name
        files = catalog[name]["files"]
        expected = {row["path"] for row in files}
        actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
        if expected != actual:
            raise ValueError("Package file list differs: " + name)
        for row in files:
            path = source / row["path"]
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()) or digest(path) != row["sha256"]:
                raise ValueError("Package integrity check failed: " + name)
        if target.is_symlink():
            raise ValueError("Existing symlink destination; inspect manually: " + str(target))
        if target.exists():
            matches = target.is_dir() and {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()} == expected
            matches = matches and all(not (target / row["path"]).is_symlink() and digest(target / row["path"]) == row["sha256"] for row in files)
            if not matches:
                raise ValueError("Existing skill differs; nothing overwritten: " + str(target))
        prepared.append((name, source, target))
    for name, source, target in prepared:
        state = "already identical" if target.exists() else "install" if args.apply else "would install"
        print(state + ": " + str(target))
    if not args.apply:
        return
    destination.mkdir(parents=True, exist_ok=True)
    for name, source, target in prepared:
        if target.exists():
            continue
        staging = Path(tempfile.mkdtemp(prefix=".workflow-kit-", dir=destination)).resolve()
        if staging.parent != destination or not staging.name.startswith(".workflow-kit-"):
            raise ValueError("Unexpected staging directory")
        try:
            stage = staging / name
            shutil.copytree(source, stage)
            if not all(digest(stage / row["path"]) == row["sha256"] for row in catalog[name]["files"]):
                raise ValueError("Copy verification failed")
            stage.rename(target)
        finally:
            # This exact temporary directory was created here under the chosen destination.
            shutil.rmtree(staging)
    print("Installed. Start a new conversation; if absent, refresh or restart your host.")


if __name__ == "__main__":
    main()
