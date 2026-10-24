"""Hand-checked cases for the money, date, hours, status, and conversion math."""

from __future__ import annotations

import copy

import pytest

import field_ticket as ft
from field_ticket.example import blank_state, example_state

TODAY = "2026-10-21"


def item(qty, rate, taxable=False, disc=0):
    return {"name": "x", "unit": "ea", "qty": qty, "rate_cents": rate, "taxable": taxable, "discount_pct": disc}


def doc(items, **kw):
    d = {"items": items, "discount_kind": "pct", "discount_value": 0, "tax_rate_pct": 0, "tax_mode": "document",
         "shipping_cents": 0, "deposit_cents": 0, "payments": []}
    d.update(kw)
    return d


# ------------------------------------------------------------ rounding

@pytest.mark.parametrize("n,d,q", [
    (1, 2, 1), (-1, 2, -1), (3, 2, 2), (-3, 2, -2), (5, 10, 1), (4, 10, 0), (-5, 10, -1),
    (15, 10, 2), (25, 10, 3), (2, 3, 1), (1, 3, 0), (-2, 3, -1), (0, 7, 0),
])
def test_div_round_half_away_from_zero(n, d, q):
    assert ft.div_round(n, d) == q


def test_div_round_exact_for_huge_numbers():
    assert ft.div_round(10**30 + 5, 10) == 10**29 + 1


def test_div_round_rejects_zero_divisor():
    with pytest.raises(ft.FieldTicketError):
        ft.div_round(1, 0)


# ------------------------------------------------------------ line totals

def test_line_total_simple():
    assert ft.line_totals(item(2, 1050)) == {"gross": 2100, "line_discount": 0, "net": 2100}


def test_line_total_fractional_qty_rounds_half_up():
    # 2.5 h x $85.00 = $212.50 exactly; 1.255 x $9.99 = 1253.745 cents -> 1254
    assert ft.line_totals(item(2.5, 8500))["net"] == 21250
    assert ft.line_totals(item(1.255, 999))["net"] == 1254
    assert ft.line_totals(item(0.5, 1))["net"] == 1
    assert ft.line_totals(item(0.333, 1))["net"] == 0


def test_line_discount_rounds_half_away_from_zero():
    # $10.05 at 50% off: discount 502.5 cents -> 503, net 502
    t = ft.line_totals(item(1, 1005, disc=50))
    assert t == {"gross": 1005, "line_discount": 503, "net": 502}


def test_line_discount_with_decimals():
    # 3 x 33.33 = 99.99; 12.5% = 12.49875 -> 12.50; net 87.49
    assert ft.line_totals(item(3, 3333, disc=12.5))["net"] == 8749


def test_float_noise_in_qty_is_absorbed():
    # 0.1 + 0.2 = 0.30000000000000004 reads as 0.300
    assert ft.line_totals(item(0.1 + 0.2, 1000))["net"] == 300


@pytest.mark.parametrize("bad", [
    item(-1, 100), item(1.0001, 100), item("2", 100), item(True, 100), item(float("nan"), 100),
    item(float("inf"), 100), item(1, 10.5), item(1, -1), item(1, 100, disc=100.5), item(1, 100, disc=-1),
    item(1000000, 1001),
])
def test_line_rejects_bad_values(bad):
    with pytest.raises(ft.FieldTicketError):
        ft.line_totals(bad)


# ------------------------------------------------------------ document totals

def test_document_percent_discount():
    t = ft.compute_totals(doc([item(1, 10000), item(1, 5001)], discount_value=10))
    assert (t["subtotal"], t["discount"], t["total"]) == (15001, 1500, 13501)


def test_document_amount_discount_capped_at_subtotal():
    t = ft.compute_totals(doc([item(1, 500)], discount_kind="amt", discount_value=900))
    assert t["discount"] == 500 and t["total"] == 0


def test_tax_rounding_document_vs_line_differs():
    # Three taxable 5 cent lines at 10%: per line 0.5 -> 1 each = 3; per document 1.5 -> 2.
    d = doc([item(1, 5, True)] * 3, tax_rate_pct=10)
    assert ft.compute_totals(d)["tax"] == 2
    d["tax_mode"] = "line"
    t = ft.compute_totals(d)
    assert t["tax"] == 3 and [ln["tax"] for ln in t["lines"]] == [1, 1, 1]


def test_tax_only_on_taxable_lines():
    # 8.25% of (199.99 + 3.33) = 16.7739 -> 16.77
    t = ft.compute_totals(doc([item(1, 19999, True), item(4, 1250), item(1, 333, True)], tax_rate_pct=8.25))
    assert t["taxable_base"] == 20332 and t["tax"] == 1677 and t["total"] == 25332 + 1677


