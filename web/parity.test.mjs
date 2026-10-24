// Parity check: run the JS core from web/app.html against tests/vectors.json.
// Usage: node web/parity.test.mjs   (after: python tests/make_vectors.py)
// Money and dates are integers, so every comparison is exact (no tolerance).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "app.html"), "utf8");
const m = html.match(/<script id="core">([\s\S]*?)<\/script>/);
if (!m) {
  console.error('FAIL: no <script id="core"> block in app.html');
  process.exit(1);
}
const ctx = vm.createContext({});
vm.runInContext(m[1] + "\n;globalThis.FT = FT;", ctx, { filename: "app.html#core" });
const FT = ctx.FT;
const V = JSON.parse(readFileSync(join(here, "..", "tests", "vectors.json"), "utf8"));

let checks = 0;
const failures = [];

function deepCompare(got, want, path) {
  checks++;
  if (want === null || typeof want !== "object") {
    if (got !== want) failures.push(`${path}: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
    return;
  }
  if (Array.isArray(want)) {
    if (!Array.isArray(got) || got.length !== want.length) {
      failures.push(`${path}: array length got ${got && got.length}, want ${want.length}`);
      return;
    }
    want.forEach((w, i) => deepCompare(got[i], w, `${path}[${i}]`));
    return;
  }
  if (got === null || typeof got !== "object") {
    failures.push(`${path}: got ${JSON.stringify(got)}, want object`);
    return;
  }
  const gk = Object.keys(got).sort().join(",");
  const wk = Object.keys(want).sort().join(",");
  if (gk !== wk) failures.push(`${path}: keys differ\n  got  ${gk}\n  want ${wk}`);
  for (const k of Object.keys(want)) deepCompare(got[k], want[k], `${path}.${k}`);
}

// Copy into the vm realm so Array.isArray and object checks behave as in a page.
const inRealm = (x) => vm.runInContext("(" + JSON.stringify(x) + ")", ctx);
const plain = (x) => JSON.parse(JSON.stringify(x));
const call = (fn, ...args) => plain(fn(...args.map(inRealm)));

function expectError(label, fn, code, message) {
  checks++;
  try {
    fn();
    failures.push(`${label}: did not throw`);
  } catch (e) {
    if (e.code !== code || e.message !== message) {
      failures.push(`${label}: got ${e.code} "${e.message}", want ${code} "${message}"`);
    }
  }
}

for (const v of V.totals) deepCompare(call(FT.computeTotals, v.input), v.output, `totals[${v.name}]`);
for (const v of V.totals_errors) expectError(`totals_errors[${v.name}]`, () => FT.computeTotals(inRealm(v.input)), v.code, v.message);

for (const v of V.div_round) {
  checks++;
  const q = FT.divRoundBig(BigInt(v.n), BigInt(v.d)).toString();
  if (q !== v.q) failures.push(`div_round(${v.n}, ${v.d}): got ${q}, want ${v.q}`);
}
for (const v of V.allocate) deepCompare(call(FT.allocate, v.amount, v.weights), v.shares, `allocate(${v.amount})`);

for (const v of V.due) deepCompare(FT.dueDate(v.issue, v.terms), v.due, `due(${v.issue}, ${v.terms})`);
for (const v of V.due_errors) expectError(`due_errors(${v.issue}, ${v.terms})`, () => FT.dueDate(v.issue, v.terms), v.code, v.message);
for (const v of V.between) deepCompare(FT.daysBetween(v.a, v.b), v.days, `between(${v.a}, ${v.b})`);

for (const v of V.shifts) deepCompare(FT.shiftMinutes(v.start, v.end), v.minutes, `shift(${v.start}, ${v.end})`);
for (const v of V.shift_errors) expectError(`shift_errors(${v.start}, ${v.end})`, () => FT.shiftMinutes(v.start, v.end), v.code, v.message);
for (const v of V.ticket_days) deepCompare(call(FT.ticketMinutes, v.days), v.out, `ticket_days`);
for (const v of V.ticket_days_errors) expectError("ticket_days_errors", () => FT.ticketMinutes(inRealm(v.days)), v.code, v.message);
for (const v of V.hours_fmt) {
  deepCompare(FT.formatHours(v.minutes), v.text, `format_hours(${v.minutes})`);
  deepCompare(FT.hoursQty(v.minutes), v.qty_milli, `hours_qty(${v.minutes})`);
}

for (const v of V.money_fmt) deepCompare(FT.formatMoney(v.cents), v.text, `format_money(${v.cents})`);
for (const v of V.docnum) deepCompare(FT.formatDocNumber(v.prefix, v.n), v.text, `docnum(${v.prefix}, ${v.n})`);
for (const v of V.parse_money) deepCompare(FT.parseMoney(v.text), v.cents, `parse_money(${JSON.stringify(v.text)})`);
for (const v of V.parse_money_errors) expectError(`parse_money_errors(${JSON.stringify(v.text)})`, () => FT.parseMoney(v.text), v.code, v.message);
for (const v of V.parse_decimal) deepCompare(FT.parseDecimal(v.text, v.places, "qty", v.hi), v.value, `parse_decimal(${v.text})`);
for (const v of V.parse_decimal_errors) expectError(`parse_decimal_errors(${v.text})`, () => FT.parseDecimal(v.text, v.places, "qty", v.hi), v.code, v.message);
for (const v of V.csv_cells) deepCompare(FT.csvCell(v.text), v.cell, `csv_cell(${JSON.stringify(v.text)})`);

const docs = inRealm(V.status.docs);
deepCompare(plain(docs.map((d) => FT.docStatus(d, V.today))), V.status.statuses, "status");
deepCompare(plain(FT.summarize(docs, V.today)), V.status.summary, "summary");
deepCompare(FT.docsCsv(docs, V.today), V.status.csv, "docs_csv");

function convert(c) {
  const src = inRealm(c.sources);
  if (c.kind === "estimate") return FT.estimateToInvoice(src[0], "newid", "INV-0009", V.today);
  return FT.ticketsToInvoice(src, "newid", "INV-0009", V.today);
}
for (const v of V.conversions) deepCompare(plain(convert(v.case)), v.output, `conversions[${v.name}]`);
for (const v of V.conversion_errors) expectError(`conversion_errors[${v.name}]`, () => convert(v.case), v.code, v.message);

for (const v of V.imports) deepCompare(call(FT.sanitizeState, v.input), v.output, `imports[${v.name}]`);
for (const v of V.import_errors) expectError(`import_errors[${v.name}]`, () => FT.sanitizeState(inRealm(v.input)), v.code, v.message);

// Oversized logo, generated here to keep vectors.json small. Python test_schema_cli covers the same case.
expectError("import logo too big", () => FT.sanitizeState(inRealm({ app: "field-ticket", version: 1,
  business: { logo: "data:image/png;base64," + "A".repeat(1000004) } })), "bad_import", "business.logo: image is too large.");

deepCompare(call(FT.exampleState, V.today), V.example_state, "example_state");
deepCompare(plain(FT.blankState()), V.blank_state, "blank_state");
for (const [i, v] of V.clear_examples.entries()) deepCompare(call(FT.clearExamples, v.input), v.output, `clear_examples[${i}]`);

if (failures.length) {
  console.error(`FAIL: ${failures.length} of ${checks} checks`);
  for (const f of failures.slice(0, 40)) console.error("  " + f);
  process.exit(1);
}
console.log(`parity ok: ${checks} exact checks (${V.totals.length} totals, ${V.due.length} due dates, ${V.shifts.length} shifts, ` +
  `${V.conversions.length} conversions, ${V.imports.length + V.import_errors.length} import vectors)`);
