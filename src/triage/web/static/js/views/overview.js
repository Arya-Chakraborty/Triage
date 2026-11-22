import { esc, fmtTs, metaLine } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderOverview(state) {
  const body = panelBody(
    state,
    "overview",
    !state.overview,
    "No overview data.",
    () => inner(state)
  );
  const o = state.overview;
  const sub = o
    ? `${(o.assets_up || 0) + (o.assets_down || 0)} assets · ${o.event_rate_per_min}/min · agent ${o.agent_busy ? "busy" : "idle"}`
    : "sources to desk";
  const extra = `<button type="button" class="reinit" data-act="reinitiate">Re-initiate</button>`;
  return `<div class="page">${disconnectStrip(state)}${pageHead("Overview", sub, extra)}${body}</div>`;
}

function inner(state) {
  const o = state.overview;
  const assets = state.assets || [];
  const events = state.ticker.length ? state.ticker : (state.events.items || []);
  const ticker = events.slice(0, 40);
  const total = (o.assets_up || 0) + (o.assets_down || 0);
  const last = ticker[0];
  return `
    <div class="quotes" aria-hidden="true">
      <div class="q"><div class="sym">SRC</div><span class="px">${esc(total)}</span><span class="chg">watched assets</span></div>
      <div class="q"><div class="sym">INGEST</div><span class="px">${esc(o.event_rate_per_min)}</span><span class="chg">events / min</span></div>
      <div class="q"><div class="sym">AGENT</div><span class="px ${o.agent_busy ? "" : "ok"}">${o.agent_busy ? "BUSY" : "IDLE"}</span><span class="chg">gemini loop</span></div>
      <div class="q"><div class="sym">DESK</div><span class="px ${o.open_incidents ? "down" : "ok"}">${esc(o.open_incidents)}</span><span class="chg">open incidents</span></div>
    </div>
    <div id="pipe-slot"></div>
    <div class="stats" aria-label="Status">
      ${stat("Open incidents", o.open_incidents, o.open_incidents ? "down" : "ok", "#/incidents", "needs human or fixing")}
      ${stat("Assets up", o.assets_up, "ok", "#/systems", `${total} total`)}
      ${stat("Assets down", o.assets_down, o.assets_down ? "down" : "", "#/systems", "health / process")}
      ${stat("Events / min", o.event_rate_per_min, "", "#/events", "rolling 60s")}
      ${stat("Agent", o.agent_busy ? "busy" : "idle", o.agent_busy ? "busy" : "ok", "#/incidents", last ? `last ${esc(fmtTs(last.ts).slice(11, 19))}` : "auto-fix")}
    </div>
    <div class="sec-h">Monitor · assets</div>
    ${
      assets.length
        ? `<div class="asset-grid">${assets.map(box).join("")}</div>`
        : `<div class="state">No assets.</div>`
    }
    <div class="split">
      <section>
        <div class="sec-h">Book · by kind</div>
        <div class="pane">
          ${kindTable(assets)}
          <div class="sec-h">Levels · tape mix</div>
          ${levelTable(events)}
          <div class="sec-h">Exceptions · down</div>
          ${downTable(assets)}
        </div>
      </section>
      <section>
        <div class="sec-h">Tape · last prints</div>
        <div class="pane">
        ${
          ticker.length
            ? `<ul class="ticker">${ticker.map(tick).join("")}</ul>`
            : `<div class="state">No events yet.</div>`
        }
        </div>
      </section>
    </div>
    <div class="sec-h">Desk · open incidents</div>
    ${incidentTable(state.incidents || [])}`;
}

function stat(lbl, val, cls, href, chg) {
  return `<button type="button" class="stat ${cls}" data-act="goto" data-href="${esc(href)}">
    <span class="lbl">${esc(lbl)}</span><span class="val">${esc(val)}</span><span class="chg">${esc(chg || "")}</span>
  </button>`;
}

function box(a) {
  const host = a.meta?.host || a.meta?.region || a.source || "";
  return `<button type="button" class="asset-box st-${esc(a.status)}" data-act="goto" data-href="#/systems/${esc(a.id)}">
    <span class="k">${esc(a.kind)}</span>
    <span class="s">${esc(a.status)}</span>
    <span class="n">${esc(a.name)}</span>
    <span class="meta">${esc(a.id)} · ${esc(host)} · ${esc(fmtTs(a.last_seen).slice(11, 19))} · ${esc(metaLine(a.meta).slice(0, 48))}</span>
  </button>`;
}

function kindTable(assets) {
  const kinds = ["process", "terminal", "server", "url", "deploy"];
  const rows = kinds.map((k) => {
    const xs = assets.filter((a) => a.kind === k);
    const down = xs.filter((a) => a.status === "down").length;
    const up = xs.filter((a) => a.status === "up").length;
    const deg = xs.filter((a) => a.status === "degraded").length;
    return `<tr>
      <td class="mono">${k}</td>
      <td class="num">${xs.length}</td>
      <td class="num st-up">${up}</td>
      <td class="num ${deg ? "st-degraded" : ""}">${deg}</td>
      <td class="num ${down ? "st-down" : ""}">${down}</td>
    </tr>`;
  });
  return `<table><thead><tr><th>Kind</th><th>N</th><th>Up</th><th>Deg</th><th>Down</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function levelTable(events) {
  const order = ["fatal", "error", "warning", "warn", "info", "debug"];
  const counts = {};
  events.forEach((e) => {
    const k = e.level === "warn" ? "warning" : e.level;
    counts[k] = (counts[k] || 0) + 1;
  });
  const rows = order
    .filter((k) => k !== "warn")
    .map((k) => {
      const n = counts[k] || 0;
      return `<tr><td class="lv lv-${k}">${k}</td><td class="num">${n}</td></tr>`;
    });
  return `<table><thead><tr><th>Level</th><th>N</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function downTable(assets) {
  const bad = assets.filter((a) => a.status === "down" || a.status === "degraded");
  if (!bad.length) return `<div class="state">No down or degraded assets.</div>`;
  const rows = bad.map((a) => `<tr class="clickable" tabindex="0" data-act="goto" data-href="#/systems/${esc(a.id)}">
    <td class="mono">${esc(a.id)}</td>
    <td>${esc(a.name)}</td>
    <td class="st-${esc(a.status)}">${esc(a.status)}</td>
    <td class="mono">${esc(fmtTs(a.last_seen).slice(11, 19))}</td>
  </tr>`);
  return `<table><thead><tr><th>id</th><th>name</th><th>status</th><th>seen</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function incidentTable(list) {
  const open = list.filter((i) => !["resolved", "failed"].includes(i.status));
  if (!open.length) return `<div class="state">No open incidents.</div>`;
  const rows = open.slice(0, 12).map((i) => `<tr class="clickable" tabindex="0" data-act="goto" data-href="#/incidents/${esc(i.id)}">
    <td class="sev-${esc(i.severity)}">${esc(i.severity)}</td>
    <td>${esc(i.status)}</td>
    <td>${esc(i.title)}</td>
    <td class="mono">${esc(i.fingerprint)}</td>
    <td class="mono">${esc(fmtTs(i.started_at).slice(11, 19))}</td>
  </tr>`);
  return `<table><thead><tr><th>sev</th><th>status</th><th>title</th><th>fingerprint</th><th>started</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function tick(ev) {
  return `<li>
    <span class="muted">${esc(fmtTs(ev.ts).slice(11, 19))}</span>
    <span class="lv lv-${esc(ev.level)}">${esc(ev.level)}</span>
    <span>${esc(ev.message)}</span>
  </li>`;
}