def test_document_discount_reduces_tax_base_proportionally():
    # Lines 100.01 (taxable), 100.01, 0.03 (taxable); 15% off 200.05 = 30.0075 -> 30.01
    d = doc([item(1, 10001, True), item(1, 10001), item(1, 3, True)], tax_rate_pct=8.875, discount_value=15)
    t = ft.compute_totals(d)
    assert t["discount"] == 3001
    allocs = [ln["discount_alloc"] for ln in t["lines"]]
    # floor shares 1500, 1500, 0 leave 1 cent; the third line has the largest remainder (0.45).
    assert allocs == [1500, 1500, 1]
    assert t["taxable_base"] == (10001 - allocs[0]) + (3 - allocs[2])
    assert t["tax"] == ft.div_round(t["taxable_base"] * 8875, 100000)


def test_allocate_largest_remainder():
    assert ft.allocate(100, [1, 1, 1]) == [34, 33, 33]
    assert ft.allocate(2, [1, 1, 1]) == [1, 1, 0]
    assert ft.allocate(7, [0, 5, 5]) == [0, 4, 3]
    assert ft.allocate(10, [0, 0]) == [0, 0]
    for a, w in [(1001, [333, 667]), (99999, [12345, 67890, 1, 0, 19999])]:
        assert sum(ft.allocate(a, w)) == a


def test_payments_deposit_and_balance():
    d = doc([item(10, 4500, True)], tax_rate_pct=6.25, shipping_cents=4250, deposit_cents=20000,
            payments=[{"amount_cents": 15000}, {"amount_cents": 1}])
    t = ft.compute_totals(d)
    # 450.00 + 28.125 -> 28.13 tax + 42.50 shipping = 520.63; paid 350.01; balance 170.62
    assert (t["tax"], t["total"], t["paid"], t["balance"]) == (2813, 52063, 35001, 17062)


def test_overpayment_gives_negative_balance():
    t = ft.compute_totals(doc([item(1, 10000)], payments=[{"amount_cents": 12000}]))
    assert t["balance"] == -2000


def test_missing_optional_keys_default():
    t = ft.compute_totals({"items": [item(1, 100)]})
    assert t["total"] == 100 and t["tax"] == 0


@pytest.mark.parametrize("kw", [
    {"discount_kind": "percent"}, {"discount_value": 1.005}, {"tax_rate_pct": 8.2501}, {"tax_mode": "both"},
    {"shipping_cents": -1}, {"deposit_cents": 0.5}, {"payments": [{"amount_cents": "5"}]},
])
def test_document_rejects_bad_fields(kw):
    with pytest.raises(ft.FieldTicketError):
        ft.compute_totals(doc([item(1, 100)], **kw))


def test_too_many_items():
    with pytest.raises(ft.FieldTicketError):
        ft.compute_totals(doc([item(1, 1)] * 501))


# ------------------------------------------------------------ dates

@pytest.mark.parametrize("issue,terms,due", [
    ("2026-01-31", "net30", "2026-03-02"),   # Feb 2026 has 28 days
    ("2024-01-31", "net30", "2024-03-01"),   # Feb 2024 has 29 days
    ("2024-02-15", "net15", "2024-03-01"),
    ("2023-02-15", "net15", "2023-03-02"),
    ("2100-02-14", "net15", "2100-03-01"),   # 2100 is not a leap year
    ("2000-02-14", "net15", "2000-02-29"),   # 2000 is
    ("2024-12-17", "net15", "2025-01-01"),
    ("2026-12-31", "net60", "2027-03-01"),
    ("2024-12-31", "net60", "2025-03-01"),
    ("2026-03-31", "receipt", "2026-03-31"),
    ("2024-02-29", "net30", "2024-03-30"),
])
def test_due_dates(issue, terms, due):
    assert ft.due_date(issue, terms) == due


@pytest.mark.parametrize("bad", ["2026-02-29", "2026-13-01", "2026-1-01", "", "2026-04-31", None, "1899-12-31",
                                 "٢٠٢٦-01-01"])
def test_bad_dates(bad):
    with pytest.raises(ft.FieldTicketError):
        ft.due_date(bad, "net30")


def test_bad_terms():
    with pytest.raises(ft.FieldTicketError):
        ft.due_date("2026-01-01", "net45")


def test_days_between_and_leap_years():
    assert ft.days_between("2024-02-28", "2024-03-01") == 2
    assert ft.days_between("2023-02-28", "2023-03-01") == 1
    assert ft.days_between("1970-01-01", "2000-01-01") == 10957


# ------------------------------------------------------------ hours

