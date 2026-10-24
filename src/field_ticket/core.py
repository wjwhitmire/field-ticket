"""Money, date, hours, numbering, status, and conversion math for Field Ticket.

Every amount of money is an integer number of cents. Quantities carry at most
three decimals, percents at most two (discounts) or three (tax rate), and each
one is converted to a scaled integer before any arithmetic, so no float ever
touches a money value. The browser tool in web/app.html mirrors this module
line for line; web/parity.test.mjs checks the two against tests/vectors.json.

Rounding: every division that produces cents rounds half away from zero
(div_round). Line amounts are rounded per line. Tax is rounded once per
document or once per line, as the document's tax_mode says.
"""

from __future__ import annotations

import copy
import math
import re

MAX_CENTS = 1_000_000_000            # $10,000,000.00 cap on any money field and on any line amount
MAX_QTY = 1_000_000                 # units per line
MAX_ITEMS = 500                     # line items per document
DOC_TYPES = ("estimate", "ticket", "invoice")
STATUSES = ("draft", "sent", "paid")
TERMS = {"receipt": 0, "net15": 15, "net30": 30, "net60": 60}
TERMS_LABEL = {"receipt": "Due on receipt", "net15": "Net 15", "net30": "Net 30", "net60": "Net 60"}
TYPE_LABEL = {"estimate": "Estimate", "ticket": "Field Ticket", "invoice": "Invoice"}


