#!/usr/bin/env python3
"""Static checks for the Uma Bellows site.

Usage:
    python tools/check_site.py            # run all checks; exit 1 on any error
    python tools/check_site.py --weights  # also print image weight per page

Checks:
  * every internal link, image and form target resolves to a file in the site
  * every #anchor exists on the page it points to
  * sitemap.xml lists every indexable page and nothing that is noindex/missing
  * indexable pages contain no draft or placeholder text
  * every page's shared parts match _partials/ (see tools/sync_partials.py)
Standard library only, so it runs unchanged in CI.
"""
import argparse
import os
import posixpath
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_HOST = "umabellows.com"
# Directories that are never published (Jekyll skips "_" and "." prefixes).
SKIP_DIRS = {"tools", "node_modules"}
DRAFT_PATTERNS = [
    r"\[TBD", r"\bTODO\b", r"\bFIXME\b", r"lorem ipsum", r"do not publish",
    r"before publishing", r"before this page goes live",
]
# Known draft text that a planned change will remove: (page, matched text) -> reason.
# Reported as a warning, not an error. Delete the entry when the fix lands.
PENDING = {
    ("certifications/index.html", "before publishing"):
        "ISO note, replaced in roadmap Phase 1C once the certificate status is confirmed",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []      # (attribute, value)
        self.ids = set()
        self.noindex = False
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "name" in a:
            self.ids.add(a["name"])
        for attr in ("href", "src", "action"):
            if a.get(attr):
                self.refs.append((attr, a[attr]))
        if tag == "img" and a.get("src"):
            self.imgs.append(a["src"])
        if tag == "meta" and (a.get("name") or "").lower() == "robots" \
                and "noindex" in (a.get("content") or "").lower():
            self.noindex = True


def published_files():
    out = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(("_", ".")) and d not in SKIP_DIRS]
        for f in filenames:
            if not f.startswith((".", "_")):
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                out.add(rel.replace(os.sep, "/"))
    return out


def resolve(path, files):
    """Map a site path like /about/ or /a.html to a published file, or None."""
    rel = unquote(path).lstrip("/")
    candidates = [rel + "index.html"] if rel == "" or rel.endswith("/") \
        else [rel, rel + "/index.html"]
    return next((c for c in candidates if c in files), None)


def page_url(page):
    return "/" + (page[: -len("index.html")] if page.endswith("index.html") else page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", action="store_true", help="print image weight per page")
    args = ap.parse_args()

    files = published_files()
    pages = sorted(f for f in files if f.endswith(".html"))
    parsed, raw = {}, {}
    for p in pages:
        with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
            raw[p] = fh.read()
        pp = PageParser()
        pp.feed(raw[p])
        parsed[p] = pp

    errors = []

    # 1. Links, images, form targets and anchors
    for p in pages:
        for attr, value in parsed[p].refs:
            u = urlparse(value)
            if u.scheme in ("mailto", "tel", "javascript", "data"):
                continue
            if u.scheme in ("http", "https") and not u.netloc.endswith(SITE_HOST):
                continue
            path = u.path
            if not path:
                target = p
            else:
                if not path.startswith("/"):
                    path = posixpath.normpath(posixpath.join("/" + posixpath.dirname(p), path))
                target = resolve(path, files)
                if target is None:
                    errors.append(f"{p}: broken {attr} -> {value}")
                    continue
            if u.fragment and target.endswith(".html") and u.fragment not in parsed[target].ids:
                errors.append(f"{p}: missing anchor -> {value}")

    # 2. Sitemap coverage
    with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as fh:
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", fh.read())
    in_sitemap = set()
    for loc in locs:
        target = resolve(urlparse(loc).path, files)
        if target is None:
            errors.append(f"sitemap.xml: URL has no page -> {loc}")
            continue
        in_sitemap.add(target)
        if parsed[target].noindex:
            errors.append(f"sitemap.xml: lists a noindex page -> {loc}")
    for p in pages:
        if p != "404.html" and not parsed[p].noindex and p not in in_sitemap:
            errors.append(f"sitemap.xml: indexable page missing -> {page_url(p)}")

    # 3. Draft / placeholder text on indexable pages (HTML comments ignored)
    draft_re = re.compile("|".join(DRAFT_PATTERNS), re.I)
    warnings = []
    for p in pages:
        if parsed[p].noindex:
            continue
        visible = re.sub(r"<!--.*?-->", "", raw[p], flags=re.S)
        for m in draft_re.finditer(visible):
            line = visible.count("\n", 0, m.start()) + 1
            reason = PENDING.get((p, m.group(0).lower()))
            if reason:
                warnings.append(f"{p}:{line}: '{m.group(0)}' ({reason})")
            else:
                errors.append(f"{p}:{line}: draft text '{m.group(0)}'")

    # 4. Shared parts (header, footer, head, logo strip) match _partials/
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sync_partials
    errors += sync_partials.check()

    if args.weights:
        print("Image weight per page (unique <img> sources):")
        rows = []
        for p in pages:
            total = 0
            for src in set(parsed[p].imgs):
                target = resolve(urlparse(src).path, files)
                if target:
                    total += os.path.getsize(os.path.join(ROOT, target))
            rows.append((total, p))
        for total, p in sorted(rows, reverse=True):
            print(f"  {total / 1e6:6.1f} MB  {page_url(p)}")
        print()

    if warnings:
        print(f"{len(warnings)} pending item(s), not failing:")
        for w in warnings:
            print("  " + w)
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print("  " + e)
        return 1
    print(f"OK: {len(pages)} pages checked, no problems.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
