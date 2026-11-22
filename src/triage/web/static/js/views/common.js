import { esc } from "../fmt.js";

export function loadingBox() {
  return `<div class="state" role="status">Loading…</div>`;
}

export function errorBox(msg) {
  return `<div class="state err" role="alert">${esc(msg)}</div>`;
}

export function emptyBox(msg) {
  return `<div class="state" role="status">${esc(msg)}</div>`;
}

export function panelBody(state, key, empty, emptyMsg, html) {
  if (state.loading[key] && empty) return loadingBox();
  if (state.error[key] && empty) return errorBox(state.error[key]);
  if (empty) return emptyBox(emptyMsg);
  return typeof html === "function" ? html() : html;
}

export function pageHead(title, sub = "") {
  const code = title.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase() || "TRG";
  return `<div class="head"><span class="bt-code">${esc(code)}</span><h1>${esc(title)}</h1><div class="sub">${esc(sub)}</div></div>`;
}

export function disconnectStrip(state) {
  if (state.connected) return "";
  const msg = state.mock
    ? "Disconnected — API missing. Showing fixture data."
    : "Disconnected — no live SSE.";
  return `<div class="strip" role="status">${msg}</div>`;
}