@pytest.mark.parametrize("s,e,m", [
    ("06:00", "17:30", 690), ("19:00", "03:15", 495), ("00:00", "00:00", 1440), ("23:59", "00:00", 1),
    ("00:00", "24:00", 1440), ("22:45", "06:10", 445), ("12:00", "12:01", 1),
])
def test_shift_minutes(s, e, m):
    assert ft.shift_minutes(s, e) == m


@pytest.mark.parametrize("s,e", [("24:00", "06:00"), ("7:00", "15:00"), ("07:60", "15:00"), ("07:00", "24:01"), ("07:00", "")])
def test_shift_minutes_bad(s, e):
    with pytest.raises(ft.FieldTicketError):
        ft.shift_minutes(s, e)


def test_ticket_minutes_skips_incomplete_rows():
    out = ft.ticket_minutes([{"start": "06:00", "end": ""}, {"start": "08:00", "end": "08:20"}, {}])
    assert out == {"days": [None, 20, None], "total": 20}


@pytest.mark.parametrize("m,text", [(0, "0.00"), (1, "0.02"), (20, "0.33"), (30, "0.50"), (45, "0.75"), (1185, "19.75")])
def test_format_hours(m, text):
    assert ft.format_hours(m) == text


def test_hours_qty_three_decimals():
    assert ft.hours_qty(20) == 333 and ft.hours_qty(40) == 667 and ft.hours_qty(1185) == 19750


# ------------------------------------------------------------ formatting and parsing

def test_format_money():
    assert ft.format_money(0) == "$0.00"
    assert ft.format_money(123456) == "$1,234.56"
    assert ft.format_money(-5) == "-$0.05"
    assert ft.format_money(100000000) == "$1,000,000.00"


def test_doc_number():
    assert ft.format_doc_number("INV-", 1) == "INV-0001"
    assert ft.format_doc_number("FT-", 12345) == "FT-12345"


@pytest.mark.parametrize("text,c", [("", 0), ("12", 1200), ("12.5", 1250), ("$1,234.56", 123456), (".5", 50), ("5.", 500)])
def test_parse_money(text, c):
    assert ft.parse_money(text) == c


@pytest.mark.parametrize("text", ["12.345", "-5", "abc", ".", "1e3", "10000000.01", "$"])
def test_parse_money_bad(text):
    with pytest.raises(ft.FieldTicketError):
        ft.parse_money(text)


def test_csv_cell_neutralizes_formulas():
    assert ft.csv_cell("=SUM(A1)") == "'=SUM(A1)"
    assert ft.csv_cell("@x") == "'@x"
    assert ft.csv_cell("a,b") == '"a,b"'
    assert ft.csv_cell('say "hi"') == '"say ""hi"""'
    assert ft.csv_cell("Ok=1") == "Ok=1"


# ------------------------------------------------------------ status

def _inv(**kw):
    d = copy.deepcopy(example_state(TODAY)["docs"][0])
    d.update(kw)
    return d


def test_status_rules():
    assert ft.doc_status(_inv(status="draft", issue_date="2020-01-01"), TODAY) == "draft"
    assert ft.doc_status(_inv(status="sent", issue_date="2026-09-21"), TODAY) == "sent"       # due today
    assert ft.doc_status(_inv(status="sent", issue_date="2026-09-20"), TODAY) == "overdue"    # due yesterday
    assert ft.doc_status(_inv(status="paid", issue_date="2020-01-01"), TODAY) == "paid"
    full = _inv(status="sent", issue_date="2020-01-01", payments=[{"amount_cents": 49140}])
    assert ft.doc_status(full, TODAY) == "paid"


def test_summary_outstanding():
    a = _inv(id="a", status="sent", issue_date="2026-10-01")
    b = _inv(id="b", status="sent", issue_date="2026-01-01")
    c = _inv(id="c", status="draft")
    s = ft.summarize([a, b, c], TODAY)
    assert s["counts"]["sent"] == 1 and s["counts"]["overdue"] == 1 and s["counts"]["draft"] == 1
    assert s["outstanding"] == 2 * 49140 and s["overdue"] == 49140


# ------------------------------------------------------------ conversions

def _ticket(n, **kw):
    d = copy.deepcopy(example_state(TODAY)["docs"][1])
    d.update({"id": f"t{n}", "number": f"FT-{n:04d}"})
    d.update(kw)
    return d


def test_estimate_to_invoice_preserves_items_and_links_source():
    est = _inv(id="e1", type="estimate", number="EST-0003")
    inv = ft.estimate_to_invoice(est, "n1", "INV-0042", TODAY)
    assert inv["type"] == "invoice" and inv["number"] == "INV-0042" and inv["status"] == "draft"
    assert inv["items"] == est["items"] and inv["sources"] == ["EST-0003"]
    assert ft.compute_totals(inv)["total"] == ft.compute_totals(est)["total"]
    assert est["items"] is not inv["items"]