class FieldTicketError(ValueError):
    """Bad input. code is stable and machine readable; message is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- rounding

def div_round(n: int, d: int) -> int:
    """n / d rounded to the nearest integer, halves away from zero. d > 0.

    Python integers are exact at any size; the JS mirror uses BigInt for the
    products that feed this function, so both stay exact.
    """
    if d <= 0:
        raise FieldTicketError("bad_divisor", "Divisor must be positive.")
    q = (abs(n) * 2 + d) // (2 * d)
    return q if n >= 0 else -q


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def scaled(x, places: int, lo: float, hi: float, name: str) -> int:
    """Number with at most `places` decimals, lo <= x <= hi, as an integer x * 10**places."""
    msg = f"{name}: must be a number from {_plain(lo)} to {_plain(hi)} with at most {places} decimals."
    if not is_number(x) or x < lo or x > hi:
        raise FieldTicketError("bad_field", msg)
    v = x * (10 ** places)
    r = math.floor(v + 0.5) if v >= 0 else -math.floor(-v + 0.5)
    if abs(v - r) > 1e-4:
        raise FieldTicketError("bad_field", msg)
    return int(r)


def cents(x, name: str, lo: int = 0, hi: int = MAX_CENTS) -> int:
    msg = f"{name}: must be a whole number of cents from {_plain(lo)} to {_plain(hi)}."
    if not is_number(x):
        raise FieldTicketError("bad_field", msg)
    if isinstance(x, float):
        if not x.is_integer():
            raise FieldTicketError("bad_field", msg)
        x = int(x)
    if x < lo or x > hi:
        raise FieldTicketError("bad_field", msg)
    return x


def _plain(v) -> str:
    """Format a limit the same way JS String(number) does for the limits used here."""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


# ---------------------------------------------------------------- totals

def line_totals(item: dict, path: str = "item") -> dict:
    """gross = qty x rate, then the line discount. Both rounded half away from zero."""
    if not isinstance(item, dict):
        raise FieldTicketError("bad_field", path + ": must be an object.")
    qm = scaled(item.get("qty"), 3, 0, MAX_QTY, path + ".qty")
    rate = cents(item.get("rate_cents"), path + ".rate_cents")
    dp = scaled(item.get("discount_pct", 0), 2, 0, 100, path + ".discount_pct")
    gross = div_round(qm * rate, 1000)
    if gross > MAX_CENTS:
        raise FieldTicketError("bad_field", path + ": line amount is over $10,000,000.00. Split it into smaller lines.")
    ldisc = div_round(gross * dp, 10000)
    return {"gross": gross, "line_discount": ldisc, "net": gross - ldisc}


def allocate(amount: int, weights: list[int]) -> list[int]:
    """Split amount across weights in proportion, largest remainder method.

    Each share is floor(amount x w / sum); leftover cents go to the largest
    remainders, ties to the earlier line. Shares always sum to amount.
    """
    total = sum(weights)
    if total <= 0 or amount == 0:
        return [0] * len(weights)
    base = [amount * w // total for w in weights]
    rem = [amount * w % total for w in weights]
    left = amount - sum(base)
    for i in sorted(range(len(weights)), key=lambda k: (-rem[k], k))[:left]:
        base[i] += 1
    return base


def compute_totals(doc: dict) -> dict:
    """Totals for one document. All results are integer cents.

    subtotal = sum of line nets
    discount = round(subtotal x pct / 100) or min(amount, subtotal)
    the discount is allocated to lines by net (largest remainder) to get each
    taxable line's tax base; tax = round(sum(bases) x rate) per document or
    sum(round(base x rate)) per line
    total = subtotal - discount + tax + shipping
    balance = total - deposit - payments
    """
    items = doc.get("items")
    if items is None:
        items = []
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise FieldTicketError("bad_field", f"items: must be a list of at most {MAX_ITEMS} entries.")
    lines = [line_totals(it, f"items[{i}]") for i, it in enumerate(items)]
    subtotal = sum(ln["net"] for ln in lines)

    kind = doc.get("discount_kind", "pct")
    val = doc.get("discount_value", 0)
    if kind == "pct":
        dp = scaled(val, 2, 0, 100, "discount_value")
        discount = div_round(subtotal * dp, 10000)
    elif kind == "amt":
        discount = min(cents(val, "discount_value"), subtotal)
    else:
        raise FieldTicketError("bad_field", "discount_kind: must be one of pct, amt.")

    alloc = allocate(discount, [ln["net"] for ln in lines])
    rate_m = scaled(doc.get("tax_rate_pct", 0), 3, 0, 100, "tax_rate_pct")
    mode = doc.get("tax_mode", "document")
    if mode not in ("document", "line"):
        raise FieldTicketError("bad_field", "tax_mode: must be one of document, line.")

    out_lines = []
    taxable_base = 0
    tax = 0
    for i, ln in enumerate(lines):
        base = ln["net"] - alloc[i] if items[i].get("taxable") is True else 0
        taxable_base += base
        t = div_round(base * rate_m, 100000) if mode == "line" else None
        if t is not None:
            tax += t
        out_lines.append(dict(ln, discount_alloc=alloc[i], tax_base=base, tax=t))
    if mode == "document":
        tax = div_round(taxable_base * rate_m, 100000)

    shipping = cents(doc.get("shipping_cents", 0), "shipping_cents")
    deposit = cents(doc.get("deposit_cents", 0), "deposit_cents")
    pays = doc.get("payments")
    if pays is None:
        pays = []
    if not isinstance(pays, list):
        raise FieldTicketError("bad_field", "payments: must be a list.")
    payments = 0
    for i, p in enumerate(pays):
        if not isinstance(p, dict):
            raise FieldTicketError("bad_field", f"payments[{i}]: must be an object.")
        payments += cents(p.get("amount_cents"), f"payments[{i}].amount_cents")
    total = subtotal - discount + tax + shipping
    paid = deposit + payments
    return {
        "lines": out_lines,
        "subtotal": subtotal,
        "discount": discount,
        "taxable_base": taxable_base,
        "tax": tax,
        "shipping": shipping,
        "total": total,
        "deposit": deposit,
        "payments": payments,
        "paid": paid,
        "balance": total - paid,
    }


# ---------------------------------------------------------------- dates

DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y: int, m: int) -> int:
    return [31, 29 if is_leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def parse_date(s, name: str = "date") -> tuple[int, int, int]:
    m = DATE_RE.fullmatch(s) if isinstance(s, str) else None
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2999 and 1 <= mo <= 12 and 1 <= d <= days_in_month(y, mo):
            return y, mo, d
    raise FieldTicketError("bad_field", f"{name}: must be a date written YYYY-MM-DD.")


def days_from_civil(y: int, m: int, d: int) -> int:
    """Days since 1970-01-01 in the proleptic Gregorian calendar (H. Hinnant)."""
    y -= m <= 2
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z: int) -> tuple[int, int, int]:
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (m <= 2), m, d


def add_days(s: str, n: int) -> str:
    y, m, d = civil_from_days(days_from_civil(*parse_date(s)) + n)
    return f"{y:04d}-{m:02d}-{d:02d}"


def due_date(issue_date: str, terms: str) -> str:
    if terms not in TERMS:
        raise FieldTicketError("bad_field", "terms: must be one of " + ", ".join(TERMS) + ".")
    return add_days(issue_date, TERMS[terms])


def days_between(a: str, b: str) -> int:
    """b - a in days."""
    return days_from_civil(*parse_date(b)) - days_from_civil(*parse_date(a))


# ---------------------------------------------------------------- hours

TIME_RE = re.compile(r"([0-9]{2}):([0-9]{2})")


def parse_time(s, name: str = "time", allow_24: bool = False) -> int:
    m = TIME_RE.fullmatch(s) if isinstance(s, str) else None
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if (h <= 23 and mi <= 59) or (allow_24 and h == 24 and mi == 0):
            return h * 60 + mi
    raise FieldTicketError("bad_field", f"{name}: must be a time written HH:MM, or blank.")


def shift_minutes(start: str, end: str) -> int:
    """Minutes from start to end on a 24 hour clock, no overtime split.

    An end at or before the start means the shift ran past midnight, so a day
    is added. Equal times mean a full 24 hour day. End may be 24:00.
    """
    s = parse_time(start, "start")
    e = parse_time(end, "end", allow_24=True)
    if e <= s:
        e += 1440
    return e - s


def ticket_minutes(days: list) -> dict:
    """Minutes per day row (None when start or end is blank) and the total."""
    per = []
    if days is None:
        days = []
    for i, d in enumerate(days):
        if not isinstance(d, dict):
            raise FieldTicketError("bad_field", f"days[{i}]: must be an object.")
        st, en = d.get("start", ""), d.get("end", "")
        if not st or not en:
            per.append(None)
            continue
        try:
            per.append(shift_minutes(st, en))
        except FieldTicketError as exc:
            raise FieldTicketError("bad_field", f"days[{i}]." + exc.message) from None
    return {"days": per, "total": sum(m for m in per if m is not None)}


def hours_qty(minutes: int) -> int:
    """Minutes as thousandths of an hour (a line quantity has three decimals), half away from zero."""
    return div_round(minutes * 1000, 60)


def format_hours(minutes: int) -> str:
    """Minutes as decimal hours, two places, half away from zero."""
    c = div_round(minutes * 100, 60)
    sign = "-" if c < 0 else ""
    c = abs(c)
    return f"{sign}{c // 100}.{c % 100:02d}"


# ---------------------------------------------------------------- formatting

def format_money(c: int) -> str:
    sign = "-" if c < 0 else ""
    c = abs(int(c))
    return f"{sign}${c // 100:,}.{c % 100:02d}"


def format_doc_number(prefix: str, n: int) -> str:
    return f"{prefix}{n:04d}"


# ---------------------------------------------------------------- status

def doc_status(doc: dict, today: str) -> str:
    """draft, sent, paid, overdue (invoices), or converted (estimates, tickets).

    Invoice: paid when marked paid, when a sent invoice has nothing left to
    pay, or when deposit and payments cover a positive total; otherwise a
    draft stays draft, and a sent invoice is overdue from the day after its
    due date.
    """
    if doc["type"] != "invoice":
        return "converted" if doc.get("converted_to") else doc.get("status", "draft")
    t = compute_totals(doc)
    settled = t["balance"] <= 0 and (t["total"] > 0 or doc.get("status") != "draft")
    if doc.get("status") == "paid" or settled:
        return "paid"
    if doc.get("status") == "draft":
        return "draft"
    if today > due_date(doc["issue_date"], doc.get("terms", "net30")):
        return "overdue"
    return "sent"


def summarize(docs: list, today: str) -> dict:
    """Counts by status and money outstanding on sent and overdue invoices."""
    counts = {k: 0 for k in ("draft", "sent", "paid", "overdue", "converted")}
    outstanding = overdue = 0
    for d in docs:
        st = doc_status(d, today)
        counts[st] += 1
        if d["type"] == "invoice" and st in ("sent", "overdue"):
            bal = compute_totals(d)["balance"]
            outstanding += bal
            if st == "overdue":
                overdue += bal
    return {"counts": counts, "outstanding": outstanding, "overdue": overdue}


# ---------------------------------------------------------------- conversions

def _clone(x):
    return copy.deepcopy(x)


def _blank_sigs(oil: dict) -> dict:
    oil = _clone(oil)
    for k in ("sig_company", "sig_crew"):
        oil[k] = ""
    return oil


def estimate_to_invoice(est: dict, new_id: str, number: str, issue_date: str) -> dict:
    """One tap Estimate to Invoice. Items, pricing, tax, and deposit carry over."""
    if est.get("type") != "estimate":
        raise FieldTicketError("bad_source", "Only an estimate can be converted with this action.")
    if est.get("converted_to"):
        raise FieldTicketError("already_converted", f"{est['number']} was already converted to {est['converted_to']}.")
    parse_date(issue_date, "issue_date")
    inv = _clone(est)
    inv.update({
        "id": new_id, "type": "invoice", "number": number, "status": "draft",
        "issue_date": issue_date, "payments": [], "sources": [est["number"]], "converted_to": "",
    })
    inv["oil"] = _blank_sigs(est["oil"])
    return inv


ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def customer_key(name: str) -> str:
    """Customer names match ignoring ASCII case and runs of spaces, tabs, or newlines."""
    return re.sub(r"[ \t\n]+", " ", name).strip(" ").translate(ASCII_LOWER)


NOTES_MAX = 2000   # same cap as schema.py s_doc notes


def _check_bundle_fits(tickets: list) -> None:
    """Refuse a bundle whose invoice the backup schema would reject.

    Without this, the invoice is saved, and the next load or import of the
    whole state fails on it.
    """
    from .schema import MAX_DAYS, MAX_PAYMENTS, MAX_SOURCES, ulen
    n_days = sum(len(t["oil"]["days"]) for t in tickets)
    if n_days > MAX_DAYS:
        raise FieldTicketError("too_many_days", f"The bundle has {n_days} day rows; an invoice holds at most {MAX_DAYS}. Bundle fewer tickets.")
    n_pay = sum(len(t["payments"]) for t in tickets)
    if n_pay > MAX_PAYMENTS:
        raise FieldTicketError("too_many_payments", f"The bundle has {n_pay} payments; an invoice holds at most {MAX_PAYMENTS}. Bundle fewer tickets.")
    if len(tickets) > MAX_SOURCES:
        raise FieldTicketError("too_many_tickets", f"An invoice can list at most {MAX_SOURCES} source tickets.")
    notes = []
    for t in tickets:
        n = t.get("notes", "")
        if n and n not in notes:
            notes.append(n)
    if ulen("\n".join(notes)) > NOTES_MAX:
        raise FieldTicketError("notes_too_long", f"The tickets' notes together are over {NOTES_MAX} characters. Shorten them, then bundle.")
    for k, label in (("shipping_cents", "shipping"), ("deposit_cents", "deposits")):
        if sum(t[k] for t in tickets) > MAX_CENTS:
            raise FieldTicketError("amount_too_large", f"The combined {label} total is over $10,000,000.00. Bundle fewer tickets.")
    mixed = not all(t["discount_kind"] == "pct" and t["discount_value"] == tickets[0]["discount_value"] for t in tickets)
    if mixed and sum(compute_totals(t)["discount"] for t in tickets) > MAX_CENTS:
        raise FieldTicketError("amount_too_large", "The combined discounts are over $10,000,000.00. Bundle fewer tickets.")


def tickets_to_invoice(tickets: list, new_id: str, number: str, issue_date: str) -> dict:
    """Bundle one or more field tickets into one invoice.

    Items are copied in ticket order, unchanged. Shipping, deposits, and
    payments add up. Tickets must share customer, tax rate, and tax mode. A
    shared percent discount carries over; any other discount mix becomes the
    sum of each ticket's discount in cents.
    """
    if not tickets:
        raise FieldTicketError("no_tickets", "Pick at least one field ticket.")
    for t in tickets:
        if t.get("type") != "ticket":
            raise FieldTicketError("bad_source", f"{t.get('number', '?')} is not a field ticket.")
        if t.get("converted_to"):
            raise FieldTicketError("already_converted", f"{t['number']} was already invoiced on {t['converted_to']}.")
    first = tickets[0]
    key = customer_key(first["customer"]["name"])
    for t in tickets[1:]:
        if customer_key(t["customer"]["name"]) != key:
            raise FieldTicketError("mixed_customers", "These tickets are for different customers. Bundle one customer at a time.")
        if t["tax_rate_pct"] != first["tax_rate_pct"] or t["tax_mode"] != first["tax_mode"]:
            raise FieldTicketError("mixed_tax", "These tickets use different tax settings. Make them match, then bundle.")
    items = [_clone(it) for t in tickets for it in t["items"]]
    if len(items) > MAX_ITEMS:
        raise FieldTicketError("too_many_items", f"The bundle has {len(items)} line items; the limit is {MAX_ITEMS}.")
    parse_date(issue_date, "issue_date")
    _check_bundle_fits(tickets)

    if all(t["discount_kind"] == "pct" and t["discount_value"] == first["discount_value"] for t in tickets):
        dkind, dval = "pct", first["discount_value"]
    else:
        dkind, dval = "amt", sum(compute_totals(t)["discount"] for t in tickets)

    notes = []
    for t in tickets:
        n = t.get("notes", "")
        if n and n not in notes:
            notes.append(n)
    oil = _blank_sigs(first["oil"])
    oil["enabled"] = any(t["oil"]["enabled"] for t in tickets)
    oil["days"] = [_clone(d) for t in tickets for d in t["oil"]["days"]]
    inv = _clone(first)
    inv.update({
        "id": new_id, "type": "invoice", "number": number, "status": "draft", "issue_date": issue_date,
        "items": items, "discount_kind": dkind, "discount_value": dval,
        "shipping_cents": sum(t["shipping_cents"] for t in tickets),
        "deposit_cents": sum(t["deposit_cents"] for t in tickets),
        "payments": [_clone(p) for t in tickets for p in t["payments"]],
        "notes": "\n".join(notes), "sources": [t["number"] for t in tickets], "converted_to": "",
        "oil": oil,
    })
    return inv


# ---------------------------------------------------------------- text input

DEC_RE = re.compile(r"([0-9]*)(?:\.([0-9]*))?")


def parse_decimal(s, places: int, name: str, hi: int) -> int:
    """Text such as "1,234.5" to an integer scaled by 10**places, exactly.

    Spaces, commas, and a leading $ are ignored. Blank is 0. Negative numbers,
    more than `places` decimals, and values over hi (scaled) are rejected.
    """
    if not isinstance(s, str):
        raise FieldTicketError("bad_field", f"{name}: must be text.")
    t = s.replace(" ", "").replace(",", "")
    if t == "":
        return 0
    if t.startswith("$"):
        t = t[1:]
    m = DEC_RE.fullmatch(t)
    if not m or (m.group(1) == "" and not m.group(2)):
        raise FieldTicketError("bad_field", f"{name}: enter a number such as 12 or 12.50.")
    frac = m.group(2) or ""
    if len(frac) > places:
        raise FieldTicketError("bad_field", f"{name}: use at most {places} decimals.")
    whole = m.group(1).lstrip("0") or "0"
    if len(whole) > 12:
        raise FieldTicketError("bad_field", f"{name}: is too large.")
    v = int(whole) * (10 ** places) + int((frac + "0" * places)[:places] or "0")
    if v > hi:
        raise FieldTicketError("bad_field", f"{name}: is too large.")
    return v


def parse_money(s, name: str = "amount") -> int:
    """Text to integer cents."""
    return parse_decimal(s, 2, name, MAX_CENTS)


# ---------------------------------------------------------------- CSV list export

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(text: str) -> str:
    """One CSV field. Text that a spreadsheet would read as a formula gets a leading quote."""
    if text.startswith(FORMULA_START):
        text = "'" + text
    if any(ch in text for ch in ',"\n\r'):
        text = '"' + text.replace('"', '""') + '"'
    return text


def cents_plain(c: int) -> str:
    sign = "-" if c < 0 else ""
    c = abs(c)
    return f"{sign}{c // 100}.{c % 100:02d}"


def docs_csv(docs: list, today: str) -> str:
    rows = ["Number,Type,Status,Date,Due,Customer,Total,Balance"]
    for d in docs:
        t = compute_totals(d)
        due = due_date(d["issue_date"], d.get("terms", "net30")) if d["type"] == "invoice" else ""
        rows.append(",".join([
            csv_cell(d["number"]), TYPE_LABEL[d["type"]], doc_status(d, today), d["issue_date"], due,
            csv_cell(d["customer"]["name"]), cents_plain(t["total"]), cents_plain(t["balance"]),
        ]))
    return "\n".join(rows) + "\n"
