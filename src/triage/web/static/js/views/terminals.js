import { esc } from "../fmt.js";
import { disconnectStrip, pageHead, panelBody } from "./common.js";

export function renderTerminals(state) {
  const terms = state.terminals || [];
  const body = panelBody(
    state,
    "terminals",
    terms.length === 0,
    "No terminals.",
    () => terms.map((t) => pane(t, state.paused[t.id])).join("")
  );
  const alive = terms.filter((t) => t.alive).length;
  return `<div class="page">${disconnectStrip(state)}${pageHead("Terminals", `${alive} alive · ${terms.length - alive} dead · ${terms.length} sessions`)}${body}</div>`;
}

function pane(t, paused) {
  const lines = (t.last_lines || []).join("\n") || "(no output)";
  const flag = t.alive ? "alive" : "dead";
  return `<section class="term" aria-label="${esc(t.name)}">
    <div class="term-h">
      <span class="name">${esc(t.name)}</span>
      <span class="mono muted">${esc(t.id)}</span>
      <span class="flag ${t.alive ? "on" : "off"}">${flag}</span>
      <button type="button" data-act="pause" data-id="${esc(t.id)}" aria-pressed="${paused ? "true" : "false"}">${paused ? "Resume" : "Pause"}</button>
    </div>
    <pre data-term="${esc(t.id)}" data-paused="${paused ? "1" : ""}">${esc(lines)}</pre>
  </section>`;
}
