# Testing

This file lists every function of Field Ticket, how each was tested, and the result. The browser checks ran against the published form of the site: the tracked files with the release placeholders filled, served under `/field-ticket/` on a local server, in headless Chromium at 1280 px (light and dark) and at 400 px with touch (light and dark). The single file `web/app.html` was also opened from `file://`.

Result key: Pass means the action finished, the numbers matched an independent calculation where there is one, and there were no page errors, console errors, or Content-Security-Policy violations.

## Function inventory

| # | Area | Function | How it was tested | Result |
|---|---|---|---|---|
| 1 | Page | Load with example data | 2 example documents, example banner, device note | Pass |
| 2 | Page | Light and dark theme | `prefers-color-scheme` light and dark; body colors checked | Pass |
| 3 | Page | Phone layout | 400 px: no sideways scroll on list and editor; all controls at least 44 px | Pass |
| 4 | Page | Method and limits panel | Opens and shows the text | Pass |
| 5 | Page | Keyboard | Tab moves focus; focus ring visible | Pass |
| 6 | Page | Network | Only jsPDF (integrity checked) and Google Fonts are requested; `connect-src 'none'` | Pass |
| 7 | Documents | New estimate, field ticket, invoice | Each opens the editor with the next number | Pass |
| 8 | Documents | Stats (Outstanding, Overdue, Open invoices, Drafts) | Outstanding $491.40 checked by hand from the example invoice | Pass |
| 9 | Documents | Filter: All, Invoices, Field tickets, Estimates, Unpaid | Counts checked | Pass |
| 10 | Documents | Copy list as CSV | Clipboard text has header and one row per document, balances match | Pass |
| 11 | Documents | CSV copy when the clipboard is blocked | Falls back to a selectable text box | Pass |
| 12 | Documents | Invoice several field tickets (bundle) | Pick, make, cancel | Pass |
| 13 | Documents | Bundle refusals (different customer or tax) | Message shown; tax now offers a one-tap choice | Pass |
| 14 | Editor | Number, date, terms, due date | Due dates across month ends and leap years | Pass |
| 15 | Editor | Status Draft, Sent, Paid; Overdue and Paid worked out | Sent with past due date shows Overdue; payments covering total show Paid | Pass |
| 16 | Editor | Made from and Invoiced on links | Open the linked document | Pass |
| 17 | Editor | Saved customer picker | Fills the Bill to block | Pass |
| 18 | Editor | Customer fields, Save to customers (new and update) | No duplicate on update | Pass |
| 19 | Editor | Oilfield mode toggle and 9 header fields | Shown in preview and PDF | Pass |
| 20 | Editor | Day rows: date, start, end, work done, add, remove | 19:00 to 03:15 is 8.25 h; equal times are 24 h | Pass |
| 21 | Editor | Add labor line from total hours | 515 minutes gives qty 8.583; rate filled from the last labor line | Pass |
| 22 | Editor | Signature pads: draw, clear, signer name | Image appears in preview and PDF; clear removes it | Pass |
| 23 | Editor | Line items: description, qty, unit, rate, discount, taxable | README example gives $2,607.58 | Pass |
| 24 | Editor | Move up, Remove line, Add blank line, Add from catalog | Order and count checked | Pass |
| 25 | Editor | Field rules | 4-decimal qty, negative, text, over-cap rate and line amount refused with a message | Pass |
| 26 | Editor | Money entry with `$` and commas | Accepted | Pass |
| 27 | Editor | Document discount percent and dollar | Percent spread by largest remainder; dollar capped at subtotal | Pass |
| 28 | Editor | Tax rate, rounding once per document or per line | Matches independent calculation | Pass |
| 29 | Editor | Extra charge label and amount, deposit | Shown in totals | Pass |
| 30 | Editor | Payments: add, date, amount, note, remove | Balance and credit rows | Pass |
| 31 | Editor | Notes | Multiline text in preview and PDF | Pass |
| 32 | Editor | Convert estimate to invoice | New invoice names the estimate as source | Pass |
| 33 | Editor | Invoice this ticket, Bundle with other tickets | Bundle now picks every open ticket for the same customer | Pass |
| 34 | Editor | Duplicate | New number, draft | Pass |
| 35 | Editor | Delete with confirm and cancel | Pass | Pass |
| 36 | Editor | Preview | Unicode and HTML shown as plain text | Pass |
| 37 | Output | Download PDF | File opens in pypdf and pdfium, has totals and fields, renders ink; non-Latin-1 letters print as `?` as documented | Pass |
| 38 | Output | PDF with logo | Renders | Pass |
| 39 | Output | PDF when jsPDF cannot load | Clear message; preview still works | Pass |
| 40 | Business | Name, license, address, phone, email | Saved and printed | Pass |
| 41 | Business | Logo upload, remove; corrupt file; wrong type | Upload shrinks to fit; bad files refused with a message | Pass |
| 42 | Business | Default tax, terms, rounding, payment instructions | New documents start with them; tax over 100 refused | Pass |
| 43 | Business | Oilfield default for new tickets | Off gives tickets without oilfield fields | Pass |
| 44 | Business | Numbering prefix and next number per type | `A-` and 41 give `A-0041`; 0 refused | Pass |
| 45 | Customers | Add, edit, delete with confirm | Pass | Pass |
| 46 | Catalog | Add, edit, rate validation, taxable, delete with confirm | Pass | Pass |
| 47 | Backup | Export all, Copy backup, Select all | Export is valid JSON and passes `field-ticket check` | Pass |
| 48 | Backup | Import paste and file, replace with confirm | Round trip restores all documents | Pass |
| 49 | Backup | Import refusals | Empty, bad JSON, NaN, array, wrong app, bad date, negative money, SVG logo, repeated ids: all refused, nothing changed | Pass |
| 50 | Backup | Large import (6.4 MB, 1,500 documents) | Imports in about 4 s; over the browser quota the page says it could not save | Pass |
| 51 | Storage | Autosave and reload | Pass | Pass |
| 52 | Storage | Unreadable saved data | Warning, copy kept under `field-ticket:v1:unreadable`, never overwritten | Pass |
| 53 | Storage | Blocked storage | Warning; app still works | Pass |
| 54 | Start fresh | Confirm, cancel, keeps your own documents | Pass | Pass |
| 55 | file:// | `web/app.html` opened as a file | Loads, PDF downloads, storage works | Pass |
| 56 | CLI | `totals`, `totals --json` | README example matches | Pass |
| 57 | CLI | `check`, `summary --today --json` | On a real browser export | Pass |
| 58 | CLI | Errors: missing file, bad JSON, NaN, Infinity, non-object, bad encoding, bad `--today` | Exit 2 with a message. A bad `--today` was accepted before this pass (fixed) | Pass after fix |
| 59 | Library | `compute_totals`, `due_date`, `shift_minutes`, `format_hours`, and the rest of the exports | 400 random documents against Python `Decimal` with half-up rounding and an independent largest-remainder split; 1,615 due dates against `datetime`; 500 shifts | Pass |