def test_tickets_to_invoice_bundles_in_order():
    a = _ticket(1, shipping_cents=1000, notes="A")
    b = _ticket(2, shipping_cents=250, notes="B")
    b["items"] = b["items"][:2]
    inv = ft.tickets_to_invoice([a, b], "n1", "INV-0010", TODAY)
    assert inv["items"] == a["items"] + b["items"]
    assert inv["sources"] == ["FT-0001", "FT-0002"]
    assert inv["shipping_cents"] == 1250 and inv["notes"] == "A\nB"
    assert len(inv["oil"]["days"]) == 4 and inv["oil"]["sig_company"] == ""
    # Same percent discount everywhere: totals add up except for rounding of shared tax.
    ta, tb, ti = (ft.compute_totals(x) for x in (a, b, inv))
    assert ti["subtotal"] == ta["subtotal"] + tb["subtotal"]


def test_tickets_mixed_discounts_become_amount():
    a = _ticket(1, discount_value=5)
    b = _ticket(2, discount_kind="amt", discount_value=1234)
    inv = ft.tickets_to_invoice([a, b], "n1", "INV-0010", TODAY)
    assert inv["discount_kind"] == "amt"
    assert inv["discount_value"] == ft.compute_totals(a)["discount"] + 1234


@pytest.mark.parametrize("mutate,code", [
    (lambda a, b: b.update(customer=dict(b["customer"], name="Other")), "mixed_customers"),
    (lambda a, b: b.update(tax_rate_pct=6.25), "mixed_tax"),
    (lambda a, b: b.update(converted_to="INV-0001"), "already_converted"),
    (lambda a, b: b.update(type="invoice"), "bad_source"),
])
def test_ticket_bundle_errors(mutate, code):
    a, b = _ticket(1), _ticket(2)
    mutate(a, b)
    with pytest.raises(ft.FieldTicketError) as ei:
        ft.tickets_to_invoice([a, b], "n1", "INV-0010", TODAY)
    assert ei.value.code == code


@pytest.mark.parametrize("mutate,code", [
    (lambda a, b: [x["oil"].update(days=[{"date": "", "start": "06:00", "end": "18:00", "note": ""}] * 32) for x in (a, b)], "too_many_days"),
    (lambda a, b: [x.update(payments=[{"date": "", "amount_cents": 1, "note": ""}] * 51) for x in (a, b)], "too_many_payments"),
    (lambda a, b: (a.update(notes="a" * 1000), b.update(notes="b" * 1000)), "notes_too_long"),
    (lambda a, b: [x.update(shipping_cents=600_000_000) for x in (a, b)], "amount_too_large"),
    (lambda a, b: [x.update(deposit_cents=600_000_000) for x in (a, b)], "amount_too_large"),
])
def test_bundle_never_makes_an_unloadable_invoice(mutate, code):
    """Review fix: a bundled invoice past a schema cap would make the saved state fail to load."""
    a, b = _ticket(1), _ticket(2)
    mutate(a, b)
    with pytest.raises(ft.FieldTicketError) as ei:
        ft.tickets_to_invoice([a, b], "n1", "INV-0010", TODAY)
    assert ei.value.code == code


def test_bundle_at_the_caps_still_loads():
    from field_ticket.schema import sanitize_state
    a, b = _ticket(1), _ticket(2)
    for x in (a, b):
        x["oil"]["days"] = [{"date": "", "start": "06:00", "end": "18:00", "note": ""}] * 31
        x["payments"] = [{"date": "", "amount_cents": 1, "note": ""}] * 50
        x["shipping_cents"] = 500_000_000
    a["notes"], b["notes"] = "a" * 999, "b" * 1000
    inv = ft.tickets_to_invoice([a, b], "n1", "INV-0010", TODAY)
    st = example_state(TODAY)
    st["docs"].append(inv)
    assert sanitize_state(st)["docs"][-1]["notes"] == inv["notes"]


def test_empty_bundle():
    with pytest.raises(ft.FieldTicketError):
        ft.tickets_to_invoice([], "n1", "INV-0010", TODAY)


# ------------------------------------------------------------ example state

def test_example_state_is_valid_and_labeled():
    st = example_state(TODAY)
    assert ft.sanitize_state(st) == st
    assert st["business"]["name"] == "Example Co."
    assert all(d["example"] for d in st["docs"])
    assert {d["type"] for d in st["docs"]} == {"invoice", "ticket"}
    assert st["docs"][1]["oil"]["enabled"]
    assert ft.ticket_minutes(st["docs"][1]["oil"]["days"])["total"] == 1185   # 11.5 h + 8.25 h


def test_blank_state_is_valid():
    st = blank_state()
    assert ft.sanitize_state(st) == st and st["docs"] == []
