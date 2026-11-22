import { esc, fmtTs, metaLine } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderSystems(state, route) {
  const id = route.id || "";
  const assets = state.assets || [];
  const selected = assets.find((a) => a.id === id) || null;
  const body = panelBody(
    state,
    "assets",
    assets.length === 0,
    "No assets.",
    () => table(assets, id) + detail(state, selected)
  );
  const up = assets.filter((a) => a.status === "up").length;
  const down = assets.filter((a) => a.status === "down").length;
  return `<div class="page">${disconnectStrip(state)}${pageHead("Systems", `${assets.length} assets · ${up} up · ${down} down`)}${body}</div>`;
}

function table(assets, id) {
  const rows = assets.map((a) => {
    const on = a.id === id ? " selected" : "";
    return `<tr class="clickable${on}" tabindex="0" data-act="goto" data-href="#/systems/${esc(a.id)}">
      <td class="mono">${esc(a.id)}</td>
      <td>${esc(a.kind)}</td>
      <td>${esc(a.name)}</td>
      <td class="st-${esc(a.status)}">${esc(a.status)}</td>
      <td class="mono">${esc(fmtTs(a.last_seen))}</td>
      <td>${esc(a.source)}</td>
      <td class="mono muted">${esc(metaLine(a.meta))}</td>
    </tr>`;
  });
  return `<table>
    <thead><tr><th>id</th><th>kind</th><th>name</th><th>status</th><th>last_seen</th><th>source</th><th>meta</th></tr></thead>
    <tbody>${rows.join("")}</tbody>
  </table>`;
}

function detail(state, asset) {
  if (!asset) {
    return `<div class="state">Select an asset for recent events.</div>`;
  }
  const items = (state.events.items || []).filter((e) => e.asset_id === asset.id);
  if (state.loading.events) return `<div class="sec-h">${esc(asset.name)}</div><div class="state">Loading…</div>`;
  if (!items.length) {
    return `<div class="sec-h">${esc(asset.name)}</div><div class="state">No recent events for this asset.</div>`;
  }
  const rows = items.map((e) => `<tr>
    <td class="mono">${esc(fmtTs(e.ts))}</td>
    <td class="lv-${esc(e.level)}">${esc(e.level)}</td>
    <td>${esc(e.source)}</td>
    <td class="mono">${esc(e.fingerprint)}</td>
    <td>${esc(e.message)}</td>
  </tr>`);
  return `<div class="sec-h">Recent events · ${esc(asset.name)}</div>
    <table><thead><tr><th>ts</th><th>level</th><th>source</th><th>fingerprint</th><th>message</th></tr></thead>
    <tbody>${rows.join("")}</tbody></table>`;
}
