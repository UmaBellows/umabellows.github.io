#!/usr/bin/env python3
"""Make site images small enough for the web.

Usage:
    python tools/optimize_images.py                     # process every image that still needs it
    python tools/optimize_images.py assets/img/x.png    # process just these files
    python tools/optimize_images.py --layout tile PATH  # also print an <img> tag for that layout
    python tools/optimize_images.py --dry-run           # report only, change nothing

What it does
  * Photos (PNG/JPEG under assets/img/) become WebP:
        name.webp       long edge up to 1600 px (never enlarged)
        name-640.webp   640 px wide, only when the photo is wider than 800 px
    Quality 80 (90 for line drawings in assets/img/drawings/). The camera
    orientation is applied, and camera metadata (EXIF, GPS) is dropped.
  * Logos keep their format and are shrunk to about twice their on-screen size:
    client logos (assets/img/clients-real/) to fit 260 x 76 px, the site logo
    to 126 px tall. An SVG that only wraps a photo becomes a PNG.
  * The certificate, icons and real SVG drawings are left alone.
  * Each original is moved to _archive/originals/<same path> (not published,
    not in git), so running the script again skips it.

After converting, point the page at the new file. The printed tag has the
right width/height/srcset; pick --layout from LAYOUTS below. Then run
python tools/check_site.py. Needs Pillow (pip install Pillow).
"""
import argparse
import base64
import io
import os
import re
import shutil
import sys

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is needed: pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = "assets/img"
ARCHIVE = "_archive/originals"
LARGE, SMALL, SMALL_MIN = 1600, 640, 800
QUALITY, DRAWING_QUALITY = 80, 90
CLIENT_LOGO_BOX = (260, 76)          # 2x the logo strip's 130 x 38 px slot
SITE_LOGO = f"{IMG}/Uma-bellows-logo.jpeg"
SITE_LOGO_HEIGHT = 126               # 3x the 42 px header logo
LEAVE_ALONE = {f"{IMG}/ISO_Certificate_Uma-Bellows.jpeg", f"{IMG}/apple-touch-icon.png", f"{IMG}/favicon.ico"}
PHOTO_EXT = (".png", ".jpg", ".jpeg")
# The `sizes` attribute for each page layout: how wide the image is shown
# (CSS px) at each screen width, measured on the site at 1280 and 375 px.
LAYOUTS = {
    "tile":    "(max-width:600px) 50vw, (max-width:900px) 33vw, 282px",   # .tile-grid (4/3/2 columns)
    "card":    "(max-width:760px) 100vw, 551px",                          # .product-card .thumb
    "hero":    "(max-width:900px) 100vw, 517px",                          # homepage slider
    "process": "(max-width:760px) calc(100vw - 120px), 282px",            # .process-card (figure margins)
    "half":    "(max-width:800px) 100vw, 546px",                          # .grid-2 column
    "full":    "(max-width:1180px) 100vw, 1132px",                        # full content width
}


def rel(path):
    return os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/")


def kind(path):
    """'photo', 'client-logo', 'site-logo' or None (leave alone)."""
    if not path.startswith(IMG + "/") or path in LEAVE_ALONE:
        return None
    if path == SITE_LOGO:
        return "site-logo"
    if path.startswith(f"{IMG}/clients-real/"):
        return "client-logo"
    if path.lower().endswith(PHOTO_EXT):
        return "photo"
    return None


def load(path):
    full = os.path.join(ROOT, path)
    if path.lower().endswith(".svg"):
        # Only SVGs that are a wrapper around one embedded photo are handled.
        with open(full, encoding="utf-8") as fh:
            svg = fh.read()
        m = re.search(r'href="data:image/[a-z]+;base64,([^"]+)"', svg)
        if not m or len(re.findall(r"<(?!svg|image|\?|!)\w+", svg)):
            return None
        im = Image.open(io.BytesIO(base64.b64decode(m.group(1))))
    else:
        im = Image.open(full)
    im.load()
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im)
    if im.mode == "P":
        im = im.convert("RGBA")
    if im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] == 255:
        im = im.convert("RGB")            # fully opaque: drop the unused alpha
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA" if "A" in im.mode else "RGB")
    return im, icc


