# Field Ticket

Field Ticket is a free browser app for contractors and service companies. It makes estimates, oilfield field tickets, and invoices, and turns one into the next. It builds a print-ready PDF on the device. It runs entirely in the browser: nothing is uploaded, and there are no accounts.

Live tool: https://wjwhitmire.github.io/field-ticket/

The same totals, date, hours, and import-check math ships as a small Python library and CLI with zero runtime dependencies. A parity test holds the Python and JavaScript results equal, cent for cent.

## What it does

- Business profile: name, address, phone, email, license or tax ID, logo, default tax rate, tax rounding mode, payment terms, and payment instructions.
- Saved customers and a saved line-item catalog (item, unit, rate, taxable).
- Three document types: Estimate, Field Ticket, Invoice. Each type has its own number prefix and counter (`EST-0001`, `FT-0001`, `INV-0001` by default).
- Line items with quantity, unit, rate, taxable flag, and a per-line discount. A document discount as a percent or a dollar amount. Tax rounded once per document or per line. A shipping or mileage charge. Deposit and payments received. Balance due.
- Due date from terms: Due on receipt, Net 15, Net 30, Net 60.
- One-tap conversions: Estimate to Invoice, and one or more Field Tickets to one Invoice. The new invoice lists its source document numbers, and each source shows the invoice it went to.
- Oilfield field-ticket mode: operator, AFE number, lease, well, rig, county and state, PO, crew, a start and end time per day with hours worked out (across midnight too), and signature boxes for the company representative and the crew lead.
- Status: draft, sent, paid, and overdue (worked out from the due date). The list shows money outstanding and overdue.
- PDF built in the browser with jsPDF, plus a full on-screen preview.
- Export all (a JSON backup you can copy) and Import (paste or pick a file) to back up or move to another device.

It opens with clearly labeled example data: a made-up business (Example Co.), two made-up customers, a catalog, one sample invoice, and one sample oilfield field ticket. "Start fresh" removes the examples after an in-page confirmation and keeps anything you added.

## Quick start

Browser: open the live tool, or open `docs/index.html` locally. Use it on a phone; every control is a large tap target and the layout works at 360 px wide.

Python:

```
pip install -e .[dev]
field-ticket totals doc.json            # totals for one document
field-ticket check backup.json          # validate a backup from Export all
field-ticket summary backup.json --today 2026-10-21 --json
```

```python
from field_ticket import compute_totals, due_date, shift_minutes, format_money

doc = {
    "items": [
        {"name": "Vacuum truck", "unit": "hr", "qty": 19.75, "rate_cents": 12500, "taxable": False, "discount_pct": 0},
        {"name": "Fittings", "unit": "ea", "qty": 3, "rate_cents": 4275, "taxable": True, "discount_pct": 0},
    ],
    "discount_kind": "pct", "discount_value": 0,
    "tax_rate_pct": 8.25, "tax_mode": "line",
    "shipping_cents": 0, "deposit_cents": 0, "payments": [],
}
t = compute_totals(doc)
print(format_money(t["total"]))          # $2,607.58
print(due_date("2024-01-31", "net30"))   # 2024-03-01
print(shift_minutes("19:00", "03:15"))   # 495
```

## Method and equations

Money is an integer number of cents everywhere. Quantities carry at most 3 decimals, discounts at most 2, and the tax rate at most 3. Each one is turned into a scaled integer (qty x 1000, percent x 100, tax rate x 1000) before any arithmetic, so no floating point value ever touches a money amount. The JavaScript core uses BigInt for the products, so both languages are exact.

`round(n / d)` below means: the nearest integer, and an exact half rounds away from zero. In integers, `q = floor((2|n| + d) / 2d)` with the sign of `n`.

