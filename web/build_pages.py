"""Wrap web/app.html into docs/index.html as a full HTML document for GitHub Pages.

app.html follows the standalone page contract (no doctype, html, head, or body
tags). This script adds them, moving the title, meta, font link, and style into
<head>. The Content-Security-Policy allows scripts only inline and from
cdnjs (the pinned, integrity-checked jsPDF build) and blocks every connection. Run: python web/build_pages.py
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "app.html"
OUT = ROOT / "docs" / "index.html"

HEAD_RE = re.compile(r"\A\s*(<title>.*?</title>.*?</style>)\s*", re.S)


def build(src: str) -> str:
    m = HEAD_RE.match(src)
    if not m:
        raise SystemExit("app.html must start with <title>, meta, font link, and <style>")
    head = m.group(1)
    body = src[m.end():]
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Estimates, oilfield field tickets, and invoices with a print-ready PDF. Runs entirely in your browser; nothing is uploaded.">\n'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
        "script-src 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src data: blob:; connect-src 'none'; "
        "form-action 'none'; base-uri 'none'\">\n"
        '<meta name="referrer" content="no-referrer">\n'
        + head
        + "\n<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "[hidden]{display:none!important}img{max-width:100%}</style>\n"
        "</head>\n"
        "<body>\n"
        + body.rstrip()
        + "\n</body>\n</html>\n"
    )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(SRC.read_text(encoding="utf-8")), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))


if __name__ == "__main__":
    main()
