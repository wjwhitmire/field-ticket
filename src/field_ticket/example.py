"""The labeled example state the browser tool opens with.

Everything here is invented: Example Co., its customers, the lease, and the
well. Dates are set relative to `today` so the sample invoice reads as sent
and not yet due, and the sample field ticket covers the two days before.
"""

from __future__ import annotations

import copy

from .core import add_days

EX_BUSINESS = {
    "name": "Example Co.",
    "address": "100 Sample Road\nMidland, TX 79701",
    "phone": "(555) 010-0100",
    "email": "office@example.com",
    "tax_id": "TX Lic. 000000",
    "logo": "",
    "tax_rate_pct": 8.25,
    "tax_mode": "document",
    "terms": "net30",
    "payment_instructions": "Pay by check to Example Co. or by ACH. Reference the invoice number.",
}

EX_CATALOG = [
    {"id": "excat1", "name": "Vacuum truck, 130 bbl", "unit": "hr", "rate_cents": 12500, "taxable": False},
    {"id": "excat2", "name": "Roustabout crew, 3 hands", "unit": "hr", "rate_cents": 19500, "taxable": False},
    {"id": "excat3", "name": "Pickup mileage", "unit": "mi", "rate_cents": 85, "taxable": False},
    {"id": "excat4", "name": "Fittings and valves", "unit": "ea", "rate_cents": 4275, "taxable": True},
    {"id": "excat5", "name": "Service call", "unit": "ea", "rate_cents": 9500, "taxable": False},
]

EX_CUSTOMERS = [
    {"id": "excus1", "name": "Sample Operating LLC", "contact": "Field office", "address": "200 Example Ave\nOdessa, TX 79761",
     "phone": "(555) 010-0200", "email": "ap@example.com"},
    {"id": "excus2", "name": "Sample Storage Yard", "contact": "Yard manager", "address": "300 Demo Lane\nMidland, TX 79703",
     "phone": "(555) 010-0300", "email": "yard@example.com"},
]


def _party(c: dict) -> dict:
    return {k: c[k] for k in ("name", "contact", "address", "phone", "email")}


def _oil_blank() -> dict:
    return {"enabled": False, "operator": "", "afe": "", "lease": "", "well": "", "rig": "", "county": "",
            "state": "", "po": "", "crew": "", "days": [], "sig_company": "", "sig_company_name": "",
            "sig_crew": "", "sig_crew_name": ""}


def example_state(today: str) -> dict:
    inv_date = add_days(today, -6)
    t1 = add_days(today, -2)
    t2 = add_days(today, -1)
    invoice = {
        "id": "exdoc1", "type": "invoice", "number": "INV-0001", "status": "sent",
        "issue_date": inv_date, "terms": "net30", "customer": _party(EX_CUSTOMERS[1]),
        "items": [
            {"name": "Service call", "unit": "ea", "qty": 1, "rate_cents": 9500, "taxable": False, "discount_pct": 0},
            {"name": "Replace yard gate latch and hinge", "unit": "hr", "qty": 2.5, "rate_cents": 8500, "taxable": False, "discount_pct": 0},
            {"name": "Fittings and valves", "unit": "ea", "qty": 6, "rate_cents": 4275, "taxable": True, "discount_pct": 10},
        ],
        "discount_kind": "pct", "discount_value": 0, "tax_rate_pct": 8.25, "tax_mode": "document",
        "shipping_label": "Shipping / mileage", "shipping_cents": 3400, "deposit_cents": 10000,
        "payments": [], "notes": "Example data. Sample invoice for a yard repair.", "sources": [],
        "converted_to": "", "example": True, "oil": _oil_blank(),
    }
    oil = _oil_blank()
    oil.update({
        "enabled": True, "operator": "Sample Operating LLC", "afe": "AFE 00-000", "lease": "Example Ranch",
        "well": "Example Ranch 1H", "rig": "Workover rig 0", "county": "Sample County", "state": "TX",
        "po": "PO 000000", "crew": "Crew lead A. Sample, hands B. Sample and C. Sample",
        "days": [
            {"date": t1, "start": "06:00", "end": "17:30", "note": "Haul fluid, flowback tank"},
            {"date": t2, "start": "19:00", "end": "03:15", "note": "Night run, across midnight"},
        ],
        "sig_company_name": "", "sig_crew_name": "",
    })
    ticket = {
        "id": "exdoc2", "type": "ticket", "number": "FT-0001", "status": "draft",
        "issue_date": t2, "terms": "net30", "customer": _party(EX_CUSTOMERS[0]),
        "items": [
            {"name": "Vacuum truck, 130 bbl", "unit": "hr", "qty": 19.75, "rate_cents": 12500, "taxable": False, "discount_pct": 0},
            {"name": "Roustabout crew, 3 hands", "unit": "hr", "qty": 11.5, "rate_cents": 19500, "taxable": False, "discount_pct": 0},
            {"name": "Pickup mileage", "unit": "mi", "qty": 142, "rate_cents": 85, "taxable": False, "discount_pct": 0},
            {"name": "Fittings and valves", "unit": "ea", "qty": 3, "rate_cents": 4275, "taxable": True, "discount_pct": 0},
        ],
        "discount_kind": "pct", "discount_value": 0, "tax_rate_pct": 8.25, "tax_mode": "line",
        "shipping_label": "Shipping / mileage", "shipping_cents": 0, "deposit_cents": 0,
        "payments": [], "notes": "Example data. Sample oilfield field ticket with two days of work.", "sources": [],
        "converted_to": "", "example": True, "oil": oil,
    }
    return {
        "app": "field-ticket",
        "version": 1,
        "business": dict(EX_BUSINESS),
        "settings": {"prefix": {"estimate": "EST-", "ticket": "FT-", "invoice": "INV-"},
                     "next": {"estimate": 1, "ticket": 2, "invoice": 2}, "oil_default": True},
        "customers": [dict(c) for c in EX_CUSTOMERS],
        "catalog": [dict(c) for c in EX_CATALOG],
        "docs": [invoice, ticket],
    }


def blank_state() -> dict:
    """What "Start fresh" leaves: no business details, no documents, counters at 1."""
    st = example_state("2000-01-01")
    st["business"] = {k: ("" if isinstance(v, str) else v) for k, v in EX_BUSINESS.items()}
    st["business"].update({"tax_rate_pct": 0, "tax_mode": "document", "terms": "net30"})
    st["settings"]["next"] = {"estimate": 1, "ticket": 1, "invoice": 1}
    st["customers"], st["catalog"], st["docs"] = [], [], []
    return st


def clear_examples(state: dict) -> dict:
    """What "Start fresh" does: drop the example documents, customers, and
    catalog items, and blank the business profile if it is still Example Co.
    Anything the user added stays. Counters restart at 1 when no documents remain.
    """
    st = copy.deepcopy(state)
    st["docs"] = [d for d in st["docs"] if not d.get("example")]
    st["customers"] = [c for c in st["customers"] if not c["id"].startswith("excus")]
    st["catalog"] = [c for c in st["catalog"] if not c["id"].startswith("excat")]
    if st["business"].get("name") == EX_BUSINESS["name"]:
        st["business"] = blank_state()["business"]
    if not st["docs"]:
        st["settings"]["next"] = {"estimate": 1, "ticket": 1, "invoice": 1}
    return st
