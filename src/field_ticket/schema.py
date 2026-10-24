"""Schema check for Field Ticket backups (Export all / Import).

sanitize_state() takes parsed JSON and returns a clean copy that holds only
known keys with checked types and sizes, or raises FieldTicketError naming the
first bad path. Missing keys take their defaults, so older or partial backups
still load. Unknown keys are dropped. The browser tool runs the same checks
(web/app.html, FT.sanitizeState) and the parity test holds them equal.
"""

from __future__ import annotations

import re

from .core import (
    MAX_ITEMS,
    MAX_QTY,
    FieldTicketError,
    cents,
    is_number,
    parse_date,
    parse_time,
    scaled,
)

SCHEMA_VERSION = 1
MAX_DOCS = 5000
MAX_CUSTOMERS = 2000
MAX_CATALOG = 2000
MAX_PAYMENTS = 100
MAX_DAYS = 62
MAX_SOURCES = 100
LOGO_MAX_CHARS = 1_000_000   # stored logo after downscaling (the source file cap is 2 MB)
SIG_MAX_CHARS = 300_000

ID_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
DATAURL_RE = re.compile(r"data:image/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _err(path: str, what: str):
    raise FieldTicketError("bad_import", f"{path}: {what}")


def s_str(v, path, maxlen, multiline=False, default=""):
    if v is None:
        return default
    if not isinstance(v, str):
        _err(path, "must be text.")
    v = CTRL_RE.sub("", v.replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline:
        v = v.replace("\n", " ").replace("\t", " ")
    if ulen(v) > maxlen:
        _err(path, f"is longer than {maxlen} characters.")
    return v


def ulen(v: str) -> int:
    """Length in UTF-16 code units, the same count JavaScript's String length gives."""
    return len(v.encode("utf-16-le", "surrogatepass")) // 2


def s_bool(v, path, default=False):
    if v is None:
        return default
    if not isinstance(v, bool):
        _err(path, "must be true or false.")
    return v


def s_enum(v, path, values, default):
    if v is None:
        return default
    if not isinstance(v, str) or v not in values:
        _err(path, "must be one of " + ", ".join(values) + ".")
    return v


def s_num(v, path, places, lo, hi, default=0):
    if v is None:
        return default
    scaled(v, places, lo, hi, path)
    return v


def s_cents(v, path, default=0):
    if v is None:
        return default
    return cents(v, path)


def s_int(v, path, lo, hi, default):
    if v is None:
        return default
    if not is_number(v) or v != int(v) or v < lo or v > hi:
        _err(path, f"must be a whole number from {lo} to {hi}.")
    return int(v)


def s_date(v, path, optional=False):
    if (v is None or v == "") and optional:
        return ""
    if v is None:
        _err(path, "is missing.")
    parse_date(v, path)
    return v


def s_time(v, path, allow_24):
    if v is None or v == "":
        return ""
    parse_time(v, path, allow_24)
    return v


def s_dataurl(v, path, maxlen):
    if v is None or v == "":
        return ""
    if not isinstance(v, str) or not DATAURL_RE.fullmatch(v):
        _err(path, "must be a PNG or JPEG image data URL.")
    if len(v) > maxlen:
        _err(path, "image is too large.")
    return v


def s_id(v, path):
    if not isinstance(v, str) or not ID_RE.fullmatch(v):
        _err(path, "must be an id of 1 to 40 letters, digits, dash, or underscore.")
    return v


def s_list(v, path, maxn):
    if v is None:
        return []
    if not isinstance(v, list):
        _err(path, "must be a list.")
    if len(v) > maxn:
        _err(path, f"has more than {maxn} entries.")
    return v


def s_obj(v, path):
    if v is None:
        return {}
    if not isinstance(v, dict):
        _err(path, "must be an object.")
    return v


def s_business(b, p):
    b = s_obj(b, p)
    return {
        "name": s_str(b.get("name"), p + ".name", 120),
        "address": s_str(b.get("address"), p + ".address", 400, True),
        "phone": s_str(b.get("phone"), p + ".phone", 60),
        "email": s_str(b.get("email"), p + ".email", 120),
        "tax_id": s_str(b.get("tax_id"), p + ".tax_id", 80),
        "logo": s_dataurl(b.get("logo"), p + ".logo", LOGO_MAX_CHARS),
        "tax_rate_pct": s_num(b.get("tax_rate_pct"), p + ".tax_rate_pct", 3, 0, 100),
        "tax_mode": s_enum(b.get("tax_mode"), p + ".tax_mode", ["document", "line"], "document"),
        "terms": s_enum(b.get("terms"), p + ".terms", ["receipt", "net15", "net30", "net60"], "net30"),
        "payment_instructions": s_str(b.get("payment_instructions"), p + ".payment_instructions", 1000, True),
    }


def s_party(c, p):
    c = s_obj(c, p)
    return {
        "name": s_str(c.get("name"), p + ".name", 120),
        "contact": s_str(c.get("contact"), p + ".contact", 120),
        "address": s_str(c.get("address"), p + ".address", 400, True),
        "phone": s_str(c.get("phone"), p + ".phone", 60),
        "email": s_str(c.get("email"), p + ".email", 120),
    }


def s_customer(c, p):
    out = {"id": s_id(s_obj(c, p).get("id"), p + ".id")}
    out.update(s_party(c, p))
    return out


def s_catalog(c, p):
    c = s_obj(c, p)
    return {
        "id": s_id(c.get("id"), p + ".id"),
        "name": s_str(c.get("name"), p + ".name", 200),
        "unit": s_str(c.get("unit"), p + ".unit", 20),
        "rate_cents": s_cents(c.get("rate_cents"), p + ".rate_cents"),
        "taxable": s_bool(c.get("taxable"), p + ".taxable"),
    }


def s_item(it, p):
    it = s_obj(it, p)
    return {
        "name": s_str(it.get("name"), p + ".name", 200),
        "unit": s_str(it.get("unit"), p + ".unit", 20),
        "qty": s_num(it.get("qty"), p + ".qty", 3, 0, MAX_QTY),
        "rate_cents": s_cents(it.get("rate_cents"), p + ".rate_cents"),
        "taxable": s_bool(it.get("taxable"), p + ".taxable"),
        "discount_pct": s_num(it.get("discount_pct"), p + ".discount_pct", 2, 0, 100),
    }


def s_payment(x, p):
    x = s_obj(x, p)
    return {
        "date": s_date(x.get("date"), p + ".date", optional=True),
        "amount_cents": s_cents(x.get("amount_cents"), p + ".amount_cents"),
        "note": s_str(x.get("note"), p + ".note", 120),
    }


def s_day(x, p):
    x = s_obj(x, p)
    return {
        "date": s_date(x.get("date"), p + ".date", optional=True),
        "start": s_time(x.get("start"), p + ".start", False),
        "end": s_time(x.get("end"), p + ".end", True),
        "note": s_str(x.get("note"), p + ".note", 200),
    }


OIL_TEXT = (("operator", 120), ("afe", 60), ("lease", 120), ("well", 120), ("rig", 60),
            ("county", 60), ("state", 40), ("po", 60), ("crew", 300))


def s_oil(o, p):
    o = s_obj(o, p)
    out = {"enabled": s_bool(o.get("enabled"), p + ".enabled")}
    for k, n in OIL_TEXT:
        out[k] = s_str(o.get(k), p + "." + k, n)
    out["days"] = [s_day(d, f"{p}.days[{i}]") for i, d in enumerate(s_list(o.get("days"), p + ".days", MAX_DAYS))]
    out["sig_company"] = s_dataurl(o.get("sig_company"), p + ".sig_company", SIG_MAX_CHARS)
    out["sig_company_name"] = s_str(o.get("sig_company_name"), p + ".sig_company_name", 120)
    out["sig_crew"] = s_dataurl(o.get("sig_crew"), p + ".sig_crew", SIG_MAX_CHARS)
    out["sig_crew_name"] = s_str(o.get("sig_crew_name"), p + ".sig_crew_name", 120)
    return out


def s_doc(d, p):
    d = s_obj(d, p)
    kind = s_enum(d.get("discount_kind"), p + ".discount_kind", ["pct", "amt"], "pct")
    if kind == "pct":
        dval = s_num(d.get("discount_value"), p + ".discount_value", 2, 0, 100)
    else:
        dval = s_cents(d.get("discount_value"), p + ".discount_value")
    return {
        "id": s_id(d.get("id"), p + ".id"),
        "type": s_enum(d.get("type"), p + ".type", ["estimate", "ticket", "invoice"], None) or _err(p + ".type", "is missing."),
        "number": s_str(d.get("number"), p + ".number", 40),
        "status": s_enum(d.get("status"), p + ".status", ["draft", "sent", "paid"], "draft"),
        "issue_date": s_date(d.get("issue_date"), p + ".issue_date"),
        "terms": s_enum(d.get("terms"), p + ".terms", ["receipt", "net15", "net30", "net60"], "net30"),
        "customer": s_party(d.get("customer"), p + ".customer"),
        "items": [s_item(x, f"{p}.items[{i}]") for i, x in enumerate(s_list(d.get("items"), p + ".items", MAX_ITEMS))],
        "discount_kind": kind,
        "discount_value": dval,
        "tax_rate_pct": s_num(d.get("tax_rate_pct"), p + ".tax_rate_pct", 3, 0, 100),
        "tax_mode": s_enum(d.get("tax_mode"), p + ".tax_mode", ["document", "line"], "document"),
        "shipping_label": s_str(d.get("shipping_label"), p + ".shipping_label", 60, default="Shipping / mileage"),
        "shipping_cents": s_cents(d.get("shipping_cents"), p + ".shipping_cents"),
        "deposit_cents": s_cents(d.get("deposit_cents"), p + ".deposit_cents"),
        "payments": [s_payment(x, f"{p}.payments[{i}]") for i, x in enumerate(s_list(d.get("payments"), p + ".payments", MAX_PAYMENTS))],
        "notes": s_str(d.get("notes"), p + ".notes", 2000, True),
        "sources": [s_str(x, f"{p}.sources[{i}]", 40) for i, x in enumerate(s_list(d.get("sources"), p + ".sources", MAX_SOURCES))],
        "converted_to": s_str(d.get("converted_to"), p + ".converted_to", 40),
        "example": s_bool(d.get("example"), p + ".example"),
        "oil": s_oil(d.get("oil"), p + ".oil"),
    }


def s_settings(s, p):
    s = s_obj(s, p)
    pre = s_obj(s.get("prefix"), p + ".prefix")
    nxt = s_obj(s.get("next"), p + ".next")
    defaults = {"estimate": "EST-", "ticket": "FT-", "invoice": "INV-"}
    return {
        "prefix": {k: s_str(pre.get(k), f"{p}.prefix.{k}", 12, default=v) for k, v in defaults.items()},
        "next": {k: s_int(nxt.get(k), f"{p}.next.{k}", 1, 999999, 1) for k in defaults},
        "oil_default": s_bool(s.get("oil_default"), p + ".oil_default"),
    }


def sanitize_state(raw) -> dict:
    """Validate and clean a parsed backup. Raises FieldTicketError (code bad_import) on the first problem."""
    try:
        return _sanitize(raw)
    except FieldTicketError as exc:
        raise FieldTicketError("bad_import", exc.message) from None


def _sanitize(raw) -> dict:
    if not isinstance(raw, dict):
        raise FieldTicketError("bad_import", "The backup must be a JSON object.")
    if raw.get("app") != "field-ticket":
        raise FieldTicketError("bad_import", 'This is not a Field Ticket backup (missing "app": "field-ticket").')
    ver = raw.get("version")
    if not is_number(ver) or ver != SCHEMA_VERSION:
        raise FieldTicketError("bad_import", f"This backup's version is not supported; this tool reads version {SCHEMA_VERSION}.")
    out = {
        "app": "field-ticket",
        "version": SCHEMA_VERSION,
        "business": s_business(raw.get("business"), "business"),
        "settings": s_settings(raw.get("settings"), "settings"),
        "customers": [s_customer(c, f"customers[{i}]") for i, c in enumerate(s_list(raw.get("customers"), "customers", MAX_CUSTOMERS))],
        "catalog": [s_catalog(c, f"catalog[{i}]") for i, c in enumerate(s_list(raw.get("catalog"), "catalog", MAX_CATALOG))],
        "docs": [s_doc(d, f"docs[{i}]") for i, d in enumerate(s_list(raw.get("docs"), "docs", MAX_DOCS))],
    }
    for key in ("customers", "catalog", "docs"):
        seen = set()
        for i, x in enumerate(out[key]):
            if x["id"] in seen:
                _err(f"{key}[{i}].id", "repeats an earlier id.")
            seen.add(x["id"])
    return out
