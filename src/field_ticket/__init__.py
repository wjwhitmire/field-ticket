"""Field Ticket: estimates, field tickets, and invoices with integer-cent math.

The browser tool (web/app.html) mirrors this package; the parity test keeps
them equal.
"""

from .core import (
    DOC_TYPES,
    MAX_CENTS,
    TERMS,
    FieldTicketError,
    add_days,
    allocate,
    compute_totals,
    days_between,
    div_round,
    doc_status,
    due_date,
    estimate_to_invoice,
    format_doc_number,
    format_hours,
    hours_qty,
    format_money,
    line_totals,
    shift_minutes,
    summarize,
    ticket_minutes,
    tickets_to_invoice,
    parse_money,
    parse_decimal,
    csv_cell,
    docs_csv,
)
from .schema import SCHEMA_VERSION, sanitize_state

__version__ = "1.0.0"

__all__ = [
    "DOC_TYPES", "MAX_CENTS", "TERMS", "SCHEMA_VERSION", "FieldTicketError",
    "add_days", "allocate", "compute_totals", "days_between", "div_round", "doc_status",
    "due_date", "estimate_to_invoice", "format_doc_number", "format_hours", "hours_qty", "format_money",
    "line_totals", "sanitize_state", "shift_minutes", "summarize", "ticket_minutes",
    "tickets_to_invoice", "parse_money", "parse_decimal", "csv_cell", "docs_csv",
]
