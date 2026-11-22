import { esc, fmtTs } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderOverview(state) {
  const body = panelBody(
    state,
    "overview",
    !state.overview,
    "No overview data.",
    () => inner(state)
  );
  return `<div class="page">${disconnectStrip(state)}${pageHead("Overview", "sources to desk")}${body}</div>`;
}

function inner(state) {
  const o = state.overview;
  const assets = state.assets || [];
  const ticker = state.ticker.length ? state.ticker : (state.events.items || []).slice(0, 12);
  return `
    ${board(state)}
    <div class="stats" aria-label="Status">
      ${stat("Open incidents", o.open_incidents, o.open_incidents ? "down" : "ok", "#/incidents")}
      ${stat("Assets up", o.assets_up, "ok", "#/systems")}
      ${stat("Assets down", o.assets_down, o.assets_down ? "down" : "", "#/systems")}
      ${stat("Events / min", o.event_rate_per_min, "", "#/events")}
      ${stat("Agent", o.agent_busy ? "busy" : "idle", o.agent_busy ? "busy" : "ok", "#/incidents")}
    </div>
    <div class="sec-h">Assets</div>
    ${
      assets.length
        ? `<div class="asset-grid">${assets.map(box).join("")}</div>`
        : `<div class="state">No assets.</div>`
    }
    <div class="split">
      <section>
        <div class="sec-h">By kind</div>
        ${kindTable(assets)}
      </section>
      <section>
        <div class="sec-h">Live ticker</div>
        ${
          ticker.length
            ? `<ul class="ticker">${ticker.map(tick).join("")}</ul>`
            : `<div class="state">No events yet.</div>`
        }
      </section>
    </div>`;
}

function board(state) {
  const o = state.overview;
  const live = state.connected ? " live" : "";
  return `<div class="manifold${live}" aria-hidden="true">
    <div class="station"><span class="k">Sources</span><span class="v">${esc((o.assets_up || 0) + (o.assets_down || 0))}</span></div>
    <div class="pipe"></div>
    <div class="station"><span class="k">Ingest</span><span class="v">${esc(o.event_rate_per_min)}</span></div>
    <div class="pipe"></div>
    <div class="station"><span class="k">Agent</span><span class="v">${o.agent_busy ? "busy" : "idle"}</span></div>
    <div class="pipe"></div>
    <div class="station"><span class="k">Desk</span><span class="v">${esc(o.open_incidents)}</span></div>
  </div>`;
}

function stat(lbl, val, cls, href) {
  return `<button type="button" class="stat ${cls}" data-act="goto" data-href="${esc(href)}">
    <span class="lbl">${esc(lbl)}</span><span class="val">${esc(val)}</span>
  </button>`;
}

function box(a) {
  return `<button type="button" class="asset-box st-${esc(a.status)}" data-act="goto" data-href="#/systems/${esc(a.id)}">
    <span class="k">${esc(a.kind)}</span>
    <span class="n">${esc(a.name)}</span>
    <span class="s">${esc(a.status)}</span>
  </button>`;
}

function kindTable(assets) {
  const kinds = ["process", "terminal", "server", "url", "deploy"];
  const rows = kinds.map((k) => {
    const xs = assets.filter((a) => a.kind === k);
    const down = xs.filter((a) => a.status === "down").length;
    return `<tr><td class="mono">${k}</td><td>${xs.length}</td><td class="${down ? "st-down" : ""}">${down} down</td></tr>`;
  });
  return `<table><thead><tr><th>Kind</th><th>Count</th><th>Down</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function tick(ev) {
  return `<li>
    <span class="muted">${esc(fmtTs(ev.ts).slice(11, 19))}</span>
    <span class="lv lv-${esc(ev.level)}">${esc(ev.level)}</span>
    <span>${esc(ev.message)}</span>
  </li>`;
}