def scaled(im, width=None, box=None):
    w, h = im.size
    if box:
        f = min(box[0] / w, box[1] / h, 1)
    else:
        f = min(width / w, 1) if width else min(LARGE / max(w, h), 1)
    size = (max(1, round(w * f)), max(1, round(h * f)))
    return im if size == im.size else im.resize(size, Image.LANCZOS)


def save(im, path, icc, fmt, quality):
    full = os.path.join(ROOT, path)
    kw = {"icc_profile": icc} if icc else {}
    if fmt == "WEBP":
        im.save(full, "WEBP", quality=quality, method=6, **kw)
    elif fmt == "PNG":
        im.save(full, "PNG", optimize=True, **kw)
    elif fmt == "JPEG":
        im.convert("RGB").save(full, "JPEG", quality=85, optimize=True, progressive=True, **kw)
    return os.path.getsize(full)


def archive(path):
    dest = os.path.join(ROOT, ARCHIVE, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(os.path.join(ROOT, path), dest)


def img_tag(large, size, small, layout):
    attrs = [f'src="/{large}"']
    if small:
        attrs.append(f'srcset="/{small} {SMALL}w, /{large} {size[0]}w" sizes="{LAYOUTS[layout]}"')
    attrs.append(f'width="{size[0]}" height="{size[1]}" alt="TODO: describe the photo" loading="lazy" decoding="async"')
    return "<img " + " ".join(attrs) + ">"


def process(path, dry_run, layout=None):
    """Return (old_path, new_paths, bytes_before, [bytes of each new file], size) or None if nothing to do."""
    k = kind(path)
    if k is None:
        return None
    before = os.path.getsize(os.path.join(ROOT, path))
    loaded = load(path)
    if loaded is None:
        return None
    im, icc = loaded
    base, ext = os.path.splitext(path)
    if k == "photo":
        large = scaled(im)
        out = [(f"{base}.webp", large, "WEBP")]
        if im.size[0] > SMALL_MIN:
            out.append((f"{base}-{SMALL}.webp", scaled(im, width=SMALL), "WEBP"))
        quality = DRAWING_QUALITY if path.startswith(f"{IMG}/drawings/") else QUALITY
    else:
        small = scaled(im, box=CLIENT_LOGO_BOX) if k == "client-logo" else \
            scaled(im, width=round(im.size[0] * SITE_LOGO_HEIGHT / im.size[1]))
        if small.size == im.size and not ext == ".svg":
            return None                   # already small enough
        fmt = {".png": "PNG", ".svg": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[ext.lower()]
        new_ext = ".png" if ext == ".svg" else ext
        out = [(base + new_ext, small, fmt)]
        quality = QUALITY
    if dry_run:
        return path, [o[0] for o in out], before, None, out[0][1].size
    archive(path)
    after = [save(o[1], o[0], icc, o[2], quality) for o in out]
    if layout and k == "photo":
        print("    " + img_tag(out[0][0], out[0][1].size, out[1][0] if len(out) > 1 else None, layout))
    return path, [o[0] for o in out], before, after, out[0][1].size


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="images to process (default: all under assets/img)")
    ap.add_argument("--layout", choices=sorted(LAYOUTS), help="print an <img> tag for this page layout")
    ap.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    args = ap.parse_args()

    if args.paths:
        paths = [rel(p) for p in args.paths]
    else:
        paths = sorted(rel(os.path.join(d, f)) for d, _, fs in os.walk(os.path.join(ROOT, IMG)) for f in fs)
    total_before = total_after = 0
    for p in paths:
        r = process(p, args.dry_run, args.layout)
        if r is None:
            continue
        old, new, before, after, size = r
        total_before += before
        total_after += sum(after or [])
        sizes = f"{before / 1024:,.0f} KB"
        if after:
            sizes += f" -> {after[0] / 1024:,.0f} KB" + (f" + {after[1] / 1024:,.0f} KB at {SMALL} px" if len(after) > 1 else "")
        print(f"  {old} -> {', '.join(os.path.basename(n) for n in new)}  ({size[0]}x{size[1]}, {sizes})")
    if total_before:
        print(f"Done: {total_before / 1e6:.1f} MB" + (f" -> {total_after / 1e6:.1f} MB (all new files)" if not args.dry_run else " to process") + ".")
    else:
        print("Nothing to do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
