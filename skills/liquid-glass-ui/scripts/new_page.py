#!/usr/bin/env python3
"""Bundle the editable palette workbench as a self-contained HTML file."""
import argparse
import html
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def replace_once(text, marker, value):
    if text.count(marker) != 1:
        raise ValueError(f"Expected one template marker: {marker}")
    return text.replace(marker, value, 1)


def build(title):
    assets = Path(__file__).resolve().parents[1] / "assets"
    page = (assets / "starter.html").read_text(encoding="utf-8")
    css = (assets / "liquid-glass.css").read_text(encoding="utf-8")
    page = replace_once(page, '<link rel="stylesheet" href="./liquid-glass.css">', f"<style>\n{css}\n</style>")
    for filename, symbol in [("glass-segments.js", "mountGlassSegments"), ("liquid-lens.js", "mountGlassLens")]:
        statement = f"import {{{symbol}}} from './{filename}';"
        page = replace_once(page, statement, (assets / filename).read_text(encoding="utf-8"))
    for tag in ["title", 'strong class="wordmark"']:
        closing = tag.split()[0]
        page = replace_once(page, f"<{tag}>色样台</{closing}>", f"<{tag}>{html.escape(title)}</{closing}>")
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New HTML file")
    parser.add_argument("--title", default="色样台", help="Page title and wordmark")
    parser.add_argument("--force", action="store_true", help="Replace the specified output file")
    args = parser.parse_args()
    page = build(args.title)
    dest = args.output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dest.parent) as scratch:
        path = Path(scratch) / "page.html"
        path.write_text(page, encoding="utf-8")
        try:
            if args.force:
                os.replace(path, dest)
            else:
                os.link(path, dest)
        except FileExistsError:
            parser.error(f"{dest} already exists; choose a different file or use --force")
    print(dest.resolve())


if __name__ == "__main__":
    main()
