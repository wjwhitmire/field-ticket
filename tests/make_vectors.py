"""Generate tests/vectors.json from the Python library.

web/parity.test.mjs runs the JavaScript core in web/app.html against these
vectors. Run: python tests/make_vectors.py
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import field_ticket as ft  # noqa: E402
from field_ticket.example import blank_state, clear_examples, example_state  # noqa: E402

TODAY = "2026-10-21"


def item(qty, rate, taxable=False, disc=0, name="x", unit="ea"):
    return {"name": name, "unit": unit, "qty": qty, "rate_cents": rate, "taxable": taxable, "discount_pct": disc}


def doc(items, **kw):
    d = {"items": items, "discount_kind": "pct", "discount_value": 0, "tax_rate_pct": 0, "tax_mode": "document",
         "shipping_cents": 0, "deposit_cents": 0, "payments": []}
    d.update(kw)
    return d


TOTALS = {
    "empty": doc([]),
    "one_line": doc([item(2, 1050)]),
    "fractional_qty_half_up": doc([item(0.5, 1)]),          # 0.5 cent rounds to 1
    "fractional_qty_below_half": doc([item(0.333, 1)]),     # 0.333 cent rounds to 0
    "qty_three_decimals": doc([item(1.255, 999)]),          # 1253.745 -> 1254
    "line_discount_half": doc([item(1, 1005, disc=50)]),    # 502.5 -> 503 discount
    "line_discount_pct_decimals": doc([item(3, 3333, disc=12.5)]),
    "doc_discount_pct": doc([item(1, 10000), item(1, 5001)], discount_value=10),
    "doc_discount_amount": doc([item(1, 10000), item(2, 2500)], discount_kind="amt", discount_value=1234),
    "doc_discount_amount_over_subtotal": doc([item(1, 500)], discount_kind="amt", discount_value=900),
    # Three taxable lines at 0.05 each: per-line tax rounds each 0.4125 cent... use a case where modes differ.
    "tax_doc_vs_line_doc": doc([item(1, 5, True), item(1, 5, True), item(1, 5, True)], tax_rate_pct=10),
    "tax_doc_vs_line_line": doc([item(1, 5, True), item(1, 5, True), item(1, 5, True)], tax_rate_pct=10, tax_mode="line"),
    "tax_mixed_taxable_doc": doc([item(1, 19999, True), item(4, 1250), item(1, 333, True)], tax_rate_pct=8.25),
    "tax_mixed_taxable_line": doc([item(1, 19999, True), item(4, 1250), item(1, 333, True)], tax_rate_pct=8.25, tax_mode="line"),
    "tax_after_doc_discount_doc": doc([item(1, 10001, True), item(1, 10001), item(1, 3, True)], tax_rate_pct=8.875, discount_value=15),
    "tax_after_doc_discount_line": doc([item(1, 10001, True), item(1, 10001), item(1, 3, True)], tax_rate_pct=8.875,
                                       discount_value=15, tax_mode="line"),
    "tax_three_decimal_rate": doc([item(7, 1999, True)], tax_rate_pct=7.125),
    "allocation_tie_breaks": doc([item(1, 1, True), item(1, 1, True), item(1, 1, True)], discount_kind="amt", discount_value=2,
                                 tax_rate_pct=50, tax_mode="line"),
    "shipping_deposit_payments": doc([item(10, 4500, True)], tax_rate_pct=6.25, shipping_cents=4250, deposit_cents=20000,
                                     payments=[{"date": "2026-01-05", "amount_cents": 15000, "note": "check 101"},
                                               {"date": "", "amount_cents": 1, "note": ""}]),
    "overpaid_negative_balance": doc([item(1, 10000)], payments=[{"date": "", "amount_cents": 12000, "note": ""}]),
    "zero_qty_and_zero_rate": doc([item(0, 5000, True), item(5, 0, True)], tax_rate_pct=10),
    "hundred_pct_discounts": doc([item(2, 777, True, disc=100), item(1, 1000, True)], discount_value=100, tax_rate_pct=10),
    "large_values": doc([item(1000000, 1000, True), item(999.999, 999999, True)], tax_rate_pct=99.999, tax_mode="line"),
    "large_values_doc": doc([item(1000000, 1000, True), item(999.999, 999999, True)], tax_rate_pct=99.999),
    "float_noise_inputs": doc([item(0.1 + 0.2, 333, True, disc=0.1 + 0.2)], tax_rate_pct=8.1 + 0.15),
    "float_integral_cents": doc([item(1, 1500.0)], shipping_cents=200.0),
    "missing_optional_keys": {"items": [item(1, 100)]},
    "example_invoice": example_state(TODAY)["docs"][0],
    "example_ticket": example_state(TODAY)["docs"][1],
}

TOTALS_ERRORS = {
    "negative_qty": doc([item(-1, 100)]),
    "qty_four_decimals": doc([item(1.0001, 100)]),
    "qty_string": doc([item("2", 100)]),
    "qty_bool": doc([item(True, 100)]),
    "qty_over_cap": doc([item(1000001, 1)]),
    "rate_fraction_of_cent": doc([item(1, 10.5)]),
    "rate_negative": doc([item(1, -5)]),
    "rate_over_cap": doc([item(1, 1000000001)]),
    "line_amount_over_cap": doc([item(1000000, 1001)]),
    "line_discount_over_100": doc([item(1, 100, disc=101)]),
    "doc_discount_three_decimals": doc([item(1, 100)], discount_value=1.005),
    "doc_discount_kind_bad": doc([item(1, 100)], discount_kind="percent"),
    "tax_rate_four_decimals": doc([item(1, 100)], tax_rate_pct=8.2501),
    "tax_mode_bad": doc([item(1, 100)], tax_mode="both"),
    "shipping_negative": doc([item(1, 100)], shipping_cents=-1),
    "payment_fraction": doc([item(1, 100)], payments=[{"amount_cents": 0.5}]),
    "items_not_list": {"items": {"a": 1}},
    "too_many_items": doc([item(1, 1)] * 501),
    "item_not_object": doc([5]),
    "payments_not_list": doc([item(1, 1)], payments={"a": 1}),
    "payment_not_object": doc([item(1, 1)], payments=[3]),
}

DIV_ROUND = [[n, d] for n, d in [(0, 3), (1, 2), (-1, 2), (3, 2), (-3, 2), (5, 10), (4, 10), (-5, 10), (-15, 10),
                                  (14, 10), (10**17 + 5, 10), (2, 3), (-2, 3), (1, 3), (-1, 3), (999, 1000), (500, 1000)]]

ALLOCATE = [[100, [1, 1, 1]], [2, [1, 1, 1]], [1, [3, 3]], [7, [0, 5, 5]], [0, [4, 5]], [10, [0, 0]],
            [1001, [333, 667]], [99999, [12345, 67890, 1, 0, 19999]]]

DUE = [
    ["2026-01-31", "net30"], ["2025-01-31", "net30"], ["2024-01-31", "net30"], ["2024-02-15", "net15"],
    ["2023-02-15", "net15"], ["2100-02-14", "net15"], ["2000-02-14", "net15"], ["2024-12-17", "net15"],
    ["2026-12-31", "net60"], ["2024-12-31", "net60"], ["2026-03-31", "receipt"], ["2024-02-29", "net30"],
    ["2026-10-21", "net30"], ["1900-02-28", "net15"], ["2999-12-20", "net15"],
]
DUE_ERRORS = [["2026-02-29", "net30"], ["2026-13-01", "net30"], ["2026-1-01", "net30"], ["26-01-01", "net30"],
              ["2026-01-01", "net45"], ["", "net30"], ["2026-04-31", "net15"], ["1899-12-31", "net15"],
              ["٢٠٢٦-01-01", "net30"]]
BETWEEN = [["2024-02-28", "2024-03-01"], ["2023-02-28", "2023-03-01"], ["2026-10-21", "2026-10-21"],
           ["2026-12-31", "2026-01-01"], ["1970-01-01", "2026-10-21"], ["2000-02-28", "2000-03-01"]]

SHIFTS = [["06:00", "17:30"], ["19:00", "03:15"], ["00:00", "00:00"], ["07:00", "07:00"], ["23:59", "00:00"],
          ["00:00", "24:00"], ["12:00", "12:01"], ["22:45", "06:10"], ["05:07", "16:53"]]
SHIFT_ERRORS = [["24:00", "06:00"], ["7:00", "15:00"], ["07:60", "15:00"], ["07:00", "25:00"], ["07:00", ""],
                ["07:00", "24:01"], ["07:00:00", "08:00"]]
TICKET_DAYS = [
    [],
    [{"start": "06:00", "end": "17:30"}, {"start": "19:00", "end": "03:15"}],
    [{"start": "06:00", "end": ""}, {"start": "", "end": ""}, {"start": "08:00", "end": "08:20"}],
]
HOURS_FMT = [0, 1, 20, 30, 45, 59, 61, 690, 495, 1185, 1440, 2879, 89999]

MONEY_FMT = [0, 1, 9, 10, 99, 100, 101, 123456, 100000000, 99999999999, -1, -123456, 1000000000]
DOCNUM = [["INV-", 1], ["FT-", 42], ["", 9999], ["EST", 10000], ["A/", 123456]]
PARSE_MONEY = ["", "0", "12", "12.5", "12.50", "$1,234.56", " 7 ", ".5", "5.", "0012.30", "10000000", "10000000.00"]
PARSE_MONEY_ERRORS = ["12.345", "-5", "abc", ".", "1e3", "10000000.01", "1.2.3", "$", "9999999999999", "١٢"]
PARSE_QTY = [["1.255", 3, 1000000000], ["2", 3, 1000000000], ["0.001", 3, 1000000000], ["8.25", 3, 100000],
             ["100", 2, 10000]]
PARSE_QTY_ERRORS = [["1.2555", 3, 1000000000], ["1000001", 3, 1000000000], ["101", 2, 10000]]
CSV_CELLS = ["plain", "=SUM(A1)", "+1", "-1", "@x", "a,b", 'say "hi"', "line\nbreak", "\ttab", "", "Ok=1"]


def sample_ticket(n, cust="Sample Operating LLC", **kw):
    d = copy.deepcopy(example_state(TODAY)["docs"][1])
    d.update({"id": f"t{n}", "number": f"FT-{n:04d}"})
    d["customer"]["name"] = cust
    d["oil"]["sig_company"] = "data:image/png;base64,AAAA"
    d.update(kw)
    return d


def sample_estimate():
    d = copy.deepcopy(example_state(TODAY)["docs"][0])
    d.update({"id": "e1", "type": "estimate", "number": "EST-0007", "status": "sent", "deposit_cents": 5000})
    return d


CONVERSIONS = {
    "estimate": {"kind": "estimate", "sources": [sample_estimate()]},
    "one_ticket": {"kind": "tickets", "sources": [sample_ticket(1)]},
    "two_tickets_same_pct": {"kind": "tickets", "sources": [
        sample_ticket(1, discount_value=5, shipping_cents=1000, notes="A"),
        sample_ticket(2, discount_value=5, shipping_cents=250, notes="B",
                      payments=[{"date": "", "amount_cents": 700, "note": "cash"}])]},
    "three_tickets_mixed_discounts": {"kind": "tickets", "sources": [
        sample_ticket(1, discount_value=5),
        sample_ticket(2, discount_kind="amt", discount_value=1234, notes=""),
        sample_ticket(3, discount_value=0)]},
    "case_insensitive_customer": {"kind": "tickets", "sources": [sample_ticket(1), sample_ticket(2, cust=" sample operating llc ")]},
}
CONVERSION_ERRORS = {
    "empty": {"kind": "tickets", "sources": []},
    "invoice_as_ticket": {"kind": "tickets", "sources": [dict(sample_ticket(1), type="invoice")]},
    "mixed_customers": {"kind": "tickets", "sources": [sample_ticket(1), sample_ticket(2, cust="Other LLC")]},
    "mixed_tax": {"kind": "tickets", "sources": [sample_ticket(1), sample_ticket(2, tax_rate_pct=6.25)]},
    "already_invoiced": {"kind": "tickets", "sources": [sample_ticket(1, converted_to="INV-0003")]},
    "ticket_as_estimate": {"kind": "estimate", "sources": [sample_ticket(1)]},
    "estimate_converted": {"kind": "estimate", "sources": [dict(sample_estimate(), converted_to="INV-0002")]},
    "too_many_items": {"kind": "tickets", "sources": [sample_ticket(1, items=[item(1, 1)] * 300),
                                                      sample_ticket(2, items=[item(1, 1)] * 201)]},
    # Review fixes: a bundle must never produce an invoice the backup schema rejects.
    "too_many_days": {"kind": "tickets", "sources": [
        sample_ticket(1, oil=dict(sample_ticket(1)["oil"], days=[{"date": "", "start": "06:00", "end": "18:00", "note": ""}] * 40)),
        sample_ticket(2, oil=dict(sample_ticket(2)["oil"], days=[{"date": "", "start": "06:00", "end": "18:00", "note": ""}] * 23))]},
    "too_many_payments": {"kind": "tickets", "sources": [
        sample_ticket(1, payments=[{"date": "", "amount_cents": 1, "note": ""}] * 60),
        sample_ticket(2, payments=[{"date": "", "amount_cents": 1, "note": ""}] * 41)]},
    "notes_too_long": {"kind": "tickets", "sources": [sample_ticket(1, notes="a" * 1500), sample_ticket(2, notes="b" * 1500)]},
    "shipping_over_cap": {"kind": "tickets", "sources": [sample_ticket(1, shipping_cents=600_000_000),
                                                         sample_ticket(2, shipping_cents=400_000_001)]},
    "deposit_over_cap": {"kind": "tickets", "sources": [sample_ticket(1, deposit_cents=1_000_000_000),
                                                        sample_ticket(2, deposit_cents=1)]},
}


def convert(case, number="INV-0009", date=TODAY):
    if case["kind"] == "estimate":
        return ft.estimate_to_invoice(case["sources"][0], "newid", number, date)
    return ft.tickets_to_invoice(case["sources"], "newid", number, date)


def status_docs():
    base = example_state(TODAY)["docs"][0]
    out = []
    for i, (st, issue, terms, pays) in enumerate([
        ("draft", "2026-01-01", "net30", 0), ("sent", "2026-10-01", "net30", 0), ("sent", "2026-09-21", "net30", 0),
        ("sent", "2026-09-20", "net30", 0), ("sent", "2026-10-21", "receipt", 0), ("sent", "2026-10-20", "receipt", 0),
        ("paid", "2026-01-01", "net15", 0), ("sent", "2026-01-01", "net15", 49140), ("sent", "2026-01-01", "net15", 100),
        ("draft", "2026-01-01", "net15", 99999),
    ]):
        d = copy.deepcopy(base)
        d.update({"id": f"s{i}", "number": f"INV-{i:04d}", "status": st, "issue_date": issue, "terms": terms,
                  "payments": [{"date": "", "amount_cents": pays, "note": ""}] if pays else []})
        out.append(d)
    est = sample_estimate()
    out.append(est)
    out.append(dict(est, id="s11", converted_to="INV-0002"))
    out.append(dict(sample_ticket(5), status="draft"))
    zero = copy.deepcopy(base)
    zero.update({"id": "s13", "items": [], "shipping_cents": 0, "deposit_cents": 0, "status": "sent", "issue_date": "2020-01-01"})
    out.append(zero)
    return out


def import_cases():
    good = example_state(TODAY)
    ok = {
        "example": good,
        "blank": blank_state(),
        "minimal": {"app": "field-ticket", "version": 1},
        "unknown_keys_dropped": dict(copy.deepcopy(good), extra={"x": 1}, business=dict(good["business"], hacker="<script>")),
        "control_chars_stripped": {"app": "field-ticket", "version": 1,
                                   "business": {"name": "A\u0000B\u0007C\tD\nE", "address": "L1\r\nL2\rL3"}},
        "html_text_kept_as_text": {"app": "field-ticket", "version": 1,
                                   "customers": [{"id": "c1", "name": "<img src=x onerror=alert(1)>"}]},
        "unicode_names": {"app": "field-ticket", "version": 1,
                          "customers": [{"id": "c1", "name": "Peña Servicios ✓ \U0001F69A"}]},
        "null_fields_default": {"app": "field-ticket", "version": 1, "business": {"name": None, "tax_rate_pct": None},
                                "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "items": None, "oil": None}]},
        "amt_discount": {"app": "field-ticket", "version": 1,
                         "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "discount_kind": "amt", "discount_value": 1500}]},
    }
    long_name = "x" * 121
    bad = {
        "not_object": [1, 2],
        "wrong_app": {"app": "other", "version": 1},
        "wrong_version": {"app": "field-ticket", "version": 2},
        "version_string": {"app": "field-ticket", "version": "1"},
        "version_bool": {"app": "field-ticket", "version": True},
        "business_not_object": {"app": "field-ticket", "version": 1, "business": "x"},
        "name_too_long": {"app": "field-ticket", "version": 1, "business": {"name": long_name}},
        "astral_counts_two": {"app": "field-ticket", "version": 1, "business": {"name": "\U0001F69A" * 61}},
        "name_number": {"app": "field-ticket", "version": 1, "business": {"name": 5}},
        "tax_rate_high": {"app": "field-ticket", "version": 1, "business": {"tax_rate_pct": 101}},
        "terms_bad": {"app": "field-ticket", "version": 1, "business": {"terms": "net45"}},
        "logo_svg": {"app": "field-ticket", "version": 1, "business": {"logo": "data:image/svg+xml;base64,PHN2Zz4="}},
        "logo_js_url": {"app": "field-ticket", "version": 1, "business": {"logo": "javascript:alert(1)"}},
        "logo_bad_chars": {"app": "field-ticket", "version": 1, "business": {"logo": "data:image/png;base64,AA\"><x"}},
        "customers_not_list": {"app": "field-ticket", "version": 1, "customers": {"a": 1}},
        "customer_bad_id": {"app": "field-ticket", "version": 1, "customers": [{"id": "a b"}]},
        "customer_dup_id": {"app": "field-ticket", "version": 1, "customers": [{"id": "a"}, {"id": "a"}]},
        "catalog_rate_float": {"app": "field-ticket", "version": 1, "catalog": [{"id": "a", "rate_cents": 1.5}]},
        "catalog_taxable_string": {"app": "field-ticket", "version": 1, "catalog": [{"id": "a", "taxable": "yes"}]},
        "doc_missing_type": {"app": "field-ticket", "version": 1, "docs": [{"id": "d1", "issue_date": "2026-01-01"}]},
        "doc_bad_type": {"app": "field-ticket", "version": 1, "docs": [{"id": "d1", "type": "quote", "issue_date": "2026-01-01"}]},
        "doc_missing_date": {"app": "field-ticket", "version": 1, "docs": [{"id": "d1", "type": "invoice"}]},
        "doc_bad_date": {"app": "field-ticket", "version": 1, "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-02-30"}]},
        "doc_status_overdue_stored": {"app": "field-ticket", "version": 1,
                                      "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "status": "overdue"}]},
        "item_qty_negative": {"app": "field-ticket", "version": 1,
                              "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "items": [{"qty": -1}]}]},
        "item_rate_huge": {"app": "field-ticket", "version": 1,
                           "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "items": [{"rate_cents": 1e20}]}]},
        "amt_discount_fraction": {"app": "field-ticket", "version": 1,
                                  "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "discount_kind": "amt", "discount_value": 1.5}]},
        "oil_day_bad_time": {"app": "field-ticket", "version": 1,
                             "docs": [{"id": "d1", "type": "ticket", "issue_date": "2026-01-01", "oil": {"days": [{"start": "25:00"}]}}]},
        "oil_sig_not_image": {"app": "field-ticket", "version": 1,
                              "docs": [{"id": "d1", "type": "ticket", "issue_date": "2026-01-01", "oil": {"sig_crew": "https://x.test/a.png"}}]},
        "settings_next_zero": {"app": "field-ticket", "version": 1, "settings": {"next": {"invoice": 0}}},
        "settings_next_float": {"app": "field-ticket", "version": 1, "settings": {"next": {"invoice": 2.5}}},
        "too_many_payments": {"app": "field-ticket", "version": 1,
                              "docs": [{"id": "d1", "type": "invoice", "issue_date": "2026-01-01", "payments": [{}] * 101}]},
    }
    return ok, bad


def err(fn, *a):
    try:
        fn(*a)
    except ft.FieldTicketError as e:
        return {"code": e.code, "message": e.message}
    raise SystemExit(f"expected an error from {fn.__name__}{a!r}")


def build() -> dict:
    v: dict = {"today": TODAY}
    v["totals"] = [{"name": k, "input": d, "output": ft.compute_totals(d)} for k, d in TOTALS.items()]
    v["totals_errors"] = [dict(name=k, input=d, **err(ft.compute_totals, d)) for k, d in TOTALS_ERRORS.items()]
    v["div_round"] = [{"n": str(n), "d": d, "q": str(ft.div_round(n, d))} for n, d in DIV_ROUND]
    v["allocate"] = [{"amount": a, "weights": w, "shares": ft.allocate(a, w)} for a, w in ALLOCATE]
    v["due"] = [{"issue": i, "terms": t, "due": ft.due_date(i, t)} for i, t in DUE]
    v["due_errors"] = [dict(issue=i, terms=t, **err(ft.due_date, i, t)) for i, t in DUE_ERRORS]
    v["between"] = [{"a": a, "b": b, "days": ft.days_between(a, b)} for a, b in BETWEEN]
    v["shifts"] = [{"start": s, "end": e, "minutes": ft.shift_minutes(s, e)} for s, e in SHIFTS]
    v["shift_errors"] = [dict(start=s, end=e, **err(ft.shift_minutes, s, e)) for s, e in SHIFT_ERRORS]
    v["ticket_days"] = [{"days": d, "out": ft.ticket_minutes(d)} for d in TICKET_DAYS]
    v["ticket_days_errors"] = [dict(days=d, **err(ft.ticket_minutes, d)) for d in [[{"start": "06:00", "end": "6:30"}]]]
    v["hours_fmt"] = [{"minutes": m, "text": ft.format_hours(m), "qty_milli": ft.hours_qty(m)} for m in HOURS_FMT]
    v["money_fmt"] = [{"cents": c, "text": ft.format_money(c)} for c in MONEY_FMT]
    v["docnum"] = [{"prefix": p, "n": n, "text": ft.format_doc_number(p, n)} for p, n in DOCNUM]
    v["parse_money"] = [{"text": s, "cents": ft.parse_money(s)} for s in PARSE_MONEY]
    v["parse_money_errors"] = [dict(text=s, **err(ft.parse_money, s)) for s in PARSE_MONEY_ERRORS]
    v["parse_decimal"] = [{"text": s, "places": p, "hi": h, "value": ft.parse_decimal(s, p, "qty", h)} for s, p, h in PARSE_QTY]
    v["parse_decimal_errors"] = [dict(text=s, places=p, hi=h, **err(ft.parse_decimal, s, p, "qty", h)) for s, p, h in PARSE_QTY_ERRORS]
    v["csv_cells"] = [{"text": s, "cell": ft.csv_cell(s)} for s in CSV_CELLS]
    sd = status_docs()
    v["status"] = {"docs": sd, "statuses": [ft.doc_status(d, TODAY) for d in sd], "summary": ft.summarize(sd, TODAY),
                   "csv": ft.docs_csv(sd, TODAY)}
    v["conversions"] = [{"name": k, "case": c, "output": convert(c)} for k, c in CONVERSIONS.items()]
    v["conversion_errors"] = [dict(name=k, case=c, **err(convert, c)) for k, c in CONVERSION_ERRORS.items()]
    ok, bad = import_cases()
    v["imports"] = [{"name": k, "input": d, "output": ft.sanitize_state(d)} for k, d in ok.items()]
    v["import_errors"] = [dict(name=k, input=d, **err(ft.sanitize_state, d)) for k, d in bad.items()]
    v["example_state"] = example_state(TODAY)
    v["blank_state"] = blank_state()
    mixed = example_state(TODAY)
    mixed["docs"].append(dict(copy.deepcopy(mixed["docs"][0]), id="mine", number="INV-0002", example=False))
    mixed["customers"].append({"id": "c-mine", "name": "Mine", "contact": "", "address": "", "phone": "", "email": ""})
    v["clear_examples"] = [{"input": s0, "output": clear_examples(s0)} for s0 in (example_state(TODAY), mixed)]
    return v


def main() -> None:
    out = ROOT / "tests" / "vectors.json"
    text = json.dumps(build(), indent=1, ensure_ascii=False, allow_nan=False)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(text) // 1024} KB)")


if __name__ == "__main__":
    main()
