#!/usr/bin/env python3
"""Stamp the shared page parts in _partials/ into every page.

Usage:
    python tools/sync_partials.py          # update pages in place
    python tools/sync_partials.py --check  # report pages that are out of date; exit 1 if any

Each page marks where a shared part goes:

    <!-- partial:header -->
    ...generated: edit _partials/header.html instead, then run this script...
    <!-- /partial:header -->

While stamping, the script also
  * marks the current section in the header nav with aria-current="page"
    (the nav link whose path is the longest prefix of the page's path),
  * marks footer links that point at the page itself,
  * replaces {{year}} with the current year.
Every page must contain the head, header and footer parts.
Standard library only.
"""
import argparse
import datetime
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTIALS = os.path.join(ROOT, "_partials")
REQUIRED = ("head", "header", "footer")
SKIP_DIRS = {"tools", "node_modules"}
BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)<!-- partial:(?P<name>[\w-]+) -->\n(?P<body>.*?)^[ \t]*<!-- /partial:(?P=name) -->",
    re.S | re.M)
HREF_RE = re.compile(r'<a href="(?P<href>[^"#]+)"')


def site_pages():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(("_", ".")) and d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f.endswith(".html"):
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
                yield rel


def page_path(rel):
    """index.html -> /, about/index.html -> /about/, 404.html -> /404.html"""
    return "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


def mark_current(html, path, scope_re, prefix_match):
    """Add aria-current="page" to the best-matching link inside the scoped block."""
    m = scope_re.search(html)
    if not m:
        return html
    block = m.group(0)
    hrefs = [h.group("href") for h in HREF_RE.finditer(block)]
    if prefix_match:
        hits = [h for h in hrefs if h == path or (h != "/" and h.endswith("/") and path.startswith(h))]
        hits = [max(hits, key=len)] if hits else []
    else:
        hits = [h for h in hrefs if h == path]
    for h in set(hits):
        block = block.replace(f'<a href="{h}">', f'<a href="{h}" aria-current="page">')
    return html[: m.start()] + block + html[m.end():]


def render(name, path, year):
    with open(os.path.join(PARTIALS, name + ".html"), encoding="utf-8") as fh:
        html = fh.read().replace("\r\n", "\n")
    html = html.replace("{{year}}", str(year))
    if name == "header":
        html = mark_current(html, path, re.compile(r'<nav class="primary-nav".*?</nav>', re.S), True)
    elif name == "footer":
        html = mark_current(html, path, re.compile(r'<div class="wrap footer-grid">.*?\n  </div>', re.S), False)
    if not html.endswith("\n"):
        html += "\n"
    return html


def sync_page(rel, year):
    """Return (new_text, original_text, problems) for one page; texts use \\n line endings."""
    with open(os.path.join(ROOT, rel), "rb") as fh:
        original = fh.read().decode("utf-8").replace("\r\n", "\n")
    problems, found = [], set()

    def stamp(m):
        name = m.group("name")
        found.add(name)
        if not os.path.exists(os.path.join(PARTIALS, name + ".html")):
            problems.append(f"{rel}: unknown partial '{name}'")
            return m.group(0)
        indent = m.group("indent")
        return (f"{indent}<!-- partial:{name} -->\n{render(name, page_path(rel), year)}"
                f"{indent}<!-- /partial:{name} -->")

    updated = BLOCK_RE.sub(stamp, original)
    for name in REQUIRED:
        if name not in found:
            problems.append(f"{rel}: missing <!-- partial:{name} --> block")
    return updated, original, problems


def check(year=None):
    """Return a list of problems; empty when every page is in sync."""
    year = year or datetime.date.today().year
    out = []
    for rel in site_pages():
        updated, original, problems = sync_page(rel, year)
        out += problems
        if updated != original:
            out.append(f"{rel}: shared parts out of date (run python tools/sync_partials.py)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    args = ap.parse_args()
    if args.check:
        problems = check()
        for p in problems:
            print("  " + p)
        print("Shared parts: " + ("OK, all pages in sync." if not problems else f"{len(problems)} problem(s)."))
        return 1 if problems else 0

    year, changed, problems = datetime.date.today().year, 0, []
    for rel in site_pages():
        updated, original, page_problems = sync_page(rel, year)
        problems += page_problems
        if updated != original:
            full = os.path.join(ROOT, rel)
            with open(full, "rb") as fh:
                crlf = b"\r\n" in fh.read()
            text = updated.replace("\n", "\r\n") if crlf else updated
            for attempt in range(5):  # Windows virus scanners can briefly lock a file
                try:
                    with open(full, "wb") as fh:
                        fh.write(text.encode("utf-8"))
                    break
                except OSError:
                    if attempt == 4:
                        raise
                    time.sleep(0.5)
            changed += 1
    for p in problems:
        print("  " + p)
    print(f"Updated {changed} page(s)." + (f" {len(problems)} problem(s)." if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