Not present in this tool, so not tested: PWA install or offline cache, undo and redo, keyboard shortcuts, network switches (the page cannot connect anywhere).

## Decisions the app now makes for you

| Decision point | Before | After |
|---|---|---|
| Which tickets to bundle from a ticket | Only the open ticket was ticked; you found and ticked the rest | Every open ticket for the same customer is ticked, with a one-line note saying why; untick to leave one out |
| Bundling tickets with different tax settings | Dead end: "Make them match, then bundle" sent you into each ticket | Asks once, right there: one button per tax setting found ("Use 8.25% tax, rounded per line (as on FT-0001)"), then bundles |
| Labor rate on "Add labor line from total hours" | Rate was 0; you typed it every time | Filled from your most recent Labor line in hours, with a note naming that document; edit it on the line |
| Tax rate, terms and rounding on a new document | Already filled from the business profile | No change |
| Due date | Already worked out from date and terms | No change |
| Paid and Overdue status | Already worked out | No change |
| Customer name, prices, hours | Only you know them | Asked in the form where they are used |

## How to rerun

```
pip install -e .[dev] playwright pypdf
python -m playwright install chromium
pytest -q                                   # core, schema, CLI, and the published-site browser test
python tests/make_vectors.py && node web/parity.test.mjs
python web/build_pages.py                   # docs/index.html must match web/app.html
```

`tests/test_published_site.py` fills the placeholders the way the release does, serves `docs/` under `/field-ticket/`, and runs the invoice, ticket, bundle, PDF, and backup workflows. It skips when Playwright is not installed. Set `PAGES_TEST_VENDOR` to a folder holding `jspdf.umd.min.js` to test the PDF without network access; the page still checks the file's integrity hash.

Test counts: 153 Python tests before this pass, 160 after (plus the parity script).

## Known limits

- A browser time box cannot hold `24:00`. Use `00:00` for a shift that ends at midnight; it gives the same hours.
- Browser storage is about 5 MB. Very large data sets import but cannot be saved; the page says so. Export a backup.
- The saved-customer picker on an open document lists a newly saved customer after you leave and reopen the document.
- The PDF uses Helvetica, so letters outside Latin-1 print as `?`. The preview shows them.