| Quantity | Equation |
|---|---|
| Line amount | `gross = round(qty_milli x rate_cents / 1000)` |
| Line discount | `line_disc = round(gross x disc_pct_x100 / 10000)` |
| Line net | `net = gross - line_disc` |
| Subtotal | `subtotal = sum(net)` |
| Document discount, percent | `discount = round(subtotal x pct_x100 / 10000)` |
| Document discount, amount | `discount = min(amount_cents, subtotal)` |
| Discount share per line | largest remainder: `floor(discount x net_i / subtotal)`, leftover cents to the largest remainders, ties to the earlier line. Shares always sum to `discount`. |
| Tax base per line | `base_i = net_i - share_i` if taxable, else 0 |
| Tax, per document | `tax = round(sum(base_i) x rate_x1000 / 100000)` |
| Tax, per line | `tax = sum(round(base_i x rate_x1000 / 100000))` |
| Total | `total = subtotal - discount + tax + shipping` |
| Paid | `paid = deposit + sum(payments)` |
| Balance | `balance = total - paid` (negative is a credit) |
| Due date | `issue date + 0, 15, 30, or 60 days` (proleptic Gregorian calendar; days counted with H. Hinnant's `days_from_civil` and `civil_from_days` algorithms) |
| Shift minutes | `end - start`, plus 1440 when `end <= start` (past midnight); `end` may be `24:00` |
| Hours shown | `round(minutes x 100 / 60) / 100` |
| Labor quantity from hours | `round(minutes x 1000 / 60) / 1000` (20 minutes is 0.333 h) |

Per document versus per line tax: three taxable 5 cent lines at 10% give 1.5 cents of tax per document, which rounds to 2. Per line, each 0.5 cent rounds to 1, for 3. Both are common; set the one your state or customer uses.

Status rules for an invoice: Paid when marked Paid, or when deposit and payments cover a positive total (or a sent invoice has nothing left to pay). A Draft stays Draft. A Sent invoice is Overdue from the day after its due date. Estimates and field tickets show Converted once invoiced. Outstanding is the sum of balances on Sent and Overdue invoices.

Conversions. Estimate to Invoice copies items, pricing, tax settings, deposit, notes, customer, and oilfield fields; it clears payments and signatures and records the estimate number in `sources`. Field Tickets to Invoice copies all items in ticket order unchanged and adds up shipping, deposits, and payments. The tickets must share a customer (matched ignoring ASCII case and extra spaces) and the same tax rate and mode, because one invoice has one tax setting. If every ticket has the same percent discount it carries over; otherwise the invoice gets a dollar discount equal to the sum of each ticket's discount in cents. Day rows carry over; signatures do not, because the invoice is a new document.

## Limits

- Not tax or legal advice. One tax rate per document. No compound or multi-jurisdiction tax, no tax on shipping, no withholding or retainage.
- US dollars only. Any money field and any one line amount is capped at $10,000,000.00. Quantity is capped at 1,000,000 and 500 lines per document.
- A bundle is refused, with a message, when the combined invoice would pass a per-document cap: 62 day rows, 100 payments, 2,000 characters of notes, or $10,000,000.00 of shipping, deposits, or combined discounts.
- When tickets with different discounts are bundled, tax is recomputed on the combined invoice. The invoice tax can differ by a cent or two from the sum of the ticket taxes because of rounding.
- Hours have no overtime, break, or lunch deduction, and no day longer than 24 hours per row.
- Data lives in the browser's localStorage on one device. Clearing site data, private windows, or some phone storage cleanups erase it. Export a backup often. Browser storage quotas (often about 5 MB) limit how many documents with signatures one device can hold.
- The PDF uses the built-in Helvetica font, which covers Western European (Latin-1) letters only. Other characters print as `?`. The on-screen preview shows them correctly.
- A drawn signature is a picture of a signature, not a verified electronic signature.
- In viewers that block downloads (for example an embedded preview), Download PDF cannot save a file. The page says so and the on-screen preview shows the same document. On GitHub Pages the download works.

## Data and backup format

Export all writes one JSON object: `{"app": "field-ticket", "version": 1, "business", "settings", "customers", "catalog", "docs"}`. Import checks it against a strict schema (in both `field_ticket/schema.py` and the page) before anything is replaced: known keys only, every string length capped, control characters removed, numbers range and decimal checked, money as whole cents, dates as real `YYYY-MM-DD` dates, times as `HH:MM`, images only as PNG or JPEG data URLs, unique ids. Any problem stops the import with a message naming the field, and nothing on the device changes. If data already on the device fails this check when the page opens, it is left untouched, a copy is kept under the `field-ticket:v1:unreadable` storage key, and nothing is saved over it until you import a backup or choose Start fresh.

## Validation

- `pytest -q`: hand-checked cases for rounding, line totals, discounts, per-line versus per-document tax, payments and balance, due dates across month ends and leap years (2024, 2000, and the non-leap 2100), shifts across midnight, status, conversions, the example data, import validation, and the CLI.
- `python tests/make_vectors.py && node web/parity.test.mjs`: runs the JavaScript core from `web/app.html` against the Python results for every vector. All comparisons are exact.
- A pytest case fails if `tests/vectors.json` is stale.

## Build

```
pip install -e .[dev]
pytest -q
python tests/make_vectors.py && node web/parity.test.mjs
python web/build_pages.py      # writes docs/index.html for GitHub Pages
```

## Third-party code

The PDF is built with [jsPDF](https://github.com/parallax/jsPDF) 4.2.1 (MIT license), loaded from `https://cdnjs.cloudflare.com/ajax/libs/jspdf/4.2.1/jspdf.umd.min.js` with a Subresource Integrity hash. If it fails to load, everything except the PDF download still works.

## License

MIT. Copyright 2026 Will Whitmire. See `LICENSE`.
