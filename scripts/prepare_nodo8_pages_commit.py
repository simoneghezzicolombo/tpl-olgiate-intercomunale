"""Prepare a fast-forward Pages commit while preserving every unselected Git path."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from build_nodo8_publication import ROOT, POLICY, selected_files


def git(*args, env=None, data=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, env=env, input=data)


def entries(ref):
    result = {}
    for record in git("ls-tree", "-r", "-z", ref).split(b"\0"):
        if not record:
            continue
        header, path = record.split(b"\t", 1)
        mode, kind, sha = header.decode().split()
        result[path.decode("utf-8")] = (mode, kind, sha)
    return result


if __name__ == "__main__":
    source = git("rev-parse", "HEAD").decode().strip()
    base = git("rev-parse", "origin/gh-pages").decode().strip()
    copy_paths = sorted(set(selected_files()) | {
        ".gitattributes", POLICY,
        ".github/workflows/nodo8-final-pages.yml",
        "scripts/build_nodo8_publication.py",
        "tests/test_nodo8_publication.py",
        "tests/test_nodo8_journey.mjs",
        "docs/NODO8_PUBBLICAZIONE_FINALE_2026_10_08.md",
    })
    before, source_entries = entries(base), entries(source)
    if any(path not in source_entries for path in copy_paths):
        raise SystemExit("Publication inputs must be committed before preparing the deployment.")
    cache = (ROOT / "cache").resolve()
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nodo8-git-index-", dir=cache) as folder:
        index = (Path(folder) / "index").resolve()
        if not index.is_relative_to(cache):
            raise SystemExit("Temporary index escaped publication cache")
        env = dict(os.environ, GIT_INDEX_FILE=str(index))
        git("read-tree", base, env=env)
        lines = []
        for path in copy_paths:
            mode, kind, sha = source_entries[path]
            if kind != "blob" or mode not in ("100644", "100755"):
                raise SystemExit("Only regular committed files can enter the publication tree")
            lines.append(f"{mode} {sha}\t{path}\n")
        git("update-index", "--index-info", env=env, data="".join(lines).encode())
        tree = git("write-tree", env=env).decode().strip()
    after = entries(tree)
    preserved = {path: value for path, value in before.items() if path not in copy_paths}
    if any(after.get(path) != value for path, value in preserved.items()):
        raise SystemExit("Unexpected deletion or modification of an unselected repository path")
    commit = git("commit-tree", tree, "-p", base, "-m",
                 f"Publish final Nodo8 artifact only; preserve retired sources ({source[:8]})").decode().strip()
    print(json.dumps({
        "commit": commit, "parent": base, "source_revision": source,
        "updated_repository_paths": len(copy_paths),
        "preserved_repository_paths": len(preserved),
        "retired_html_preserved": [path for path in preserved if path.endswith(".html")],
        "deleted_repository_paths": [],
    }))
