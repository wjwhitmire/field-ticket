"""Import validation (sanitize_state), CLI, and vectors.json freshness."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

import field_ticket as ft
from field_ticket import cli
from field_ticket.example import example_state

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = "2026-10-21"


def base(**kw):
    d = {"app": "field-ticket", "version": 1}
    d.update(kw)
    return d


def doc(**kw):
    d = {"id": "d1", "type": "invoice", "issue_date": "2026-01-01"}
    d.update(kw)
    return d


def test_minimal_backup_fills_defaults():
    st = ft.sanitize_state(base())
    assert st["docs"] == [] and st["settings"]["prefix"]["invoice"] == "INV-"
    assert st["business"]["terms"] == "net30"


def test_unknown_keys_dropped():
    st = ft.sanitize_state(base(extra=1, business={"name": "A", "evil": "<script>"}))
    assert "extra" not in st and "evil" not in st["business"]


def test_html_kept_as_plain_text():
    st = ft.sanitize_state(base(customers=[{"id": "c1", "name": "<img src=x onerror=alert(1)>"}]))
    assert st["customers"][0]["name"] == "<img src=x onerror=alert(1)>"


def test_control_characters_stripped_and_newlines_handled():
    st = ft.sanitize_state(base(business={"name": "A\u0000B\tC\nD", "address": "L1\r\nL2\rL3"}))
    assert st["business"]["name"] == "AB C D"
    assert st["business"]["address"] == "L1\nL2\nL3"


@pytest.mark.parametrize("raw,where", [
    ([1], "object"),
    (base(app="x"), "Field Ticket backup"),
    (base(version=2), "version"),
    (base(version=True), "version"),
    (base(business={"name": "x" * 121}), "business.name"),
    (base(business={"name": "\U0001F69A" * 61}), "business.name"),
    (base(business={"logo": "data:image/svg+xml;base64,PHN2Zz4="}), "business.logo"),
    (base(business={"logo": "javascript:alert(1)"}), "business.logo"),
    (base(business={"logo": "data:image/png;base64," + "A" * 1_000_004}), "business.logo"),
    (base(business={"tax_rate_pct": float("nan")}), "tax_rate_pct"),
    (base(customers=[{"id": "a"}, {"id": "a"}]), "customers[1].id"),
    (base(catalog=[{"id": "a", "rate_cents": 1.5}]), "catalog[0].rate_cents"),
    (base(docs=[doc(type="quote")]), "docs[0].type"),
    (base(docs=[doc(issue_date="2026-02-30")]), "docs[0].issue_date"),
    (base(docs=[doc(status="overdue")]), "docs[0].status"),
    (base(docs=[doc(items=[{"qty": -1}])]), "docs[0].items[0].qty"),
    (base(docs=[doc(oil={"days": [{"start": "25:00"}]})]), "docs[0].oil.days[0].start"),
    (base(docs=[doc(oil={"sig_crew": "https://x.test/a.png"})]), "sig_crew"),
    (base(settings={"next": {"invoice": 0}}), "settings.next.invoice"),
    (base(docs=[doc(payments=[{}] * 101)]), "payments"),
])
def test_import_rejects(raw, where):
    with pytest.raises(ft.FieldTicketError) as ei:
        ft.sanitize_state(raw)
    assert ei.value.code == "bad_import" and where in ei.value.message


def test_roundtrip_example():
    st = example_state(TODAY)
    again = ft.sanitize_state(json.loads(json.dumps(st)))
    assert again == st


# ------------------------------------------------------------ CLI

def run_cli(capsys, *args):
    with pytest.raises(SystemExit) as ei:
        cli.main(list(args))
    out = capsys.readouterr()
    return ei.value.code, out.out, out.err


def test_cli_totals(tmp_path, capsys):
    p = tmp_path / "doc.json"
    p.write_text(json.dumps(example_state(TODAY)["docs"][0]))
    code, out, _ = run_cli(capsys, "totals", str(p))
    assert code == 0 and "$591.40" in out and "$491.40" in out
    code, out, _ = run_cli(capsys, "totals", str(p), "--json")
    assert json.loads(out)["balance"] == 49140


def test_cli_check_and_summary(tmp_path, capsys):
    p = tmp_path / "backup.json"
    p.write_text(json.dumps(example_state(TODAY)))
    code, out, _ = run_cli(capsys, "check", str(p))
    assert code == 0 and "2 documents" in out
    code, out, _ = run_cli(capsys, "summary", str(p), "--today", TODAY, "--json")
    s = json.loads(out)
    assert s["counts"]["sent"] == 1 and s["outstanding"] == 49140


def test_cli_bad_inputs(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    code, _, err = run_cli(capsys, "check", str(p))
    assert code == 2 and "not valid JSON" in err
    p.write_text('{"app": "field-ticket", "version": NaN}')
    code, _, err = run_cli(capsys, "check", str(p))
    assert code == 2 and "NaN" in err
    code, _, err = run_cli(capsys, "check", str(tmp_path / "missing.json"))
    assert code == 2 and "cannot read" in err


def test_cli_size_cap(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cli, "MAX_BYTES", 10)
    p = tmp_path / "big.json"
    p.write_text(json.dumps({"x": "y" * 50}))
    code, _, err = run_cli(capsys, "check", str(p))
    assert code == 2 and "larger than" in err


# ------------------------------------------------------------ vectors

def test_vectors_file_is_current():
    sys.path.insert(0, str(ROOT / "tests"))
    import make_vectors  # noqa: PLC0415

    want = json.loads(json.dumps(make_vectors.build()))
    have = json.loads((ROOT / "tests" / "vectors.json").read_text(encoding="utf-8"))
    assert have == want, "run python tests/make_vectors.py"


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-02-30", "tomorrow", "26-10-23"])
def test_cli_summary_rejects_bad_today(tmp_path, capsys, bad):
    # A bad --today used to be compared as text and gave wrong overdue counts.
    p = tmp_path / "backup.json"
    p.write_text(json.dumps(example_state(TODAY)))
    code, _, err = run_cli(capsys, "summary", str(p), "--today", bad)
    assert code == 2 and "--today" in err
