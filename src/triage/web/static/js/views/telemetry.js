import { esc, fmtTs } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderTelemetry(state) {
  const t = state.telemetry;
  const body = panelBody(state, "telemetry", !t, "No telemetry.", () => inner(t));
  return `<div class="page">${disconnectStrip(state)}${pageHead("Telemetry", t ? `${t.heartbeats} heartbeats` : "")}${body}</div>`;
}

function inner(t) {
  const health = t.health || [];
  const cols = t.collectors || [];
  return `
    <div class="stats" aria-label="Rate">
      <div class="stat"><span class="lbl">Heartbeats</span><span class="val">${esc(t.heartbeats)}</span></div>
      <div class="stat"><span class="lbl">Events / min</span><span class="val">${esc(t.event_rate_per_min)}</span></div>
      <div class="stat"><span class="lbl">Health probes</span><span class="val">${health.length}</span></div>
      <div class="stat"><span class="lbl">Collectors</span><span class="val">${cols.length}</span></div>
      <div class="stat ${health.some((h) => !h.ok) ? "down" : "ok"}"><span class="lbl">Failing</span><span class="val">${health.filter((h) => !h.ok).length}</span></div>
    </div>
    <div class="sec-h">Health</div>
    ${
      health.length
        ? `<table>
            <thead><tr><th>name</th><th>url</th><th>ok</th><th>latency_ms</th><th>last_check</th></tr></thead>
            <tbody>${health.map(hRow).join("")}</tbody>
          </table>`
        : `<div class="state">No health checks.</div>`
    }
    <div class="sec-h">Collectors</div>
    ${
      cols.length
        ? `<table>
            <thead><tr><th>hostname</th><th>last_seen</th><th>event_count</th></tr></thead>
            <tbody>${cols.map(cRow).join("")}</tbody>
          </table>`
        : `<div class="state">No collectors.</div>`
    }`;
}

function hRow(h) {
  return `<tr>
    <td>${esc(h.name)}</td>
    <td class="mono">${esc(h.url)}</td>
    <td class="${h.ok ? "health-ok" : "health-bad"}">${h.ok ? "ok" : "fail"}</td>
    <td class="mono">${esc(h.latency_ms)}</td>
    <td class="mono">${esc(fmtTs(h.last_check))}</td>
  </tr>`;
}

function cRow(c) {
  return `<tr>
    <td class="mono">${esc(c.hostname)}</td>
    <td class="mono">${esc(fmtTs(c.last_seen))}</td>
    <td class="mono">${esc(c.event_count)}</td>
  </tr>`;
}
