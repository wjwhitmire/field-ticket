"""Command line interface.

Usage:
  field-ticket totals DOC.json            print the totals for one document
  field-ticket check BACKUP.json          validate a browser backup (Export all)
  field-ticket summary BACKUP.json [--today YYYY-MM-DD]
                                          status counts and money outstanding
  add --json to any command for raw JSON output.

DOC.json holds one document with the keys compute_totals reads (items,
discount_kind, discount_value, tax_rate_pct, tax_mode, shipping_cents,
deposit_cents, payments). Money is integer cents.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from .core import FieldTicketError, compute_totals, doc_status, format_money, parse_date, summarize
from .schema import sanitize_state

MAX_BYTES = 20 * 1024 * 1024   # backups carry logos and signatures


def _read_json(path: str):
    with open(path, "rb") as fh:
        data = fh.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise FieldTicketError("too_large", path + " is larger than 20 MB.")
    try:
        return json.loads(data.decode("utf-8-sig"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FieldTicketError("bad_json", f"{path} is not valid JSON ({exc}).") from None


def _reject_constant(name: str):
    raise FieldTicketError("bad_json", f"JSON value {name} is not allowed.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="field-ticket", description="Totals and checks for Field Ticket documents.")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("totals", help="totals for one document JSON")
    t.add_argument("path")
    c = sub.add_parser("check", help="validate a backup JSON from the browser tool")
    c.add_argument("path")
    s = sub.add_parser("summary", help="status counts and outstanding balance for a backup")
    s.add_argument("path")
    s.add_argument("--today", help="date for overdue checks, YYYY-MM-DD (default: today)")
    for sp in (t, c, s):
        sp.add_argument("--json", action="store_true", help="print raw JSON")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = _read_json(args.path)
    if args.cmd == "totals":
        if not isinstance(raw, dict):
            raise FieldTicketError("bad_input", "Document JSON must be an object.")
        t = compute_totals(raw)
        if args.json:
            print(json.dumps(t, indent=2))
        else:
            for k in ("subtotal", "discount", "tax", "shipping", "total", "paid", "balance"):
                print(f"{k:<10}{format_money(t[k]):>18}")
        return 0
    state = sanitize_state(raw)
    if args.cmd == "check":
        msg = {"docs": len(state["docs"]), "customers": len(state["customers"]), "catalog": len(state["catalog"])}
        print(json.dumps(msg) if args.json else f"ok: {msg['docs']} documents, {msg['customers']} customers, {msg['catalog']} catalog items")
        return 0
    today = args.today or datetime.date.today().isoformat()
    parse_date(today, "--today")
    s = summarize(state["docs"], today)
    if args.json:
        s["docs"] = [{"number": d["number"], "type": d["type"], "status": doc_status(d, today),
                      "balance": compute_totals(d)["balance"]} for d in state["docs"]]
        print(json.dumps(s, indent=2))
    else:
        print("  ".join(f"{k} {v}" for k, v in s["counts"].items()))
        print(f"outstanding {format_money(s['outstanding'])}  overdue {format_money(s['overdue'])}")
    return 0


def main(argv: list[str] | None = None) -> None:
    try:
        sys.exit(run(argv))
    except FieldTicketError as exc:
        print("error: " + exc.message, file=sys.stderr)
        sys.exit(2)
    except OSError as exc:
        print(f"error: cannot read file ({exc.strerror}).", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
