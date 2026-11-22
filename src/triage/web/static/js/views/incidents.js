import { esc, fmtTs, pretty } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderIncidents(state, route) {
  const list = state.incidents || [];
  const id = route.id || "";
  const body = panelBody(
    state,
    "incidents",
    list.length === 0,
    "No incidents.",
    () => `<div class="inc-layout">${listCol(list, id)}${detailCol(state, id)}</div>`
  );
  return `<div class="page">${disconnectStrip(state)}${pageHead("Incidents", `${list.length} listed`)}${body}</div>`;
}

function listCol(list, id) {
  const items = list.map((inc) => {
    const on = inc.id === id ? ` aria-current="page"` : "";
    return `<a class="inc-item" href="#/incidents/${esc(inc.id)}"${on}>
      <div>${esc(inc.title)}</div>
      <div class="muted">${esc(inc.severity)} · ${esc(inc.status)}</div>
      <div class="mono muted">${esc(inc.fingerprint)}</div>
    </a>`;
  });
  return `<div class="inc-list">${items.join("")}</div>`;
}

function detailCol(state, id) {
  if (!id) return `<div class="state">Select an incident.</div>`;
  if (state.loading.incident) return `<div class="state" role="status">Loading…</div>`;
  if (state.error.incident) return `<div class="state err" role="alert">${esc(state.error.incident)}</div>`;
  const inc = state.incident;
  if (!inc || inc.id !== id) return `<div class="state">Incident not found.</div>`;
  const events = inc.events || [];
  const actions = inc.actions || [];
  return `<div>
    ${kv(inc)}
    <div class="sec-h">Trigger / events</div>
    ${eventTable(events)}
    <div class="sec-h">Gemini transcript</div>
    ${actions.length ? actions.map(actionBlock).join("") : `<div class="state">No actions.</div>`}
  </div>`;
}

function kv(inc) {
  const rows = [
    ["id", inc.id],
    ["title", inc.title],
    ["fingerprint", inc.fingerprint],
    ["severity", inc.severity],
    ["status", inc.status],
    ["event_id", inc.event_id],
    ["started_at", fmtTs(inc.started_at)],
    ["resolved_at", fmtTs(inc.resolved_at)],
    ["escalate_reason", inc.escalate_reason || "—"],
    ["report_path", inc.report_path || "—"],
  ];
  return `<div class="kv">${rows.map(([k, v]) => `<div>${esc(k)}</div><div class="${k === "fingerprint" || k === "report_path" ? "mono" : ""}">${esc(v)}</div>`).join("")}</div>`;
}

function eventTable(events) {
  if (!events.length) return `<div class="state">No linked events.</div>`;
  if (typeof events[0] === "string") {
    return `<table><thead><tr><th>event id</th></tr></thead><tbody>${events.map((id) => `<tr><td class="mono">${esc(id)}</td></tr>`).join("")}</tbody></table>`;
  }
  const rows = events.map((e) => `<tr>
    <td class="mono">${esc(fmtTs(e.ts))}</td>
    <td>${esc(e.level)}</td>
    <td class="mono">${esc(e.fingerprint)}</td>
    <td>${esc(e.message)}</td>
  </tr>`);
  return `<table><thead><tr><th>ts</th><th>level</th><th>fingerprint</th><th>message</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function actionBlock(a) {
  const ok = a.ok ? "ok" : "fail";
  return `<section class="action">
    <div class="action-h">
      <span>${esc(fmtTs(a.ts))}</span>
      <span>${esc(a.role)}</span>
      <span>${esc(a.name)}</span>
      <span class="${a.ok ? "st-up" : "st-down"}">${ok}</span>
    </div>
    ${io("input", a.input)}${io("output", a.output)}
  </section>`;
}

function io(label, value) {
  const text = pretty(value);
  if (!text) return "";
  return `<div class="io-lbl">${label}</div><pre>${esc(text)}</pre>`;
}
