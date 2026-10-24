# Security

## What the browser tool does with your data

- The page makes no network requests with your data: no fetch, XHR, WebSocket, beacons, or analytics. It loads two external resources, both static: the Google Fonts stylesheet and the jsPDF library from cdnjs (version 4.2.1, pinned, with a Subresource Integrity hash, so a changed file is refused). The GitHub Pages build adds a Content-Security-Policy with `connect-src 'none'`.
- Nothing you enter leaves your device. Your business profile, customers, catalog, and documents are kept in this browser's localStorage so they survive a reload. This is the product's own data and it never goes anywhere else. Every storage access is wrapped in try/catch, and the page works (without saving) when storage is blocked.
- Backups leave the device only when you copy or save them yourself (Export all).
- Imported backups are parsed with JSON.parse and checked against a strict schema before use: known keys only, length caps on every string, control characters removed, numeric ranges, whole cents, real dates and times, PNG or JPEG data URLs only for images, unique ids. A failed check changes nothing.
- Logos are read with FileReader, files over 2 MB are refused, and the image is redrawn on a canvas and stored as a PNG or JPEG data URL. SVG is not accepted.
- No eval, no `new Function`, no inline event handlers. User text goes into the page through textContent or createElement only, never innerHTML, and into the PDF through jsPDF text calls.
- The "Copy list as CSV" export prefixes cells that start with `=`, `+`, `-`, `@`, tab, or carriage return with a single quote so spreadsheets do not run them as formulas.

## Python library

- No network calls, no pickle, no eval, no shell calls. The CLI reads only the file path you pass it, capped at 20 MB, and rejects NaN and Infinity in JSON.

## Reporting an issue

Open a GitHub issue titled "Security" with a description and steps to reproduce. For anything sensitive, use GitHub's private vulnerability reporting on this repository instead of a public issue.
