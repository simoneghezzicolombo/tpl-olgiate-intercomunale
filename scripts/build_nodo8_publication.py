"""Publish an explicit two-page allowlist, never the whole repository."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
POLICY = "config/nodo8_publication_allowlist.json"
HTML_PAGES = {"index.html", "dietro-l-analisi/index.html"}


def selected_files(root=ROOT):
    policy = json.loads((root / POLICY).read_text(encoding="utf-8"))
    if policy["contract"] != "nodo8_final_only_publication_v1":
        raise ValueError("Unknown publication policy")
    paths = policy["include_files"]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate publication path")
    if {path for path in paths if path.endswith(".html")} != HTML_PAGES:
        raise ValueError("Only the two final HTML pages may be published")
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ".git" in path.parts:
            raise ValueError("Unsafe publication path")
        resolved = (root / name).resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file() or (root / name).is_symlink():
            raise ValueError(f"Missing/unsafe selected file: {name}")
    return sorted(paths)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = "src" if tag in ("script", "img", "iframe") else "href" if tag in ("a", "link") else None
        if key and key in attrs:
            self.references.append(attrs[key])


def validate_links(output):
    for page in HTML_PAGES:
        parser = Links()
        parser.feed((output / page).read_text(encoding="utf-8"))
        for reference in parser.references:
            url = urlsplit(reference)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (output / page).parent / unquote(url.path)
            if not target.is_file() and not (target / "index.html").is_file():
                raise ValueError(f"Unpublished dependency from {page}: {reference}")


def build(output, root=ROOT, revision="unspecified"):
    root, output = root.resolve(), output.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError("Output cannot replace or contain the source repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite a non-empty publication directory")
    paths = selected_files(root)
    output.mkdir(parents=True, exist_ok=True)
    for name in paths:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    validate_links(output)
    if {p.relative_to(output).as_posix() for p in output.rglob("*.html")} != HTML_PAGES:
        raise ValueError("Unexpected HTML in publication artifact")
    manifest = {
        "contract": "nodo8_final_only_publication_v1",
        "source_revision": revision,
        "published_html_pages": sorted(HTML_PAGES),
        "excluded_repository_files_deleted": False,
        "files": [{"path": name, "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
                  for name in paths],
    }
    (output / "publication-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", default="unspecified")
    args = parser.parse_args()
    result = build(args.output, revision=args.revision)
    print(f"Built {len(result['files'])} allowlisted files; exactly two final HTML pages.")
