import { esc, fmtTs } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderEvents(state) {
  const f = state.filters;
  const pack = state.events || { items: [], total: 0 };
  const items = pack.items || [];
  const total = pack.total || 0;
  const body = panelBody(state, "events", items.length === 0 && !hasFilters(f), "No events.", () => table(items));
  const from = total === 0 ? 0 : f.offset + 1;
  const to = Math.min(f.offset + items.length, total);
  return `<div class="page">
    ${disconnectStrip(state)}
    ${pageHead("Events", `${total} total`)}
    ${filters(f)}
    ${body}
    <div class="pager">
      <button type="button" data-act="page" data-dir="-1" ${f.offset <= 0 ? "disabled" : ""}>Prev</button>
      <span>${from}–${to} of ${total}</span>
      <button type="button" data-act="page" data-dir="1" ${f.offset + (f.limit || 25) >= total ? "disabled" : ""}>Next</button>
    </div>
  </div>`;
}

function hasFilters(f) {
  return Boolean(f.level || f.asset || f.source || f.fingerprint || f.q);
}

function filters(f) {
  const levels = ["", "debug", "info", "warning", "error", "fatal"];
  const opts = levels.map((l) => `<option value="${l}" ${f.level === l ? "selected" : ""}>${l || "any"}</option>`).join("");
  return `<form class="filters" data-act="filters">
    <label>level <select name="level">${opts}</select></label>
    <label>source <input name="source" value="${esc(f.source)}" placeholder="journal"></label>
    <label>asset <input name="asset" value="${esc(f.asset)}" placeholder="proc-api"></label>
    <label>fingerprint <input name="fingerprint" value="${esc(f.fingerprint)}" class="mono"></label>
    <label>search <input name="q" value="${esc(f.q)}" placeholder="message"></label>
    <button type="submit">Filter</button>
  </form>`;
}

function table(items) {
  const rows = items.map((e) => `<tr>
    <td class="mono">${esc(fmtTs(e.ts))}</td>
    <td class="lv-${esc(e.level)}">${esc(e.level)}</td>
    <td>${esc(e.source)}</td>
    <td class="mono">${esc(e.asset_id)}</td>
    <td class="mono">${esc(e.fingerprint)}</td>
    <td>${esc(e.message)}</td>
  </tr>`);
  return `<table>
    <thead><tr><th>ts</th><th>level</th><th>source</th><th>asset</th><th>fingerprint</th><th>message</th></tr></thead>
    <tbody>${rows.join("")}</tbody>
  </table>`;
}
